"""Read-only route for discovering built-in agents (``GET /v1/agents``).

Built-in agents are the long-lived, shared agents the server provides
out of the box — the seeded ``claude-native-ui`` agent plus anything
registered at startup with ``omnigent server --agent``. They are the
``session_id IS NULL`` rows in ``agent_store``; ``agent_store.list()``
already filters to exactly these. Session-scoped agents (created via
multipart ``POST /v1/sessions``) belong to one conversation and are read
through ``GET /v1/sessions/{id}/agent`` — never here.

The Web UI's new-session picker calls this to discover bindable
built-ins, then creates a session with
``POST /v1/sessions {agent_id, host_id, workspace}``. See
``designs/BUILTIN_AGENTS.md``.

This is the read-only successor to the removed ``GET /api/agents`` list
for *discovery*. It also exposes ``POST /v1/agents`` to register a
reusable template agent (``session_id IS NULL``) at runtime from an
uploaded bundle — a thin HTTP wrapper over the same internal
:func:`omnigent.server.app._ensure_builtin_agent` seeding function the
server already runs at startup, so a runtime create reuses the exact
seeding logic (content-addressed, idempotent by name). There is still
no per-session agent create/update/delete here; session-scoped agent
writes happen through session creation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from omnigent.entities import Agent
from omnigent.errors import ErrorCode, OmnigentError
from omnigent.runtime.agent_cache import AgentCache
from omnigent.server.auth import AuthProvider, local_single_user_enabled
from omnigent.server.bundles import validate_agent_bundle
from omnigent.server.routes._auth_helpers import require_user as _require_user
from omnigent.server.schemas import AgentObject, MCPServerSummary, PaginatedList, SkillSummary
from omnigent.stores import AgentStore, ArtifactStore

_logger = logging.getLogger(__name__)

# Cap an uploaded agent bundle at 10 MiB. A template agent spec is a
# small config.yaml (+ optional AGENTS.md / skills); this stops an
# oversized upload from buffering unbounded memory. Mirrors the intent
# of the session-bundle upload cap.
_MAX_BUNDLE_BYTES: int = 10 * 1024 * 1024

# Read uploads in 1 MiB chunks so an oversized body is aborted ~1 MiB
# past the cap instead of being buffered whole. Mirrors
# ``omnigent.server.routes.sessions._read_upload_capped``.
_UPLOAD_READ_CHUNK_BYTES: int = 1024 * 1024


async def _read_upload_capped(file: UploadFile, limit_bytes: int) -> bytes:
    """Read an uploaded file into memory, aborting past *limit_bytes*.

    :param file: The multipart upload.
    :param limit_bytes: Maximum allowed size in bytes.
    :returns: The full file content.
    :raises HTTPException: 413 when the upload exceeds *limit_bytes*.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > limit_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Agent bundle exceeds the {limit_bytes // (1024 * 1024)} MB limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _to_agent_object(agent: Agent, agent_cache: AgentCache) -> AgentObject:
    """
    Convert a runtime Agent entity to an API-layer AgentObject.

    Loads the spec from cache to populate ``mcp_servers``,
    ``skills``, and (when the stored row has none) the
    ``description``; on any load failure those fall back to empty /
    the stored value rather than failing the whole list — one
    unreadable bundle must not break discovery.

    :param agent: The runtime agent entity, e.g. the seeded
        ``claude-native-ui`` agent.
    :param agent_cache: Cache used to load the agent spec.
    :returns: An :class:`AgentObject` for the API response.
    """
    mcp_servers: list[MCPServerSummary] = []
    skills: list[SkillSummary] = []
    terminals: list[str] = []
    harness: str | None = None
    # Prefer the stored entity's description; fall back to the spec's
    # top-level description when the stored value is unset (single-file
    # YAML agents don't persist it at registration today). Lets the
    # new-session picker show a hover description without a migration.
    description: str | None = agent.description
    try:
        # Built-ins are operator-authored template agents
        # (session_id is None), so ${VAR} expansion against the server
        # env is allowed here; a tenant session-scoped agent would not
        # expand.
        loaded = agent_cache.load(
            agent.id, agent.bundle_location, expand_env=agent.session_id is None
        )
        if description is None:
            description = loaded.spec.description
        # Declared terminal names, in spec order (mirrors the
        # session-agent endpoint so both report it consistently).
        terminals = list(loaded.spec.terminals or {})
        # Bundled skills only — host-discovered skills are runner-owned
        # and unknowable here (no session, no runner). The new-session
        # composer uses this list for its "/" menu.
        skills = [SkillSummary(name=s.name, description=s.description) for s in loaded.spec.skills]
        mcp_servers = [
            MCPServerSummary(
                name=srv.name,
                transport=srv.transport,
                description=srv.description,
                url=srv.url,
                command=srv.command,
                args=srv.args,
            )
            for srv in loaded.spec.mcp_servers
        ]
        # Kind for the Add Agent picker (Codex vs Claude). Stays None
        # when the bundle can't be loaded (the except below).
        harness = loaded.spec.executor.harness_kind
    except Exception:  # noqa: BLE001 — spec load failure must not break the list
        _logger.debug(
            "Failed to load spec for agent %s; mcp_servers/skills will be empty",
            agent.id,
            exc_info=True,
        )
    return AgentObject(
        id=agent.id,
        name=agent.name,
        version=agent.version,
        description=description,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        harness=harness,
        mcp_servers=mcp_servers,
        mcp_servers_editable=False,
        skills=skills,
        terminals=terminals,
    )


def create_builtin_agents_router(
    agent_store: AgentStore,
    agent_cache: AgentCache,
    *,
    artifact_store: ArtifactStore | None = None,
    auth_provider: AuthProvider | None = None,
) -> APIRouter:
    """Build the router for ``GET``/``POST`` ``/v1/agents``.

    Mounted with ``prefix="/v1"`` so the final path is ``/v1/agents``.

    :param agent_store: Store whose ``list()`` returns only built-in
        (``session_id IS NULL``) agents; also used by ``POST`` to fetch
        the freshly-registered agent by name.
    :param agent_cache: Cache for loading specs (populates
        ``mcp_servers`` on each agent; warm-swapped on a ``POST``).
    :param artifact_store: Store for agent bundles. Required for the
        ``POST`` create path (it stores the uploaded bundle); when
        ``None`` the create route is still mounted but returns 500 if
        called, matching how the server always wires it in practice.
    :param auth_provider: Optional auth provider; when set, the caller
        must be authenticated.
    :returns: A FastAPI router exposing the list and runtime create.
    """
    router = APIRouter()

    @router.get("/agents")
    async def list_builtin_agents(
        request: Request,
        limit: int = Query(default=20, ge=1, le=1000),
        after: str | None = Query(default=None),
        before: str | None = Query(default=None),
        order: str = Query(default="desc", pattern="^(asc|desc)$"),
    ) -> PaginatedList:
        """List built-in agents with cursor-based pagination.

        Returns only built-in agents — ``agent_store.list()`` filters
        ``session_id IS NULL`` — so session-scoped agents never appear.

        :param request: The incoming FastAPI request (for auth).
        :param limit: Maximum number of agents to return (1-1000).
        :param after: Cursor — return agents after this id.
        :param before: Cursor — return agents before this id.
        :param order: Sort order, ``"asc"`` or ``"desc"``.
        :returns: A :class:`PaginatedList` of built-in agents.
        """
        _require_user(request, auth_provider)
        page = agent_store.list(limit=limit, after=after, before=before, order=order)
        return PaginatedList(
            data=[_to_agent_object(a, agent_cache) for a in page.data],
            first_id=page.first_id,
            last_id=page.last_id,
            has_more=page.has_more,
        )

    @router.post("/agents")
    async def create_builtin_agent(
        request: Request,
        bundle: Annotated[UploadFile, File(...)],
    ) -> AgentObject:
        """Register a reusable template agent from an uploaded bundle.

        This is a thin HTTP wrapper over the server's own startup
        seeding function :func:`omnigent.server.app._ensure_builtin_agent`:
        it validates the uploaded ``.tar.gz`` with omnigent's existing
        bundle validator, then calls that function to create (or refresh,
        idempotently by name) a built-in (``session_id IS NULL``) agent
        row — the same kind ``GET /v1/agents`` lists. No new
        agent-creation logic: the create path and the ``--agent`` /
        ``OMNIGENT_BUILTIN_AGENT_DIRS`` startup seeding share one
        implementation.

        :param request: The incoming request (for auth — same
            header-trust auth as ``GET /v1/agents``).
        :param bundle: Multipart upload of the agent bundle
            (``.tar.gz`` of a directory containing ``config.yaml``).
        :returns: The :class:`AgentObject` for the registered agent.
        :raises OmnigentError: 400 on an invalid bundle / missing name
            / unregistered policy handler; 500 if no artifact store is
            configured.
        :raises HTTPException: 413 if the upload exceeds the size cap.
        """
        _require_user(request, auth_provider)

        if artifact_store is None:
            raise OmnigentError(
                "Artifact store not configured",
                code=ErrorCode.INTERNAL_ERROR,
            )

        bundle_bytes = await _read_upload_capped(bundle, _MAX_BUNDLE_BYTES)

        # Validate with omnigent's existing untrusted-upload validator
        # (tar extraction + spec parse, off the event loop). It parses
        # with expand_env=False and enforces the policy-handler
        # allowlist on a shared/multi-user server — exactly as the
        # session-bundle upload path does. A bad bundle raises
        # OmnigentError(INVALID_INPUT) -> 400, never a 500.
        spec = await asyncio.to_thread(
            validate_agent_bundle,
            bundle_bytes,
            enforce_handler_allowlist=not local_single_user_enabled(),
        )
        if spec.name is None:
            raise OmnigentError("spec missing name", code=ErrorCode.INVALID_INPUT)

        # Reuse the server's own seeding function: content-addressed,
        # idempotent by name (create, or refresh-in-place when the
        # bundle changed). Imported here to avoid a circular import —
        # omnigent.server.app imports this module to mount the router.
        from omnigent.server.app import _ensure_builtin_agent

        await asyncio.to_thread(
            _ensure_builtin_agent,
            agent_store,
            artifact_store,
            agent_cache,
            name=spec.name,
            bundle_bytes=bundle_bytes,
        )

        agent = await asyncio.to_thread(agent_store.get_by_name, spec.name)
        if agent is None:  # pragma: no cover — _ensure_builtin_agent just wrote it
            raise OmnigentError(
                f"agent {spec.name!r} not found after registration",
                code=ErrorCode.INTERNAL_ERROR,
            )
        return _to_agent_object(agent, agent_cache)

    return router
