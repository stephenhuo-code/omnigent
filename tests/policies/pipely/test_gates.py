"""Tests for the pipely phase-gate policy.

A gate is an ordered scale, so the decisive tests are the two sides of the
threshold: a scale tested on one side only pins nothing, because "at the gate"
and "past the gate" pass the same single test.
"""

from omnigent.policies.pipely.gates import GATE_LABEL, require_gate

G1 = "g1_passed"
G2 = "g2_passed"
G3 = "g3_passed"


def _tool_call(gate: str | None) -> dict[str, object]:
    """Build a V0 ``tool_call`` event whose session sits at *gate*."""
    labels = {} if gate is None else {GATE_LABEL: gate}
    return {
        "type": "tool_call",
        "data": {"name": "sys_os_shell", "arguments": {}},
        "context": {"labels": labels},
    }


def test_a_session_exactly_at_the_required_gate_is_allowed() -> None:
    """The lower boundary is inclusive: reaching the gate is enough to pass it."""
    decision = require_gate(minimum=G2)(_tool_call(G2), {})

    assert decision["result"] == "ALLOW"


def test_a_session_one_gate_below_the_requirement_is_denied() -> None:
    """The other side of the same threshold: not yet there is not good enough."""
    decision = require_gate(minimum=G2)(_tool_call(G1), {})

    assert decision["result"] == "DENY"


def test_a_session_past_the_required_gate_is_still_allowed() -> None:
    """Later work does not lose access to what an earlier gate opened."""
    decision = require_gate(minimum=G2)(_tool_call(G3), {})

    assert decision["result"] == "ALLOW"


def test_a_session_carrying_no_gate_at_all_is_denied() -> None:
    """An absent gate reads as *not yet passed*, never as *nothing to enforce*."""
    decision = require_gate(minimum=G2)(_tool_call(None), {})

    assert decision["result"] == "DENY"


def test_a_denial_names_both_where_the_session_is_and_where_it_must_be() -> None:
    """Naming only the requirement leaves the reader to guess the shortfall."""
    decision = require_gate(minimum=G3)(_tool_call(G1), {})

    assert G1 in decision["reason"]
    assert G3 in decision["reason"]
