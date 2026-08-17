"""Preflight gate for pipely.

The runtime has no agent-startup hook, so the only place a precondition check
can be made binding is a policy on the first tool call. An absent result must
therefore read as *not verified* — treating it as *nothing to enforce* would
let every unconfigured deployment straight through.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

_Json: TypeAlias = dict[str, Any]  # type: ignore[explicit-any]

_ALLOW: _Json = {"result": "ALLOW"}

PREFLIGHT_LABEL = "pipely.preflight.status"
PASSED = "passed"


def require_preflight(
    *,
    deny_reason: str = "Preconditions have not been verified for this session.",
) -> Callable[[_Json, _Json], _Json]:
    """Factory: refuse tool calls until preconditions have been verified.

    :param deny_reason: Reason text surfaced on a DENY decision.
    :returns: An evaluator ``fn(event, config)`` returning a V0 decision.
    """

    def _evaluate(event: _Json, config: _Json) -> _Json:  # noqa: ARG001
        """Judge one tool call against the recorded preflight result.

        :param event: V0 ``tool_call`` event.
        :param config: Runtime config dict (unused).
        :returns: ALLOW / DENY decision dict.
        """
        labels = event.get("context", {}).get("labels") or {}
        if labels.get(PREFLIGHT_LABEL) == PASSED:
            return _ALLOW
        return {"result": "DENY", "reason": deny_reason}

    return _evaluate
