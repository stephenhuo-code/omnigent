"""Governance verification for pipely.

Read-only by construction: this tool checks that the platform administrator's
manual work actually landed, and reports what is still outstanding. It never
performs the governance operation itself.

Carries FR-011 (read-only by construction), FR-017 (every assertion is
checked against what the catalog reports), FR-018 (an unmet assertion
yields the step that would satisfy it), and FR-019 (repeatable, no side
effects).
"""

from __future__ import annotations

from typing import Any


def verify(*, assertions: list[dict[str, Any]]) -> dict[str, Any]:
    """Check every governance assertion against what the catalog reports.

    :param assertions: Assertions, each with ``name``, ``expected``, ``actual``.
    :returns: Report with ``passed``, ``results``, and ``missing_steps``.
    """
    if not assertions:
        # "All zero assertions held" is the most dangerous possible pass: it
        # opens the gate having verified nothing at all.
        return {
            "passed": False,
            "malformed": True,
            "results": [],
            "missing_steps": ["Supply the governance assertions to verify."],
        }
    # Carrying both values through is the point: "not passed" alone sends the
    # operator back to the administrator with nothing to act on.
    results = [{**a, "met": a["actual"] == a["expected"]} for a in assertions]
    unmet = [r for r in results if not r["met"]]
    # One step per unmet assertion. The report goes to a human administrator,
    # and a single lumped "fix governance" is not something anyone can execute.
    missing_steps = [
        f"Set {r['name']} to {r['expected']} (currently {r['actual']})." for r in unmet
    ]
    return {"passed": not unmet, "results": results, "missing_steps": missing_steps}
