"""Preflight gate for pipely.

The runtime has no agent-startup hook, so the only place a precondition check
can be made binding is a policy on the first tool call. An absent result must
therefore read as *not verified* — treating it as *nothing to enforce* would
let every unconfigured deployment straight through.

Carries FR-060 (report every gap in one pass), FR-076 (the bootstrap bot
is provisioned by hand), and FR-091 (the first tool call is the only place
a precondition check can be made binding — the runtime has no startup hook).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

_Json: TypeAlias = dict[str, Any]  # type: ignore[explicit-any]

_ALLOW: _Json = {"result": "ALLOW"}

PREFLIGHT_LABEL = "pipely.preflight.status"
PREFLIGHT_MISSING_LABEL = "pipely.preflight.missing"
PASSED = "passed"
FAILED = "failed"
BOOTSTRAP_BOT = "om_bootstrap_reader"
PROVISION_BY_HAND = "provision_by_hand"


def assess(
    *,
    credentials: dict[str, bool],
    shared_with: list[str],
    approve_granted: list[str],
) -> _Json:
    """Judge the observed preconditions.

    :param credentials: Credential name to whether it was found.
    :param shared_with: Users the working session is shared with.
    :param approve_granted: Users delegated approval authority.
    :returns: Result with ``passed`` and ``missing``.
    """
    missing = [f"credential:{name}" for name, found in credentials.items() if not found]
    # Two distinct mis-configurations: an unshared session hides the item from
    # the gatekeeper's inbox, while a shared-but-undelegated one shows it and
    # refuses the click. They are diagnosed differently, so they are reported
    # apart rather than folded into one "cannot approve".
    if not shared_with:
        missing.append("session:not_shared")
    elif not approve_granted:
        missing.append("session:no_approve_grant")
    # The bootstrap bot cannot be self-served: creating it *is* the privilege it
    # exists to bootstrap. Absent, it is handed back to a human, never created.
    remediation = {
        f"credential:{BOOTSTRAP_BOT}": PROVISION_BY_HAND,
    }
    # The gate denies later calls from a label, so the reason must be on the
    # session too — otherwise the operator sees a refusal with no way back to
    # which item was absent.
    labels = {PREFLIGHT_LABEL: PASSED if not missing else FAILED}
    if missing:
        labels[PREFLIGHT_MISSING_LABEL] = ",".join(sorted(missing))
    return {
        "passed": not missing,
        "missing": missing,
        "labels": labels,
        "remediation": {k: v for k, v in remediation.items() if k in missing},
    }


def require_preflight(
    *,
    deny_reason: str = "Preconditions have not been verified for this session.",
    probe: Callable[[], _Json] | None = None,
) -> Callable[[_Json, _Json], _Json]:
    """Factory: refuse tool calls until preconditions have been verified.

    :param deny_reason: Reason text surfaced on a DENY decision.
    :param probe: Collects the observed preconditions. Injected so the gate
        stays deterministic in tests.
    :returns: An evaluator ``fn(event, config)`` returning a V0 decision.
    """

    def _evaluate(event: _Json, config: _Json) -> _Json:  # noqa: ARG001
        """Judge one tool call against the recorded preflight result.

        :param event: V0 ``tool_call`` event.
        :param config: Runtime config dict (unused).
        :returns: ALLOW / DENY decision dict.
        """
        labels = event.get("context", {}).get("labels") or {}
        # A recorded result short-circuits: probing again on every tool call
        # would turn a one-time check into per-call overhead, and could flip
        # the verdict mid-session on a transient blip.
        if labels.get(PREFLIGHT_LABEL) == PASSED:
            return _ALLOW
        if probe is not None:
            probe()
        return {"result": "DENY", "reason": deny_reason}

    return _evaluate
