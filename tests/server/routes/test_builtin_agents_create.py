"""Tests for runtime template-agent creation (``POST /v1/agents``).

``POST /v1/agents`` is a thin HTTP wrapper over the server's own
startup seeding function (``_ensure_builtin_agent``): it validates an
uploaded bundle with omnigent's existing validator and registers a
reusable built-in (``session_id IS NULL``) agent — the same kind
``GET /v1/agents`` lists. These tests prove create -> list, that bad
bundles 4xx (not 500), and idempotency by name.
"""

from __future__ import annotations

import httpx

from tests.server.helpers import build_agent_bundle


def _claude_native_bundle(name: str, description: str | None = None) -> bytes:
    """Minimal claude-native template-agent bundle for the create tests."""
    return build_agent_bundle(
        name=name,
        description=description,
        executor={"type": "omnigent", "config": {"harness": "claude-native"}},
    )


async def test_post_agent_creates_and_lists(client: httpx.AsyncClient) -> None:
    """A valid bundle -> 200 AgentObject, then it shows up in GET /v1/agents."""
    bundle = _claude_native_bundle("probe-helper", description="answers in one word")

    resp = await client.post(
        "/v1/agents",
        files={"bundle": ("agent.tar.gz", bundle, "application/gzip")},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "probe-helper"
    assert body["object"] == "agent"
    assert body["harness"] == "claude-native"
    assert body["description"] == "answers in one word"
    new_id = body["id"]
    assert new_id

    # The new agent is a built-in (session_id NULL) and is listed.
    listed = await client.get("/v1/agents?limit=1000")
    assert listed.status_code == 200
    ids = [a["id"] for a in listed.json()["data"]]
    assert new_id in ids


async def test_post_agent_invalid_bundle_is_4xx(client: httpx.AsyncClient) -> None:
    """A non-tar / garbage bundle is rejected with a 4xx, never a 500."""
    resp = await client.post(
        "/v1/agents",
        files={"bundle": ("agent.tar.gz", b"not a tarball", "application/gzip")},
    )
    assert 400 <= resp.status_code < 500, resp.text


async def test_post_agent_empty_bundle_is_4xx(client: httpx.AsyncClient) -> None:
    """An empty bundle is rejected with a 4xx, never a 500."""
    resp = await client.post(
        "/v1/agents",
        files={"bundle": ("agent.tar.gz", b"", "application/gzip")},
    )
    assert 400 <= resp.status_code < 500, resp.text


async def test_post_agent_is_idempotent_by_name(client: httpx.AsyncClient) -> None:
    """Posting the same name twice is a no-op upsert: same id, no duplicate."""
    bundle = _claude_native_bundle("dup-agent")

    first = await client.post(
        "/v1/agents",
        files={"bundle": ("agent.tar.gz", bundle, "application/gzip")},
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]

    second = await client.post(
        "/v1/agents",
        files={"bundle": ("agent.tar.gz", bundle, "application/gzip")},
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first_id

    # Exactly one row with this name in the listing.
    listed = await client.get("/v1/agents?limit=1000")
    names = [a["name"] for a in listed.json()["data"]]
    assert names.count("dup-agent") == 1
