"""Catalog sync for pipely.

Writes a released pipeline's facts back to the catalog, where operators look
when something is wrong. The catalog is injected so the sync stays testable
without one.

Carries FR-031 (the catalog records version, counts, quality, lineage and
run state), FR-033 (a retried sync lands on the same record), and FR-059
(a catalog outage is reported apart from a scheduler outage).
"""

from __future__ import annotations

from typing import Any, Protocol


class Catalog(Protocol):
    """The catalog surface this tool needs."""

    def upsert(self, key: str, facts: dict[str, Any]) -> None:
        """Record *facts* under *key*, replacing any previous record."""
        ...


def sync(*, catalog: Catalog, pipeline: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Write *facts* about *pipeline* into the catalog.

    :param catalog: The catalog to write to.
    :param pipeline: The pipeline the facts describe.
    :param facts: Version, counts, quality, lineage, and run state.
    :returns: Report with ``synced``.
    """
    # Catalog and scheduler ship together, which is exactly why one outage must
    # not be reported as the other: they send the operator to different places.
    # Retries are normal, so the key must be derived only from what identifies
    # this release. Anything per-call would leave two versions of the truth.
    key = f"{pipeline}@{facts['version']}"
    try:
        catalog.upsert(key, facts)
    except ConnectionError:
        # Deliberately NOT str(exc): clients routinely put the request URL —
        # token and all — into the exception text, and this report reaches the
        # catalog and the operator's console. Say what could not be reached,
        # never what it was reached with.
        return {
            "synced": False,
            "unreachable": "catalog",
            "reason": "The catalog could not be reached.",
        }
    return {"synced": True}
