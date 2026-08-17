"""Phase-gate policy for pipely.

Work moves through four ordered gates. A tool call is judged against the gate
the session has reached, so the gate is a scale rather than a flag.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

_Json: TypeAlias = dict[str, Any]  # type: ignore[explicit-any]

GATE_LABEL = "pipely.gate.reached"

#: The gates in order. Rank comes from this sequence, never from comparing the
#: label strings — lexicographic order would put "G10" below "G2".
GATE_ORDER = ("G1", "G2", "G3", "G4")


def _rank(gate: str | None) -> int:
    """Return *gate*'s position on the scale, or ``-1`` when it is not a gate.

    :param gate: A gate name, or ``None`` when the session carries no gate.
    :returns: Index into :data:`GATE_ORDER`, or ``-1``.
    """
    try:
        return GATE_ORDER.index(gate)  # type: ignore[arg-type]
    except ValueError:
        return -1


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
