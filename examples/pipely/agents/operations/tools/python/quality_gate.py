"""Judge a released pipeline against the frozen quality contract.

Thin adapter over :mod:`omnigent.tools.pipely.quality_gate`. The gate policy
reads THIS tool's real return value to move ``pipely.gate``, so the return
shape is a hard contract, not a report format.
"""

from __future__ import annotations

from typing import Any

from omnigent_client.tools import tool

from omnigent.tools.pipely import quality_gate as _impl


@tool
def quality_gate(
    checks: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """
    Judge every gate check against the threshold frozen in the contract.

    :param checks: One entry per check, each with ``name``, ``actual``,
        ``threshold``, and ``direction`` (``"min"`` where higher is better,
        ``"max"`` where lower is). All five required checks must be present.
    :param contract: The frozen thresholds from the artifact reference. These
        override whatever ``threshold`` the caller supplied — a threshold read
        from a writable checkout is a pass mark the graded party set itself.
    :returns: ``passed``, per-check ``checks`` carrying actual and threshold,
        and ``absent_checks`` naming any required check that was not run.
    """
    return _impl.evaluate(checks=checks, contract=contract)
