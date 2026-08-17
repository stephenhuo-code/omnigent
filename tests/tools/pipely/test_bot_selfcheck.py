"""Tests for the pipely bot permission self-check.

The self-check exists to prove a permission boundary is really in force, so its
negative path is the behavior that matters most: a read-only bot whose write
probe was *not* refused has silently lost its boundary, and the check must say
so rather than pass because the token merely worked.
"""

from omnigent.tools.pipely.bot_selfcheck import (
    compare_permissions,
    evaluate,
    probe_actions,
)

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


def test_a_bot_with_no_write_probe_at_all_does_not_pass() -> None:
    """Proving the token works is not the check; proving the write is refused is.

    A read probe that merely succeeded says nothing about the boundary, so a
    bot with no negative probe must not be reported as verified.
    """
    report = evaluate(
        expected={"governance": READ_ONLY},
        observed=[{"bot": "governance", "action": "read_probe", "refused": False}],
    )

    assert report["passed"] is False
    assert "governance" in report["unproven"]


def test_readonly_bot_write_probe_refused_passes_the_selfcheck() -> None:
    """A refused write probe on a read-only bot is the passing case."""
    report = evaluate(
        expected={"governance": READ_ONLY},
        observed=[_probe("governance", refused=True)],
    )

    assert report["passed"] is True
    assert report["over_privileged"] == []


def test_permissions_matching_the_role_exactly_pass() -> None:
    """The inclusive middle of the scale: exactly what the role needs is correct."""
    report = compare_permissions(
        required={"read_catalog", "write_lineage"},
        granted={"read_catalog", "write_lineage"},
    )

    assert report["passed"] is True
    assert report["excess"] == []
    assert report["missing"] == []


def test_permissions_wider_than_the_role_name_the_extra_ones() -> None:
    """Upper side of the threshold, and it must say which grant to remove."""
    report = compare_permissions(
        required={"read_catalog"},
        granted={"read_catalog", "delete_domain", "grant_role"},
    )

    assert report["passed"] is False
    assert report["excess"] == ["delete_domain", "grant_role"]


def test_permissions_narrower_than_the_role_name_the_absent_ones() -> None:
    """Lower side of the threshold: too little fails as loudly as too much.

    Under-granting does not fail safe — the bot works until it reaches the one
    operation it cannot do, mid-release.
    """
    report = compare_permissions(
        required={"read_catalog", "write_lineage"},
        granted={"read_catalog"},
    )

    assert report["passed"] is False
    assert report["missing"] == ["write_lineage"]


def test_every_write_probe_declares_that_it_leaves_no_residue() -> None:
    """A probe only lands when the boundary is already broken — the worst moment
    for it to be destructive. Each probe must therefore declare it does not
    persist, so adding a persisting one is a visible, failing act.

    This pins the declaration, not the catalog state; the state-unchanged
    assertion needs a real catalog and belongs to the integration behaviors.
    """
    probes = probe_actions()

    assert probes, "the self-check must define at least one write probe"
    for probe in probes:
        assert probe["persists"] is False, probe["action"]
