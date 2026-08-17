"""Prove each bot's permission boundary by probing it negatively.

Thin adapter over :mod:`omnigent.tools.pipely.bot_selfcheck`; see
``verify_governance.py`` in this directory for why the adapter exists.
"""

from __future__ import annotations

from typing import Any

from omnigent_client.tools import tool

from omnigent.tools.pipely import bot_selfcheck as _impl


@tool
def bot_selfcheck(
    expected: dict[str, str],
    observed: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Judge observed probe outcomes against each bot's expected permission.

    The decisive case is a read-only bot whose WRITE probe was not refused:
    that bot has silently lost its boundary, and this must fail rather than
    pass because the token merely worked.

    :param expected: Bot name to the permission level it is supposed to have.
    :param observed: Probe outcomes, each with ``bot``, ``action``, and
        ``refused``. Use :func:`probe_actions` to learn which probes to run —
        every one of them is harmless, because a probe only lands when the
        boundary is already broken.
    :returns: ``passed``, the ``probes`` as given, ``over_privileged`` naming
        bots that accepted a write they should have refused, and ``unproven``
        naming bots with no write probe at all.
    """
    return _impl.evaluate(expected=expected, observed=observed)


@tool
def probe_actions() -> list[dict[str, Any]]:
    """
    Return the write probes the self-check expects to be run.

    :returns: Probe descriptors, each with ``action`` and ``persists``. Every
        probe declares ``persists: false`` — a probe succeeds only when a
        boundary is already broken, which is the worst moment for it to be
        destructive.
    """
    return _impl.probe_actions()
