"""Phase-gate policy for pipely.

Work moves through four ordered gates. A tool call is judged against the gate
the session has reached, so the gate is a scale rather than a flag.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypeAlias

_Json: TypeAlias = dict[str, Any]  # type: ignore[explicit-any]

GATE_LABEL = "pipely.gate"

#: The gates in order. Rank comes from this sequence, never from comparing the
#: label strings — lexicographic order would put "g10_passed" below "g2_passed".
GATE_ORDER = ("g1_passed", "g2_passed", "g3_passed", "g4_passed")


def _rank(gate: str | None) -> int:
    """Return *gate*'s position on the scale, or ``-1`` when it is not a gate.

    :param gate: A gate name, or ``None`` when the session carries no gate.
    :returns: Index into :data:`GATE_ORDER`, or ``-1``.
    """
    try:
        return GATE_ORDER.index(gate)  # type: ignore[arg-type]
    except ValueError:
        return -1


FLOW_PIPELINE_LABEL = "pipely.flow.pipeline"
FLOW_KIND_LABEL = "pipely.flow.kind"

#: A delivery flow climbs g1 to g4; an operation flow enters at release.
KIND_DELIVERY = "delivery"
KIND_OPERATION = "operation"

#: The gate an operation flow is judged on, whatever the caller asked for.
RELEASE_GATE = "g4_passed"


def bind_flow() -> Callable[[_Json, _Json], _Json]:
    """Factory: pin the session to one pipeline flow instance.

    :returns: An evaluator ``fn(event, config)`` returning a V0 decision.
    """

    def _evaluate(event: _Json, config: _Json) -> _Json:  # noqa: ARG001
        """Bind the session on first contact, and defend the binding after.

        :param event: V0 ``tool_call`` event.
        :param config: Runtime config dict (unused).
        :returns: ALLOW / DENY decision dict.
        """
        arguments = event.get("data", {}).get("arguments") or {}
        pipeline = arguments.get("pipeline")
        kind = arguments.get("kind")
        if pipeline is None:
            return {"result": "ALLOW"}
        bound = (event.get("context", {}).get("labels") or {}).get(FLOW_PIPELINE_LABEL)
        if bound is not None and bound != pipeline:
            # Overwriting would carry this session's gate progress onto a
            # different pipeline's work. A second pipeline needs a second session.
            return {
                "result": "DENY",
                "reason": (
                    f"This session is bound to pipeline {bound}; it cannot also act on {pipeline}."
                ),
            }
        return {
            "result": "ALLOW",
            "set_labels": {
                FLOW_PIPELINE_LABEL: pipeline,
                FLOW_KIND_LABEL: kind,
            },
        }

    return _evaluate


def require_flow_gate(*, minimum: str) -> Callable[[_Json, _Json], _Json]:
    """Factory: gate a call according to the flow instance's own path.

    Development work climbs G1 to G4; an operation enters at release and is
    judged on that gate alone.

    :param minimum: The gate a call requires on the development path.
    :returns: An evaluator ``fn(event, config)`` returning a V0 decision.
    """

    def _evaluate(event: _Json, config: _Json) -> _Json:  # noqa: ARG001
        """Judge one tool call against the gate its flow kind requires.

        :param event: V0 ``tool_call`` event.
        :param config: Runtime config dict (unused).
        :returns: ALLOW / DENY decision dict.
        """
        labels = event.get("context", {}).get("labels") or {}
        reached = labels.get(GATE_LABEL)
        # An operation enters at release: it is judged on the release gate
        # alone, never on development gates it was never meant to climb.
        required = RELEASE_GATE if labels.get(FLOW_KIND_LABEL) == KIND_OPERATION else minimum
        if _rank(reached) >= _rank(required):
            return {"result": "ALLOW"}
        return {
            "result": "DENY",
            "reason": (
                f"This session is at gate {reached or 'none'}; the call requires gate {required}."
            ),
        }

    return _evaluate


def _verdict(data: Any) -> _Json | None:
    """Return the tool's verdict dict from *data*, whatever form it arrived in.

    The runner passes a raw output string; a hand-built event may carry the
    dict directly, or wrap it under ``result``.

    :param data: The event's ``data`` field.
    :returns: The verdict dict, or ``None`` when it cannot be recovered.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            return None
    if not isinstance(data, dict):
        return None
    inner = data.get("result")
    return inner if isinstance(inner, dict) else data


def advance_on_result(*, tool: str, grants: str) -> Callable[[_Json, _Json], _Json]:
    """Factory: move the gate forward on *tool*'s real return value.

    Bound to the ``tool_result`` phase, so the decision is made from what the
    tool actually returned rather than from anything the model asserts.

    :param tool: The tool whose result can move the gate.
    :param grants: The gate a passing result grants.
    :returns: An evaluator ``fn(event, config)`` returning a V0 decision.
    """

    def _evaluate(event: _Json, config: _Json) -> _Json:  # noqa: ARG001
        """Read one tool result and decide whether the gate moves.

        :param event: V0 ``tool_result`` event.
        :param config: Runtime config dict (unused).
        :returns: ALLOW decision, with ``set_labels`` when the gate moves.
        """
        # The runner evaluates this phase with ``content`` set to the tool's raw
        # output STRING (omnigent/runner/policy.py), not to its dict. Reading it
        # as a dict raised, the engine turned that into DENY, and the gate could
        # never advance — while the hand-built events in the unit tests passed.
        if str(event.get("target") or "") not in ("", tool):
            return {"result": "ALLOW"}
        result = _verdict(event.get("data"))
        if not isinstance(result, dict) or "passed" not in result:
            # No verdict at all is a broken check, not a quiet non-pass: left
            # unflagged, a tool that stopped reporting would stall the gate
            # forever with nobody able to see why.
            return {
                "result": "ALLOW",
                "malformed": True,
                "reason": f"{tool} returned no 'passed' verdict.",
            }
        labels = event.get("context", {}).get("labels") or {}
        # A ratchet: re-running an earlier check must not undo later progress.
        moves_forward = _rank(grants) > _rank(labels.get(GATE_LABEL))
        if result["passed"] is True and moves_forward:
            return {"result": "ALLOW", "set_labels": {GATE_LABEL: grants}}
        return {"result": "ALLOW"}

    return _evaluate


def require_gate(*, minimum: str) -> Callable[[_Json, _Json], _Json]:
    """Factory: refuse tool calls until the session has reached *minimum*.

    :param minimum: The gate a call requires, e.g. ``"G2"``.
    :returns: An evaluator ``fn(event, config)`` returning a V0 decision.
    """

    def _evaluate(event: _Json, config: _Json) -> _Json:  # noqa: ARG001
        """Judge one tool call against the gate the session has reached.

        :param event: V0 ``tool_call`` event.
        :param config: Runtime config dict (unused).
        :returns: ALLOW / DENY decision dict.
        """
        labels = event.get("context", {}).get("labels") or {}
        reached = labels.get(GATE_LABEL)
        if _rank(reached) >= _rank(minimum):
            return {"result": "ALLOW"}
        return {
            "result": "DENY",
            "reason": (
                f"This session is at gate {reached or 'none'}; the call requires gate {minimum}."
            ),
        }

    return _evaluate
