"""Tests for the Lite-AI per-provider harness wraps (minimax / deepseek).

These are thin copies of the ``openai-agents`` wrap that reuse
:class:`OpenAIAgentsSDKExecutor` but read their OWN credential slot so two
OpenAI-compatible providers never compete for the shared ``OPENAI_*`` env in one
sandbox. Each new provider harness must be registered in SIX places (see
``docs/superpowers/plans/2026-07-07-model-providers/PROBE.md``); these tests lock
all six down so a half-wired provider fails loud in CI, not at a live turn.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from omnigent.host.connect import HARNESS_CREDENTIAL_ENV_VARS
from omnigent.inner import deepseek_harness, minimax_harness
from omnigent.model_override import _SDK_MODEL_OVERRIDE_HARNESSES
from omnigent.runner.app import _HARNESS_MODEL_ENV_KEY
from omnigent.runtime.harnesses import _HARNESS_MODULES
from omnigent.spec._omnigent_compat import OMNIGENT_HARNESSES

# (harness key, module, api_env, base_env, model_env, default_base, default_model)
_PROVIDERS = [
    (
        "minimax",
        minimax_harness,
        "MINIMAX_API_KEY",
        "MINIMAX_BASE_URL",
        "HARNESS_MINIMAX_MODEL",
        "https://api.minimaxi.com/v1",
        "MiniMax-Text-01",
    ),
    (
        "deepseek",
        deepseek_harness,
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "HARNESS_DEEPSEEK_MODEL",
        "https://api.deepseek.com",
        "deepseek-chat",
    ),
]


@pytest.mark.parametrize("harness,module,api_env,base_env,model_env,dbase,dmodel", _PROVIDERS)
def test_registered_in_all_six_touch_points(
    harness, module, api_env, base_env, model_env, dbase, dmodel
) -> None:
    # 1) harness dispatch registry
    assert _HARNESS_MODULES.get(harness) == f"omnigent.inner.{harness}_harness"
    # 3) model-override allow-set
    assert harness in _SDK_MODEL_OVERRIDE_HARNESSES
    # 4) model -> spawn-env key
    assert _HARNESS_MODEL_ENV_KEY.get(harness) == model_env
    # 5) agent-spec harness validation allow-set
    assert harness in OMNIGENT_HARNESSES
    # 6) host->runner credential forward allow-set (both key + base url)
    assert api_env in HARNESS_CREDENTIAL_ENV_VARS
    assert base_env in HARNESS_CREDENTIAL_ENV_VARS


@pytest.mark.parametrize("harness,module,api_env,base_env,model_env,dbase,dmodel", _PROVIDERS)
def test_create_app_exposes_harness_routes(
    harness, module, api_env, base_env, model_env, dbase, dmodel
) -> None:
    app = module.create_app()
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]
    assert "/health" in paths
    assert "/v1/sessions/{conversation_id}/events" in paths


@pytest.mark.parametrize("harness,module,api_env,base_env,model_env,dbase,dmodel", _PROVIDERS)
def test_factory_reads_own_slot(
    harness, module, api_env, base_env, model_env, dbase, dmodel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(api_env, "sk-provider-key")
    monkeypatch.setenv(base_env, "https://example.test/v1")
    monkeypatch.setenv(model_env, "some-model-7b")

    captured: dict[str, Any] = {}

    def _fake_init(self: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    with patch(
        "omnigent.inner.openai_agents_sdk_executor.OpenAIAgentsSDKExecutor.__init__",
        _fake_init,
    ):
        getattr(module, f"_build_{harness}_executor")()

    assert captured["api_key"] == "sk-provider-key"
    assert captured["base_url_override"] == "https://example.test/v1"
    assert captured["model"] == "some-model-7b"
    # OpenAI-compatible providers speak chat/completions.
    assert captured["use_responses"] is False


@pytest.mark.parametrize("harness,module,api_env,base_env,model_env,dbase,dmodel", _PROVIDERS)
def test_factory_defaults_when_slot_absent(
    harness, module, api_env, base_env, model_env, dbase, dmodel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env in (api_env, base_env, model_env):
        monkeypatch.delenv(env, raising=False)

    captured: dict[str, Any] = {}

    def _fake_init(self: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    with patch(
        "omnigent.inner.openai_agents_sdk_executor.OpenAIAgentsSDKExecutor.__init__",
        _fake_init,
    ):
        getattr(module, f"_build_{harness}_executor")()

    # No api key anywhere -> None (executor falls through to its own resolution).
    assert captured["api_key"] is None
    # base_url / model fall back to the provider default (never api.openai.com).
    assert captured["base_url_override"] == dbase
    assert captured["model"] == dmodel


def test_claude_subscription_token_not_forwarded() -> None:
    """Claude subscription token is fully removed — never forwarded host->runner.

    owner decision (2026-07-07): claude uses enterprise ANTHROPIC_API_KEY only;
    the subscription token must not be used nor baked into the image.
    """
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in HARNESS_CREDENTIAL_ENV_VARS
