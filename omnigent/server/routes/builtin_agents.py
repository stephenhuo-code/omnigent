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
import dataclasses
import logging
import re
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from omnigent.entities import Agent
from omnigent.errors import ErrorCode, OmnigentError
from omnigent.runtime.agent_cache import AgentCache
from omnigent.server.auth import AuthProvider, local_single_user_enabled
from omnigent.server.bundles import validate_agent_bundle
from omnigent.server.routes._auth_helpers import require_user as _require_user
from omnigent.server.schemas import AgentObject, MCPServerSummary, PaginatedList, SkillSummary
from omnigent.spec.types import AgentSpec, SharePolicy
from omnigent.stores import AgentStore, ArtifactStore

_logger = logging.getLogger(__name__)

# ── Safe-spec gate for HTTP-uploaded built-ins ─────────────────────────
#
# A built-in agent (``session_id IS NULL``) is the runtime's
# *trusted/operator-authored* provenance class: its spec is later loaded
# with ``expand_env=True`` (see ``runtime/agent_cache.load`` and the
# ``expand_env=(agent.session_id is None)`` call sites in
# ``server/routes/sessions.py``). With ``expand_env=True`` the parser
# expands ``${VAR}`` / ``$VAR`` references against the *server process
# environment* in these carrier fields (the complete set found by
# grepping ``expand_env_vars`` / ``os.path.expandvars`` in
# ``spec/parser.py``):
#
#   - ``llm.connection``      (parser.py:299 — lifted onto executor.connection)
#   - ``executor.connection`` (parser.py:548)
#   - ``executor.auth``       (parser.py:610/616 — api_key, base_url)
#   - ``mcp_servers[*]``      headers / env / url (parser.py:2211/2218/2355/2424)
#
# ``validate_agent_bundle(expand_env=False)`` only protects the
# *validation-time* parse; the *runtime* load still expands. So an HTTP
# upload promoted to a built-in is a latent server-secret-exfil
# primitive: a crafted bundle could put ``${SOME_SECRET}`` in an MCP
# header/url and exfiltrate it to a spec-controlled endpoint.
#
# Our agent-library built-ins need: name, description, instructions
# (system prompt), harness (executor type/harness), model, and — for the
# per-agent API key feature (ADR-027 §4') — a LITERAL ``executor.auth``
# (and ``executor``/``llm`` connection). So we apply a POSITIVE
# whitelist: an uploaded built-in spec may populate ONLY the safe fields
# below; the three connection/auth env-expansion carriers are
# allowed-if-no-env-ref (a literal ``sk-...`` key has no ``${}`` ref so
# ``expand_env`` does nothing → safe; a ``${SERVER_SECRET}`` ref is still
# rejected → exfil stays closed). Every other env-expansion carrier (MCP
# fields) and every tool/secret/sub-agent bearer or capability flag is
# rejected 400. This closes the exfil at zero cost to the feature and is
# robust against future spec fields (default = reject).

# Keys permitted inside ``executor.config`` for an uploaded built-in.
# ``harness`` selects the harness kind (e.g. ``claude-native``);
# ``profile`` names a server-side credential profile (a *reference*,
# not a secret value, and not env-expanded). Everything else
# (notably a nested ``os_env``) is rejected.
_ALLOWED_EXECUTOR_CONFIG_KEYS: frozenset[str] = frozenset({"harness", "profile"})

