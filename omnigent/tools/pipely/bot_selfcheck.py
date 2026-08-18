"""Bot permission self-check for pipely.

A read-only bot whose write probe was not refused has silently lost its
boundary. Proving the token *works* is not the check; proving the write is
*refused* is.

Carries FR-074 (the boundary is proven by a refused write probe, not by a
working token) and FR-075 (permissions wider or narrower than the role
are both reported, naming the specific grants).
"""

from __future__ import annotations

from typing import Any

READ_ONLY = "read_only"
WRITE_PROBE = "write_probe"


def probe_actions() -> list[dict[str, Any]]:
    """Return the write probes the self-check performs.

    :returns: Probe descriptors, each with ``action`` and ``persists``.
    """
    # A probe lands only when the boundary is already broken — the worst moment
    # for it to be destructive. Every probe here must leave no residue.
    return [
        {"action": "set_description_on_own_probe_asset", "persists": False},
        {"action": "validate_only_lineage_edge", "persists": False},
    ]


def compare_permissions(
    *,
    required: set[str],
    granted: set[str],
) -> dict[str, Any]:
    """Compare what a bot was granted against what its role requires.

    :param required: The permissions the role needs.
    :param granted: The permissions the bot actually holds.
    :returns: Report with ``passed``, ``excess``, and ``missing``.
    """
    excess = sorted(granted - required)
    missing = sorted(required - granted)
    return {
        "passed": not excess and not missing,
        "excess": excess,
        "missing": missing,
    }


def evaluate(
    *,
    expected: dict[str, str],
    observed: list[dict[str, Any]],
) -> dict[str, Any]:
    """Judge observed probe outcomes against each bot's expected permission.

    :param expected: Bot name to the permission level it is supposed to have.
    :param observed: Probe outcomes, each naming the bot, the action, and
        whether the target system refused it.
    :returns: Report with ``passed``, ``probes``, and ``over_privileged``.
    """
    over_privileged = [
        probe["bot"]
        for probe in observed
        if probe["action"] == WRITE_PROBE
        and expected.get(str(probe["bot"])) == READ_ONLY
        and not probe["refused"]
    ]
    # A read probe that merely succeeded says nothing about the boundary. A bot
    # with no negative probe is unproven, which is not the same as compliant.
    probed = {probe["bot"] for probe in observed if probe["action"] == WRITE_PROBE}
    unproven = [bot for bot in expected if bot not in probed]
    return {
        "passed": not over_privileged and not unproven,
        "probes": observed,
        "over_privileged": over_privileged,
        "unproven": unproven,
    }
