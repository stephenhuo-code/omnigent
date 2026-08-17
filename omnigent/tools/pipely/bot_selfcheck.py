"""Bot permission self-check for pipely.

A read-only bot whose write probe was not refused has silently lost its
boundary. Proving the token *works* is not the check; proving the write is
*refused* is.
"""

from __future__ import annotations

from typing import Any

READ_ONLY = "read_only"


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
        if expected.get(str(probe["bot"])) == READ_ONLY and not probe["refused"]
    ]
    return {
        "passed": not over_privileged,
        "probes": observed,
        "over_privileged": over_privileged,
    }
