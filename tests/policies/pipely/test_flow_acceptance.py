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
from omnigent.policies.pipely.preflight import assess
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


def _read_only_engine(bot: str) -> PolicyEngine:
    """Build an engine carrying the read-only policy *bot*'s agent declares."""
    spec = FunctionPolicySpec(
        name="read_only_catalog",
        on=None,
        function=FunctionRef(
            path="omnigent.policies.pipely.identity.require_read_only",
            arguments={"bot": bot},
        ),
    )
    return PolicyEngine(
        policies=[resolve_function_policy(spec)],
        label_defs={},
        ask_timeout=30,
        conversation_id=CONV_ID,
        initial_labels={},
        conversation_store=_Store(),  # type: ignore[arg-type]
    )


def _tool_call_ctx(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Build the context the runner passes on TOOL_CALL."""
    from omnigent.policies.types import EvaluationContext

    return EvaluationContext(
        phase=Phase.TOOL_CALL,
        content={"name": tool_name, "arguments": arguments or {}},
        tool_name=tool_name,
    )


@pytest.mark.asyncio
async def test_the_governance_agent_cannot_write_through_the_real_engine() -> None:
    """Read-only holds when the runtime dispatches it, not just when called directly.

    The same class of gap that broke the G2 gate applies here: the policy could
    be reading a field the runner never populates, and every unit test would
    still be green.
    """
    engine = _read_only_engine("governance")

    decision = await engine.evaluate(_tool_call_ctx("update_table"))

    assert decision.action.value == "deny"


@pytest.mark.asyncio
async def test_the_consumer_agent_cannot_write_but_can_still_search() -> None:
    """Verification must not be able to change what it verifies — and must
    still be able to verify. Both halves, because a policy that denied
    everything would satisfy the first while making the agent pointless.
    """
    engine = _read_only_engine("consumer")

    refused = await engine.evaluate(_tool_call_ctx("create_table"))
    allowed = await engine.evaluate(_tool_call_ctx("search_metadata"))

    assert refused.action.value == "deny"
    assert allowed.action.value == "allow"


@pytest.mark.asyncio
async def test_the_scheduler_credential_cannot_govern_only_run() -> None:
    """Airflow ships inside OpenMetadata, so one credential looks like it covers
    both. Running a job and governing one are different authorities, and the
    refusal has to happen at the call, not in a rule someone remembers.
    """
    spec = FunctionPolicySpec(
        name="no_platform_admin_via_scheduler",
        on=None,
        function=FunctionRef(
            path="omnigent.policies.pipely.identity.deny_platform_operations",
            arguments={"credential": "om_scheduler"},
        ),
    )
    engine = PolicyEngine(
        policies=[resolve_function_policy(spec)],
        label_defs={},
        ask_timeout=30,
        conversation_id=CONV_ID,
        initial_labels={},
        conversation_store=_Store(),  # type: ignore[arg-type]
    )

    governing = await engine.evaluate(_tool_call_ctx("create_domain"))
    running = await engine.evaluate(_tool_call_ctx("trigger_dag_run"))

    assert governing.action.value == "deny"
    assert running.action.value == "allow"


@pytest.mark.asyncio
async def test_no_task_is_dispatched_until_preconditions_are_verified() -> None:
    """The runtime has no agent-startup hook, so the FIRST tool call is the only
    place this can be made binding. An unverified session must be refused there
    — half a pipeline built on a missing credential is worse than none.
    """
    spec = FunctionPolicySpec(
        name="preflight",
        on=None,
        function=FunctionRef(
            path="omnigent.policies.pipely.preflight.require_preflight",
            arguments={},
        ),
    )
    engine = PolicyEngine(
        policies=[resolve_function_policy(spec)],
        label_defs={},
        ask_timeout=30,
        conversation_id=CONV_ID,
        initial_labels={},
        conversation_store=_Store(),  # type: ignore[arg-type]
    )

    decision = await engine.evaluate(_tool_call_ctx("search_metadata"))

    assert decision.action.value == "deny"


def test_a_partly_configured_deployment_is_told_every_gap_at_once() -> None:
    """One round trip, not one gap per round trip.

    An operator who fixes the first missing credential, re-runs, and meets the
    second has learned the same lesson twice at their own expense.
    """
    result = assess(
        credentials={"model_access": True, "code_hosting": False, "om_reader": False},
        shared_with=[],
        approve_granted=[],
    )

    assert sorted(result["missing"]) == [
        "credential:code_hosting",
        "credential:om_reader",
        "session:not_shared",
    ]
