"""Tests for binding a session to one pipeline flow instance.

A session that drifts between pipelines would carry one pipeline's gate
progress into another's work, so the binding is written once and thereafter
defended rather than overwritten.
"""

from omnigent.policies.pipely.gates import (
    FLOW_KIND_LABEL,
    FLOW_PIPELINE_LABEL,
    GATE_LABEL,
    bind_flow,
    require_flow_gate,
)

PIPELINE = "orders_daily"
KIND_DELIVERY = "delivery"
KIND_OPERATION = "operation"
G4 = "g4_passed"


def _tool_call(labels: dict[str, str], *, pipeline: str = PIPELINE) -> dict[str, object]:
    """Build a V0 ``tool_call`` event naming *pipeline* in its arguments."""
    return {
        "type": "tool_call",
        "data": {
            "name": "pipely_quality_gate",
            "arguments": {"pipeline": pipeline, "kind": KIND_DELIVERY},
        },
        "context": {"labels": labels},
    }


def test_the_first_tool_call_records_the_pipeline_and_kind() -> None:
    """The flow instance is pinned on first contact, not inferred later."""
    decision = bind_flow()(_tool_call(labels={}), {})

    assert decision["set_labels"] == {
        FLOW_PIPELINE_LABEL: PIPELINE,
        FLOW_KIND_LABEL: KIND_DELIVERY,
    }


def test_a_second_pipeline_in_a_bound_session_is_refused_not_absorbed() -> None:
    """Overwriting would carry one pipeline's gate progress onto another's work."""
    bound = {FLOW_PIPELINE_LABEL: PIPELINE, FLOW_KIND_LABEL: KIND_DELIVERY}

    decision = bind_flow()(_tool_call(bound, pipeline="returns_hourly"), {})

    assert decision["result"] == "DENY"
    assert "set_labels" not in decision


def test_an_operation_flow_is_judged_on_its_own_gate_only() -> None:
    """Operations enter at release; the development gates are not their path.

    Requiring G1-G3 of an operator would make the spec's separate entry point
    unreachable without replaying work that was never theirs.
    """
    decision = require_flow_gate(minimum=G4)(
        _tool_call(
            {FLOW_KIND_LABEL: KIND_OPERATION, GATE_LABEL: G4},
            pipeline=PIPELINE,
        ),
        {},
    )

    assert decision["result"] == "ALLOW"
