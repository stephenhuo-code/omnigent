"""Write a released pipeline's facts back to the catalog.

Thin adapter over :mod:`omnigent.tools.pipely.sync_catalog`.
"""

from __future__ import annotations

from typing import Any

from omnigent_client.tools import tool

from omnigent.tools.pipely import sync_catalog as _impl


@tool
def sync_catalog(
    pipeline: str,
    facts: dict[str, Any],
    catalog: Any = None,
) -> dict[str, Any]:
    """
    Record this release's facts against *pipeline* in the catalog.

    Keyed on the release identity, so a retried sync lands on the same record
    rather than leaving two versions of the truth for an operator to choose
    between.

    :param pipeline: The pipeline the facts describe.
    :param facts: ``version``, ``record_count``, ``quality``, ``lineage``, and
        ``run_state``. A dropped field leaves the operator reading a
        half-truth, so all five belong here.
    :param catalog: The catalog client. Injected by the runtime.
    :returns: ``synced``; on failure also ``unreachable`` naming which system
        was down — ``"catalog"`` and ``"scheduler"`` send the reader to
        different dashboards.
    """
    return _impl.sync(catalog=catalog, pipeline=pipeline, facts=facts)
