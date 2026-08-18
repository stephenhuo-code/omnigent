"""Tests for the pipely phase-gate policy.

A gate is an ordered scale, so the decisive tests are the two sides of the
threshold: a scale tested on one side only pins nothing, because "at the gate"
and "past the gate" pass the same single test.
"""

from omnigent.policies.pipely.gates import (
    GATE_LABEL,
    QUALITY_LABEL,
    require_flow_gate,
    require_gate,
    require_release,
)

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


def _switch_call(gate: str | None, quality: str | None) -> dict[str, object]:
    """Build a tool call for the pointer switch at *gate* with *quality*."""
    labels: dict[str, str] = {}
    if gate is not None:
        labels[GATE_LABEL] = gate
    if quality is not None:
        labels[QUALITY_LABEL] = quality
    return {
        "type": "tool_call",
        "data": {"name": "switch_live_pointer", "arguments": {}},
        "context": {"labels": labels},
    }


def test_the_switch_needs_both_release_readiness_and_this_runs_quality() -> None:
    """Two different questions, and passing one does not answer the other.

    The gate says this VERSION may ship; the quality verdict says THIS RUN's
    output is usable. A rerun re-decides the second and leaves the first alone,
    so neither alone may open the switch.
    """
    evaluate = require_release()

    ready_but_bad = evaluate(_switch_call(gate=G3, quality="failed"), {})
    good_but_not_ready = evaluate(_switch_call(gate=G2, quality="passed"), {})
    both = evaluate(_switch_call(gate=G3, quality="passed"), {})

    assert ready_but_bad["result"] == "DENY"
    assert good_but_not_ready["result"] == "DENY"
    assert both["result"] == "ALLOW"


def _dispatch(phase: str, gate: str | None, quality: str | None) -> dict[str, object]:
    """Build a sub-agent dispatch for *phase* with the given session state."""
    labels: dict[str, str] = {}
    if gate is not None:
        labels[GATE_LABEL] = gate
    if quality is not None:
        labels[QUALITY_LABEL] = quality
    return {
        "type": "tool_call",
        "data": {"name": "sys_session_send", "arguments": {"phase": phase}},
        "context": {"labels": labels},
    }


def test_only_the_switch_dispatch_is_held_to_the_release_conditions() -> None:
    """The orchestrator dispatches every phase through one tool, so the guard
    has to tell them apart — by the argument it was called with, never by the
    wording of the task. Gating every dispatch alike would stop phase 1 dead.
    """
    evaluate = require_release(applies_to_phase="switch")

    early_work = evaluate(_dispatch("plan", gate=None, quality=None), {})
    premature_switch = evaluate(_dispatch("switch", gate=G3, quality=None), {})
    ready_switch = evaluate(_dispatch("switch", gate=G3, quality="passed"), {})

    assert early_work["result"] == "ALLOW"
    assert premature_switch["result"] == "DENY"
    assert ready_switch["result"] == "ALLOW"


def test_only_the_release_dispatch_is_held_to_the_release_gate() -> None:
    """Release work must not be dispatched before a human merged the change
    request. Earlier phases are how the flow reaches that point at all, so
    gating them on the same value would deadlock the whole thing.
    """
    evaluate = require_flow_gate(minimum=G3, applies_to_phase="release")

    planning = evaluate(
        {
            "type": "tool_call",
            "data": {"name": "sys_session_send", "arguments": {"phase": "plan"}},
            "context": {"labels": {}},
        },
        {},
    )
    premature_release = evaluate(
        {
            "type": "tool_call",
            "data": {"name": "sys_session_send", "arguments": {"phase": "release"}},
            "context": {"labels": {GATE_LABEL: G2}},
        },
        {},
    )
    ready_release = evaluate(
        {
            "type": "tool_call",
            "data": {"name": "sys_session_send", "arguments": {"phase": "release"}},
            "context": {"labels": {GATE_LABEL: G3}},
        },
        {},
    )

    assert planning["result"] == "ALLOW"
    assert premature_release["result"] == "DENY"
    assert ready_release["result"] == "ALLOW"
