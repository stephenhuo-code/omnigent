"""Tests for the pipely bot permission self-check.

The self-check exists to prove a permission boundary is really in force, so its
negative path is the behavior that matters most: a read-only bot whose write
probe was *not* refused has silently lost its boundary, and the check must say
so rather than pass because the token merely worked.
"""

from omnigent.tools.pipely.bot_selfcheck import evaluate

READ_ONLY = "read_only"


def _probe(bot: str, *, refused: bool) -> dict[str, object]:
    """Build one observed write-probe outcome for *bot*."""
    return {"bot": bot, "action": "write_probe", "refused": refused}


def test_readonly_bot_write_probe_not_refused_fails_the_selfcheck() -> None:
    """An unrefused write probe on a read-only bot fails and names the bot."""
    report = evaluate(
        expected={"governance": READ_ONLY},
        observed=[_probe("governance", refused=False)],
    )

    assert report["passed"] is False
    assert "governance" in report["over_privileged"]


def test_readonly_bot_write_probe_refused_passes_the_selfcheck() -> None:
    """A refused write probe on a read-only bot is the passing case."""
    report = evaluate(
        expected={"governance": READ_ONLY},
        observed=[_probe("governance", refused=True)],
    )

    assert report["passed"] is True
    assert report["over_privileged"] == []