# Matches a ``$VAR`` or ``${VAR}`` reference (mirrors the parser's
# ``_UNRESOLVED_VAR_RE``). Because the gate runs on a spec parsed with
# ``expand_env=False``, these references survive verbatim and can be
# detected before the trusted runtime load would expand them.
_ENV_REF_RE = re.compile(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*")

_SAFE_SPEC_REJECT_MSG = (
    "agent-library uploads may only set name/description/instructions/"
    "harness/model and a LITERAL executor auth/connection (per-agent API "
    "key); env references (${VAR}/$VAR), MCP servers, sub-agents, skills, "
    "tools, os_env/terminals, guardrails, and capability flags "
    "(spawn/timers/agent_session_sharing/async) are not allowed"
)


def _contains_env_ref(value: Any) -> bool:
    """Return True if *value* (recursively) carries a ``$VAR``/``${VAR}`` ref.

    Walks strings, mappings, sequences, and dataclass instances so a
    reference nested anywhere inside an allowed field is caught —
    ``llm.connection``/``executor.connection`` are plain dicts, while
    ``executor.auth`` is a frozen dataclass (e.g. :class:`ApiKeyAuth`
    with ``api_key``/``base_url``), so dataclass support is what makes a
    ``${SECRET}`` in a per-agent key detectable.

    :param value: Any parsed spec value (str, dict, list, dataclass, scalar).
    :returns: ``True`` if an env reference is present anywhere.
    """
    if isinstance(value, str):
        return _ENV_REF_RE.search(value) is not None
    if isinstance(value, dict):
        return any(_contains_env_ref(v) for v in value.values()) or any(
            _contains_env_ref(k) for k in value
        )
    if isinstance(value, (list, tuple, set)):
        return any(_contains_env_ref(v) for v in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return any(_contains_env_ref(getattr(value, f.name)) for f in dataclasses.fields(value))
    return False


def _assert_safe_builtin_spec(spec: AgentSpec) -> None:
    """Reject an uploaded built-in spec that exceeds the safe field set.

    Positive whitelist: an HTTP-uploaded built-in (which the runtime
    loads with ``expand_env=True``) may declare ONLY name, description,
    instructions, the executor type/harness/model, and LITERAL (non
    env-referencing) executor ``auth``/``connection`` and ``llm.connection``
    — the per-agent API key path (SDK harnesses read ``executor.auth``).
    A literal ``api_key`` (e.g. ``sk-...``) carries no ``${}`` ref so the
    runtime ``expand_env`` expands nothing → safe; any ``$VAR``/``${VAR}``
    ref in those carriers is still rejected (server-secret exfil stays
    closed). Any other env-expansion carrier (MCP fields) or
    tool/secret/sub-agent bearer is rejected with a clear 400.

    :param spec: The spec parsed from the uploaded bundle (parsed with
        ``expand_env=False``, so env references survive verbatim).
    :raises OmnigentError: ``INVALID_INPUT`` (HTTP 400) if the spec
        populates any field outside the safe whitelist or carries any
        ``$VAR`` / ``${VAR}`` reference.
    """

    def _reject(detail: str) -> None:
        raise OmnigentError(
            f"{_SAFE_SPEC_REJECT_MSG} ({detail})",
            code=ErrorCode.INVALID_INPUT,
        )

    # ── Tool / secret / sub-agent bearers: must be absent ──────────────
    if spec.mcp_servers:
        _reject("mcp_servers declared")
    if spec.sub_agents:
        _reject("sub_agents declared")
    if spec.skills:
        _reject("bundled skills declared")
    if spec.local_tools:
        _reject("local_tools declared")
    if spec.guardrails is not None:
        _reject("guardrails declared")
    if spec.os_env is not None:
        _reject("os_env declared")
    if spec.terminals:
        _reject("terminals declared")
    if spec.params:
        _reject("params declared")
    # tools.agents grants sub-agent spawning; any non-default tools.agents
    # or tools.builtins is outside the safe set.
    if spec.tools.agents:
        _reject("tools.agents declared")
    if spec.tools.builtins:
        _reject("tools.builtins declared")
    # Non-default skills_filter ("all" is the parser default) would change
    # the host-skill surface; keep it at the default.
    if spec.skills_filter != "all":
        _reject("skills_filter declared")

    # ── Top-level capability/behavior flags: must stay at their safe
    # defaults. A library agent only ever needs name/instructions/harness/
    # model — none of these flags. Each toggles a privileged tool surface
    # or changes execution behavior, so a non-default value is an
    # escalation outside the whitelist (a true default-reject gate rejects
    # any deviation, not only env-expansion carriers):
    #   - spawn=True            → registers ``sys_session_create`` (launch
    #     arbitrary agents/bundles) plus session send/close — a capability
    #     escalation beyond a plain chat agent.
    #   - timers=True           → registers ``sys_timer_set`` /
    #     ``sys_timer_cancel`` (durable background firings).
    #   - agent_session_sharing != NONE → registers ``sys_session_share``,
    #     which MUTATES access control (can grant ``__public__`` read).
    #   - async_enabled != True (the parser default) → would change the
    #     async-dispatch tool surface (``sys_call_async`` / ``sys_read_inbox``
    #     / ``sys_cancel_async``); the safe library profile is the default.
    # These are NOT env-expansion carriers (the Critical stays closed via
    # the scan below); they round out the positive whitelist so the upload
    # endpoint can only ever produce a plain chat agent.
    if spec.spawn:
        _reject("spawn declared")
    if spec.timers:
        _reject("timers declared")
    if spec.agent_session_sharing != SharePolicy.NONE:
        _reject("agent_session_sharing declared")
    if not spec.async_enabled:
        _reject("async (async_enabled) declared")

    # ── Executor: only type + harness/profile-in-config + model + a
    # literal auth/connection. ``executor.auth`` is the per-agent API key
    # carrier (SDK harnesses claude-sdk/codex/qwen/pi read it); it is
    # ALLOWED with literal values and env-scanned below (an env ref is
    # still rejected). Reject a ``profile`` (server-side credential
    # reference, outside the per-agent-key feature) and any config key
    # beyond harness/profile (notably a nested os_env). ────────────────
    executor = spec.executor
    if executor.profile is not None:
        _reject("executor.profile declared")
    extra_cfg = set(executor.config) - _ALLOWED_EXECUTOR_CONFIG_KEYS
    if extra_cfg:
        _reject(f"executor.config keys {sorted(extra_cfg)} not allowed")

    # ── Env-reference scan over the env-expansion carriers that ARE
    # permitted to be present (literal executor auth + executor/llm
    # connection — the complete expandable-and-allowed set; MCP fields,
    # the only other carriers, are rejected above). After an
    # expand_env=False parse, a ``${SECRET}`` left in any of these would
    # be expanded against the server env at the trusted runtime load — so
    # reject any reference anywhere in them (literal-only). This keeps the
    # secret-exfil hole closed while permitting a literal per-agent key. ─
    if _contains_env_ref(executor.auth):
        _reject("env reference in executor auth")
    if _contains_env_ref(executor.connection):
        _reject("env reference in executor connection")
    if spec.llm is not None and _contains_env_ref(spec.llm.connection):
        _reject("env reference in llm connection")
    # Defense in depth: also reject an env reference anywhere in the
    # passthrough kwargs / executor config we let through.
    if spec.llm is not None and _contains_env_ref(spec.llm.extra):
        _reject("env reference in llm config")
    if _contains_env_ref(executor.config):
        _reject("env reference in executor config")


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

        # Safe-spec gate: an HTTP-uploaded built-in (session_id IS NULL)
        # is loaded with expand_env=True at runtime, so any env-expansion
        # carrier (MCP server env/headers/url, executor auth/connection)
        # would expand ${VAR} against the server process environment —
        # a server-secret-exfil primitive. validate_agent_bundle only
        # parses with expand_env=False (validation-time), NOT the runtime
        # load, so restrict uploads to the safe field whitelist here.
        _assert_safe_builtin_spec(spec)

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
