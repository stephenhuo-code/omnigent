"""Acceptance behaviors for pipely, composed through the real policy engine.

The unit tests in this directory call each policy's evaluator directly with an
event dict built by hand. That proves the logic and nothing about the wiring: if
the shape the runtime actually passes differs, every unit test stays green while
the gate never moves.

These tests close that gap. They build a real :class:`PolicyEngine`, resolve the
policies from their dotted paths exactly as the agent definitions declare them,
and feed it the real return value of the real tool.

Host note: ``tests/integration/`` — the host the test list originally named — is
excluded from the default pytest run (``--ignore=tests/integration`` in
pyproject) and gated behind ``--integration`` plus a harness CLI. An acceptance
test nobody runs is not an acceptance test, so the composable behaviors live
here, in the default suite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from omnigent.entities import ConversationItem, PagedList
from omnigent.policies.function import resolve_function_policy
from omnigent.policies.pipely.gates import GATE_LABEL
from omnigent.runtime.policies.engine import PolicyEngine
from omnigent.spec.types import FunctionPolicySpec, FunctionRef, Phase
from omnigent.tools.pipely.verify_governance import verify

CONV_ID = "conv_pipely_flow"
VERIFY_TOOL = "verify_governance"
G2 = "g2_passed"


@dataclass
class _Store:
    """Minimal conversation store recording what the engine persists."""

    label_writes: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def set_labels(self, conversation_id: str, labels: dict[str, str]) -> None:
        """Record a label write."""
        self.label_writes.append((conversation_id, dict(labels)))

    def set_session_state(self, conversation_id: str, state: dict[str, Any]) -> None:
        """Record a session-state write."""
        del conversation_id, state

    def list_items(
        self,
        conversation_id: str,
        *,
        limit: int = 20,
        order: str = "asc",
        **kwargs: Any,
    ) -> PagedList[ConversationItem]:
        """Return an empty page — the engine only needs this for trajectory."""
        del conversation_id, limit, order, kwargs
        return PagedList(data=[], has_more=False)


def _engine(*, labels: dict[str, str] | None = None) -> PolicyEngine:
    """Build an engine carrying the G2 advance policy the orchestrator declares."""
    spec = FunctionPolicySpec(
        name="advance_g2_on_verification",
        on=None,
        function=FunctionRef(
            path="omnigent.policies.pipely.gates.advance_on_result",
            arguments={"tool": VERIFY_TOOL, "grants": G2},
        ),
    )
    return PolicyEngine(
        policies=[resolve_function_policy(spec)],
        label_defs={},
        ask_timeout=30,
        conversation_id=CONV_ID,
        initial_labels=dict(labels or {}),
        conversation_store=_Store(),  # type: ignore[arg-type]
    )


def _tool_result_ctx(report: dict[str, Any]) -> Any:
    """Build the context the runner passes on TOOL_RESULT.

    ``content`` is the tool's raw output STRING, not its dict — the runner
    serialises before the policy sees it (omnigent/runner/policy.py).
    """
    from omnigent.policies.types import EvaluationContext

    return EvaluationContext(
        phase=Phase.TOOL_RESULT,
        content=json.dumps(report),
        tool_name=VERIFY_TOOL,
    )


@pytest.mark.asyncio
async def test_an_unmet_governance_assertion_leaves_the_g2_gate_shut() -> None:
    """The gate reads the tool's real output, so an unmet assertion holds it shut.

    Driven through the real engine rather than by calling the evaluator with a
    hand-made event: the event the runtime builds is what decides whether this
    mechanism exists at all.
    """
    engine = _engine()
    report = verify(
        assertions=[
            {"name": "domain_exists", "expected": "present", "actual": "present"},
            {"name": "owner_set", "expected": "data_platform", "actual": "unassigned"},
        ],
    )

    await engine.evaluate(_tool_result_ctx(report))

    assert report["passed"] is False
    assert report["missing_steps"], "an unmet assertion must say what to do"
    assert engine.labels.get(GATE_LABEL) is None


@pytest.mark.asyncio
async def test_a_fully_met_verification_opens_the_g2_gate() -> None:
    """The other side of the same mechanism, and the one that gives it meaning.

    Without this, a policy that opened the gate for nothing — or that crashed
    on every call — would pass the test above while the flow could never
    advance past G2 at all.
    """
    engine = _engine()
    report = verify(
        assertions=[
            {"name": "domain_exists", "expected": "present", "actual": "present"},
            {"name": "owner_set", "expected": "data_platform", "actual": "data_platform"},
        ],
    )

    decision = await engine.evaluate(_tool_result_ctx(report))

    assert report["passed"] is True
    assert decision.action.value == "allow"
    assert engine.labels.get(GATE_LABEL) == G2
