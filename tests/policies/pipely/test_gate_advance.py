"""Tests for advancing the pipely gate from a tool's real return value.

This is the closed loop that makes the gates mean something: the label is
written by a ``tool_result`` policy reading what the tool actually returned,
never by the model saying it verified something. A model claim that moves a
gate is the failure mode this whole mechanism exists to prevent.
"""

from omnigent.policies.pipely.gates import GATE_LABEL, advance_on_result

G1 = "g1_passed"
G2 = "g2_passed"
G3 = "g3_passed"


def _tool_result(payload: object, *, reached: str = G1) -> dict[str, object]:
    """Build a V0 ``tool_result`` event carrying *payload* as the return value."""
    return {
        "type": "tool_result",
        "data": {"name": "pipely_quality_gate", "result": payload},
        "context": {"labels": {GATE_LABEL: reached}},
    }


def test_a_tool_reporting_a_pass_advances_the_gate() -> None:
    """The gate moves on evidence: the tool's own ``passed`` flag."""
    decision = advance_on_result(tool="pipely_quality_gate", grants=G2)(
        _tool_result({"passed": True}), {}
    )

    assert decision["set_labels"] == {GATE_LABEL: G2}


def test_a_tool_reporting_a_failure_leaves_the_gate_where_it_was() -> None:
    """A failed check must not advance anything, however the call is narrated."""
    decision = advance_on_result(tool="pipely_quality_gate", grants=G2)(
        _tool_result({"passed": False}), {}
    )

    assert "set_labels" not in decision


def test_a_model_claiming_it_verified_something_moves_no_gate() -> None:
    """The gate reads tool results. A message asserting success is not one."""
    claim = {
        "type": "llm_response",
        "data": {"content": "I ran the quality gate and it passed."},
        "context": {"labels": {GATE_LABEL: G1}},
    }

    decision = advance_on_result(tool="pipely_quality_gate", grants=G2)(claim, {})

    assert "set_labels" not in decision


def test_a_result_with_no_verdict_field_is_flagged_rather_than_ignored() -> None:
    """A malformed result is a broken check, not a quiet non-pass.

    Silently treating it as "did not pass" hides a tool that stopped
    reporting, and the gate would then never move for a reason nobody sees.
    """
    decision = advance_on_result(tool="pipely_quality_gate", grants=G2)(
        _tool_result({"details": "ran 12 checks"}), {}
    )

    assert "set_labels" not in decision
    assert decision["malformed"] is True


def test_a_lower_gates_result_does_not_pull_the_session_back() -> None:
    """Gates are a ratchet: re-running an earlier check must not undo progress."""
    decision = advance_on_result(tool="pipely_quality_gate", grants=G2)(
        _tool_result({"passed": True}, reached=G3), {}
    )

    assert "set_labels" not in decision
