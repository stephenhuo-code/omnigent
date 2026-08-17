"""Tests for the pipely preflight gate policy.

The runtime has no agent-startup hook, so the only place a precondition check
can be made binding is a policy on the first tool call. That makes "no check
recorded yet" the decisive case: it must read as *not verified*, never as
*nothing to enforce*.
"""

from omnigent.policies.pipely.preflight import assess, require_preflight

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


def test_one_absent_credential_is_reported_as_exactly_that_one() -> None:
    """A single gap names that gap and nothing else."""
    result = assess(
        credentials={"model_access": True, "code_hosting": False},
        shared_with=["admin@example.com"],
        approve_granted=["admin@example.com"],
    )

    assert result["missing"] == ["credential:code_hosting"]


def test_several_absent_credentials_are_all_reported_at_once() -> None:
    """Every gap is listed in one pass, not just the first one found."""
    result = assess(
        credentials={"model_access": False, "code_hosting": False, "om_reader": False},
        shared_with=["admin@example.com"],
        approve_granted=["admin@example.com"],
    )

    assert sorted(result["missing"]) == [
        "credential:code_hosting",
        "credential:model_access",
        "credential:om_reader",
    ]


def test_not_shared_and_no_approve_grant_are_distinct_failures() -> None:
    """The two mis-configurations are reported apart, not as one."""
    not_shared = assess(
        credentials={},
        shared_with=[],
        approve_granted=[],
    )
    shared_without_grant = assess(
        credentials={},
        shared_with=["admin@example.com"],
        approve_granted=[],
    )

    assert not_shared["missing"] != shared_without_grant["missing"]
