"""Quality gate for pipely.

The tool whose real return value moves the G2 gate. Thresholds run in both
directions, so each check declares which way it is read.
"""

from __future__ import annotations

from typing import Any

MIN = "min"
MAX = "max"

#: Every check a G2 pass must include. Order is the order they are reported in.
REQUIRED_CHECKS = (
    "record_count",
    "anomaly_rate",
    "schema_match",
    "golden_cases",
    "query_latency",
)


def evaluate(
    *,
    checks: list[dict[str, Any]],
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Judge every gate check against its threshold.

    :param checks: Checks, each with ``name``, ``actual``, ``threshold``, and
        ``direction`` (``"min"`` for higher-is-better, ``"max"`` for lower).
    :param contract: Frozen thresholds from the artifact reference.
    :returns: Report with ``passed``, ``checks``, and ``absent_checks``.
    """
    # Thresholds come from the frozen contract, never from the checkout: a
    # writable threshold lets the same commit that fails the gate lower the bar.
    if not contract:
        return {
            "passed": False,
            "malformed": True,
            "checks": [],
            "absent_checks": list(REQUIRED_CHECKS),
            "reason": "No frozen contract in the artifact reference; nothing to grade against.",
        }
    frozen = contract
    checks = [{**c, "threshold": frozen[c["name"]]} if c["name"] in frozen else c for c in checks]
    results = [{**c, "met": _meets(c)} for c in checks]
    # A gate that silently drops a check still reports green, having quietly
    # stopped gating on it. Absence must weigh the same as failure.
    present = {c["name"] for c in checks}
    absent = [name for name in REQUIRED_CHECKS if name not in present]
    return {
        "passed": all(r["met"] for r in results) and not absent,
        "checks": results,
        "absent_checks": absent,
    }


def _meets(check: dict[str, Any]) -> bool:
    """Return whether *check*'s observed value satisfies its threshold.

    :param check: One check with ``actual``, ``threshold``, and ``direction``.
    :returns: ``True`` when the check is satisfied.
    """
    if check["direction"] == MIN:
        return bool(check["actual"] >= check["threshold"])
    return bool(check["actual"] <= check["threshold"])
