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


def assess(
    *,
    credentials: dict[str, bool],
    shared_with: list[str],
    approve_granted: list[str],
) -> _Json:
    """Judge the observed preconditions.

    :param credentials: Credential name to whether it was found.
    :param shared_with: Users the working session is shared with.
    :param approve_granted: Users delegated approval authority.
    :returns: Result with ``passed`` and ``missing``.
    """
    missing = [f"credential:{name}" for name, found in credentials.items() if not found]
    # Two distinct mis-configurations: an unshared session hides the item from
    # the gatekeeper's inbox, while a shared-but-undelegated one shows it and
    # refuses the click. They are diagnosed differently, so they are reported
    # apart rather than folded into one "cannot approve".
    if not shared_with:
        missing.append("session:not_shared")
    elif not approve_granted:
        missing.append("session:no_approve_grant")
    return {"passed": not missing, "missing": missing}


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
