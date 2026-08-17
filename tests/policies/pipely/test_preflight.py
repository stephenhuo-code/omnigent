"""Tests for the pipely preflight gate policy.

The runtime has no agent-startup hook, so the only place a precondition check
can be made binding is a policy on the first tool call. That makes "no check
recorded yet" the decisive case: it must read as *not verified*, never as
*nothing to enforce*.
"""

from omnigent.policies.pipely.preflight import require_preflight

PREFLIGHT_LABEL = "pipely.preflight.status"


def _tool_call(labels: dict[str, str]) -> dict[str, object]:
    """Build a V0 ``tool_call`` event carrying *labels* as session state."""
    return {
        "type": "tool_call",
        "data": {"name": "sys_os_shell", "arguments": {}},
        "context": {"labels": labels},
    }


def test_tool_call_is_denied_when_no_preflight_result_is_recorded() -> None:
    """An absent preflight label denies the call rather than waving it through."""
    decision = require_preflight()(_tool_call(labels={}), {})

    assert decision["result"] == "DENY"


def test_tool_call_is_allowed_once_preflight_is_recorded_as_passed() -> None:
    """A recorded pass lets the call through."""
    decision = require_preflight()(_tool_call(labels={PREFLIGHT_LABEL: "passed"}), {})

    assert decision["result"] == "ALLOW"
