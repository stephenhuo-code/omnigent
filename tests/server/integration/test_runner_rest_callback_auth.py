"""Integration tests for runner REST-callback auth under multi-user mode.

A server-managed runner runs in a sandbox container with no user
identity (no auth cookie / ``X-Forwarded-Email`` header). It calls
back to the server over REST with ``Authorization: Bearer {binding
token}``. Header-mode auth (``UnifiedAuthProvider(source="header")``)
ignores that bearer, so without the binding-token fallback every
runner REST callback 401s and the native terminal cannot bootstrap.

These tests pin the T3.6 fix: the sessions router falls back to
deriving the *managed runner's owner* from the binding token when no
normal identity is present, mirroring the T3.5 WS-tunnel fix. The
fallback must fire ONLY when identity is absent, must still reject an
absent/invalid token, and must never override a present identity.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from omnigent.db.utils import now_epoch
from omnigent.runner.identity import token_bound_runner_id
from omnigent.runtime.agent_cache import AgentCache
from omnigent.server.app import create_app
from omnigent.server.auth import LEVEL_OWNER, UnifiedAuthProvider
from omnigent.stores.agent_store.sqlalchemy_store import SqlAlchemyAgentStore
from omnigent.stores.artifact_store.local import LocalArtifactStore
from omnigent.stores.conversation_store.sqlalchemy_store import (
    SqlAlchemyConversationStore,
)
from omnigent.stores.file_store.sqlalchemy_store import SqlAlchemyFileStore
from omnigent.stores.host_store import HostStore
from omnigent.stores.permission_store.sqlalchemy_store import (
    SqlAlchemyPermissionStore,
)
from tests.server.helpers import build_agent_bundle

pytestmark = pytest.mark.asyncio

OWNER = "alice@example.com"
BINDING_TOKEN = "server-issued-managed-binding-token-rest"


@pytest.fixture()
def auth_app(db_uri: str, tmp_path: Path) -> FastAPI:
    """Header-auth, host-enabled app — the deployed multi-user posture.

    Strict header mode (no ``X-Forwarded-Email`` => unauthenticated)
    plus a host store so the managed-runner owner lookup is live.
    """
    artifact_store = LocalArtifactStore(str(tmp_path / "artifacts"))
    app = create_app(
        agent_store=SqlAlchemyAgentStore(db_uri),
        file_store=SqlAlchemyFileStore(db_uri),
        conversation_store=SqlAlchemyConversationStore(db_uri),
        artifact_store=artifact_store,
        agent_cache=AgentCache(
            artifact_store=artifact_store,
            cache_dir=tmp_path / "cache",
        ),
        permission_store=SqlAlchemyPermissionStore(db_uri),
        # Strict header mode: absent header => None (unauthenticated),
        # so the only way a runner callback authenticates is via the
        # binding-token fallback under test.
        auth_provider=UnifiedAuthProvider(source="header", local_single_user=False),
        host_store=HostStore(db_uri),
    )
    # Test-only: stash the artifact store so the seed helper can put a
    # real agent bundle (so agent/contents returns 200, not a 500 on a
    # missing bundle). create_app does not normally expose it on state.
    app.state.artifact_store = artifact_store
    return app


@pytest_asyncio.fixture()
async def auth_client(auth_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=auth_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _seed_managed_session(app: FastAPI, db_uri: str, *, owner: str = OWNER) -> str:
    """Create a managed session bound to the binding-token runner id.

    Models the steady state after a managed launch: a server-managed
    host row (``sandbox_provider`` set), a conversation bound to that
    host and to the runner id derived from the binding token, and an
    OWNER grant for the owning user. Returns the session id.

    The app and these fresh store handles share one ``db_uri``, so rows
    written here are visible to the request path under test.
    """
    host_store: HostStore = app.state.host_store
    conv_store = SqlAlchemyConversationStore(db_uri)
    perm_store = SqlAlchemyPermissionStore(db_uri)
    agent_store = SqlAlchemyAgentStore(db_uri)

    agent_id = f"ag_{owner.replace('@', '_')}"
    bundle_location = f"{agent_id}/bundle"
    agent_store.create(
        agent_id=agent_id,
        name=f"agent-{owner}",
        bundle_location=bundle_location,
    )
    # Store a real bundle so the snapshot + agent/contents callback have
    # something to read (otherwise the local artifact store KeyErrors).
    app.state.artifact_store.put(
        bundle_location, build_agent_bundle(name=f"agent-{owner}")
    )

    host_id = f"host_{owner.replace('@', '_')}"
    host_store.register_managed_host(
        host_id=host_id,
        name=f"managed-{host_id}",
        owner=owner,
        token=BINDING_TOKEN if owner == OWNER else f"{BINDING_TOKEN}-{owner}",
        provider="modal",
        sandbox_id=f"sb-{owner}",
        token_expires_at=now_epoch() + 3600,
    )
    runner_id = token_bound_runner_id(
        BINDING_TOKEN if owner == OWNER else f"{BINDING_TOKEN}-{owner}"
    )
    conv = conv_store.create_conversation(
        title="managed session",
        agent_id=agent_id,
        host_id=host_id,
        runner_id=runner_id,
        # A host-bound conversation requires a workspace
        # (ck_conversations_workspace_required_for_host).
        workspace="/workspace",
    )
    perm_store.ensure_user(owner)
    perm_store.grant(owner, conv.id, LEVEL_OWNER)
    return conv.id


async def test_runner_rest_callback_binding_token_authenticates_as_owner(
    auth_app: FastAPI,
    auth_client: httpx.AsyncClient,
    db_uri: str,
) -> None:
    """(a) No identity header + valid managed binding token => 200 as owner.

    The runner's ``GET /v1/sessions/{id}`` callback, carrying only the
    server-issued binding token as a bearer (no ``X-Forwarded-Email``),
    must authenticate as the managed session's owner and succeed —
    not 401.
    """
    session_id = _seed_managed_session(auth_app, db_uri)

    resp = await auth_client.get(
        f"/v1/sessions/{session_id}",
        headers={"Authorization": f"Bearer {BINDING_TOKEN}"},
    )

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["id"] == session_id


async def test_runner_rest_callback_no_token_still_rejected(
    auth_app: FastAPI,
    auth_client: httpx.AsyncClient,
    db_uri: str,
) -> None:
    """(b) No identity + no/invalid bearer => still 401 (no new anon access)."""
    session_id = _seed_managed_session(auth_app, db_uri)

    # No Authorization header at all.
    resp_none = await auth_client.get(f"/v1/sessions/{session_id}")
    assert resp_none.status_code == 401, (
        f"expected 401 with no creds, got {resp_none.status_code}: {resp_none.text}"
    )

    # A bearer that derives an unknown runner id (no managed session).
    resp_bad = await auth_client.get(
        f"/v1/sessions/{session_id}",
        headers={"Authorization": "Bearer not-a-real-binding-token"},
    )
    assert resp_bad.status_code == 401, (
        f"expected 401 with bogus token, got {resp_bad.status_code}: {resp_bad.text}"
    )


async def test_present_identity_header_wins_over_token_fallback(
    auth_app: FastAPI,
    auth_client: httpx.AsyncClient,
    db_uri: str,
) -> None:
    """(c) A present X-Forwarded-Email wins; the token fallback isn't consulted.

    Bob presents his own identity header AND (adversarially) alice's
    binding token. The fallback must NOT fire — the request is bob's,
    and bob has no access to alice's session, so it 404s (existence
    hidden) rather than silently authenticating as alice.
    """
    session_id = _seed_managed_session(auth_app, db_uri)

    resp = await auth_client.get(
        f"/v1/sessions/{session_id}",
        headers={
            "X-Forwarded-Email": "bob@test",
            "Authorization": f"Bearer {BINDING_TOKEN}",
        },
    )

    # Identity (bob) wins: he is not the owner and has no grant, so the
    # normal permission path denies. Token fallback would have made this
    # 200-as-alice — that must NOT happen.
    assert resp.status_code in (403, 404), (
        f"present identity must win (expected 403/404), got "
        f"{resp.status_code}: {resp.text}"
    )


async def test_require_user_guarded_route_honors_token_fallback(
    auth_app: FastAPI,
    auth_client: httpx.AsyncClient,
    db_uri: str,
) -> None:
    """The fallback covers ``_require_user`` routes too, not just ``_get_user_id``.

    ``GET /v1/sessions/{id}/agent/contents`` (a runner callback) gates on
    ``_require_user``. With only the binding token, the request must
    authenticate as the owner and return the bundle (200). With no creds
    it must still 401. This proves the single chokepoint shadows BOTH
    ``_get_user_id`` and ``_require_user``.
    """
    session_id = _seed_managed_session(auth_app, db_uri)

    with_token = await auth_client.get(
        f"/v1/sessions/{session_id}/agent/contents",
        headers={"Authorization": f"Bearer {BINDING_TOKEN}"},
    )
    assert with_token.status_code == 200, (
        f"binding token should clear the _require_user gate, got "
        f"{with_token.status_code}: {with_token.text}"
    )

    no_creds = await auth_client.get(f"/v1/sessions/{session_id}/agent/contents")
    assert no_creds.status_code == 401, (
        f"no creds must 401 on _require_user route, got "
        f"{no_creds.status_code}: {no_creds.text}"
    )


async def test_runner_rest_callback_token_unknown_runner_rejected(
    auth_app: FastAPI,
    auth_client: httpx.AsyncClient,
    db_uri: str,
) -> None:
    """A syntactically valid token whose runner has no managed session => 401.

    Proves the fallback fails closed: deriving a runner id is not enough;
    it must resolve to a live, server-managed session.
    """
    session_id = _seed_managed_session(auth_app, db_uri)

    # Valid-shaped token, but never registered against any managed host.
    resp = await auth_client.get(
        f"/v1/sessions/{session_id}",
        headers={"Authorization": "Bearer some-other-unregistered-token"},
    )
    assert resp.status_code == 401, (
        f"unknown managed runner must 401, got {resp.status_code}: {resp.text}"
    )
