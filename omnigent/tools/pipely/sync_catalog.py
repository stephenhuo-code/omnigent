"""Catalog sync for pipely.

Writes a released pipeline's facts back to the catalog, where operators look
when something is wrong. The catalog is injected so the sync stays testable
without one.
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
    except ConnectionError as exc:
        return {"synced": False, "unreachable": "catalog", "reason": str(exc)}
    return {"synced": True}
