"""MiniMax harness wrap — a per-provider copy of the openai-agents SDK harness.

MiniMax exposes an OpenAI-compatible chat/completions endpoint, so this wrap
reuses :class:`omnigent.inner.openai_agents_sdk_executor.OpenAIAgentsSDKExecutor`
(the *same* executor the ``openai-agents`` harness uses) but reads its OWN
credential slot so a MiniMax agent never competes with a real OpenAI / DeepSeek
agent for the shared ``OPENAI_*`` env in the same sandbox.

Resolved by the runner from
:data:`omnigent.runtime.harnesses._HARNESS_MODULES` under the key ``"minimax"``.

Credential slot (injected into the managed sandbox by Lite-AI per enterprise):

- ``MINIMAX_API_KEY``: MiniMax API key (literal). Passed explicitly to the
  executor so it wins over any ambient ``OPENAI_API_KEY``.
- ``MINIMAX_BASE_URL``: MiniMax OpenAI-compatible endpoint. Falls back to
  :data:`_DEFAULT_BASE_URL` so a missing value never routes to api.openai.com.
- ``HARNESS_MINIMAX_MODEL``: model id, set by the runner from the agent spec's
  ``model`` field (see ``runner/app.py::_HARNESS_MODEL_ENV_KEY`` and
  ``model_override._SDK_MODEL_OVERRIDE_HARNESSES`` — the harness name MUST be
  registered in both for the override to land here). Falls back to
  :data:`_DEFAULT_MODEL`.

MiniMax speaks chat/completions, so ``use_responses`` is pinned ``False`` (the
Agents SDK's default ``/responses`` wire 404s here).
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from omnigent.inner.executor import Executor
from omnigent.inner.openai_agents_sdk_executor import OpenAIAgentsSDKExecutor
from omnigent.runtime.harnesses._executor_adapter import ExecutorAdapter

_ENV_API_KEY = "MINIMAX_API_KEY"
_ENV_BASE_URL = "MINIMAX_BASE_URL"
_ENV_MODEL = "HARNESS_MINIMAX_MODEL"

_DEFAULT_BASE_URL = "https://api.minimaxi.com/v1"
_DEFAULT_MODEL = "MiniMax-Text-01"


def _build_minimax_executor() -> Executor:
    """Construct an :class:`OpenAIAgentsSDKExecutor` from the MiniMax slot."""
    return OpenAIAgentsSDKExecutor(
        api_key=os.environ.get(_ENV_API_KEY) or None,
        base_url_override=os.environ.get(_ENV_BASE_URL) or _DEFAULT_BASE_URL,
        model=os.environ.get(_ENV_MODEL) or _DEFAULT_MODEL,
        use_responses=False,
    )


def create_app() -> FastAPI:
    """Harness entry point — the runner imports this module and calls it."""
    return ExecutorAdapter(executor_factory=_build_minimax_executor).build()
