"""Read-only verification that governance work actually landed.

Thin adapter. The logic and its tests live in
:mod:`omnigent.tools.pipely.verify_governance`; this file exists because an
agent package reaches a Python tool only as ``tools/python/<name>.py`` (the
tool name is the file stem). Keeping the logic in the importable package is
what lets ``tests/tools/pipely/`` sit next to it.
"""

from __future__ import annotations

from typing import Any

from omnigent_client.tools import tool

from omnigent.tools.pipely import verify_governance as _impl


@tool
def verify_governance(assertions: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Check every governance assertion against what the catalog reports.

    The gate moves on THIS return value, so it reports what was found rather
    than what was expected to be found.

    :param assertions: One entry per assertion, each with ``name``,
        ``expected``, and ``actual`` (the value read back from the catalog).
    :returns: ``passed``, per-assertion ``results`` carrying both values, and
        ``missing_steps`` naming what would satisfy each unmet assertion.
    """
    return _impl.verify(assertions=assertions)
