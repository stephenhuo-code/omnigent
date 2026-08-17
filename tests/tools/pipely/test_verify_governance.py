"""Tests for the pipely governance verification tool.

This tool is what turns "the admin says it is done" into evidence. Its whole
value is in the negative path: an unmet assertion must come back naming what
was expected, what was found, and what to do about it — a bare "not passed"
sends the operator back to the admin with nothing to act on.
"""

from omnigent.tools.pipely import verify_governance
from omnigent.tools.pipely.verify_governance import verify

_WRITE_VERBS = ("create", "update", "delete", "set_", "patch", "put", "post")

DOMAIN_EXISTS = "domain_exists"
OWNER_SET = "owner_set"


def _assertion(name: str, *, expected: str, actual: str) -> dict[str, object]:
    """Build one governance assertion with its expected and observed values."""
    return {"name": name, "expected": expected, "actual": actual}


def test_all_assertions_met_reports_a_pass_with_nothing_outstanding() -> None:
    """The positive path: nothing left to do, and it says so explicitly."""
    report = verify(
        assertions=[
            _assertion(DOMAIN_EXISTS, expected="present", actual="present"),
            _assertion(OWNER_SET, expected="data_platform", actual="data_platform"),
        ],
    )

    assert report["passed"] is True
    assert report["missing_steps"] == []


def test_an_unmet_assertion_reports_both_the_expected_and_the_found_value() -> None:
    """ "Not passed" is not actionable; the gap between the two values is."""
    report = verify(
        assertions=[
            _assertion(DOMAIN_EXISTS, expected="present", actual="present"),
            _assertion(OWNER_SET, expected="data_platform", actual="unassigned"),
        ],
    )

    assert report["passed"] is False
    unmet = [r for r in report["results"] if not r["met"]]
    assert len(unmet) == 1
    assert unmet[0]["expected"] == "data_platform"
    assert unmet[0]["actual"] == "unassigned"


def test_an_unmet_assertion_yields_the_step_that_would_satisfy_it() -> None:
    """The report goes back to a human admin, so it must say what to actually do.

    One step per unmet assertion, naming that assertion — a single lumped
    "fix governance" is not something anyone can execute.
    """
    report = verify(
        assertions=[
            _assertion(DOMAIN_EXISTS, expected="present", actual="absent"),
            _assertion(OWNER_SET, expected="data_platform", actual="unassigned"),
        ],
    )

    assert len(report["missing_steps"]) == 2
    assert any(DOMAIN_EXISTS in step for step in report["missing_steps"])
    assert any(OWNER_SET in step for step in report["missing_steps"])


def test_verifying_the_same_assertions_twice_gives_the_same_answer() -> None:
    """A verdict that drifts between runs cannot gate anything.

    The gate reads this tool's result, so a second call that disagreed with
    the first would make the gate depend on when it happened to be asked.
    """
    assertions = [
        _assertion(DOMAIN_EXISTS, expected="present", actual="absent"),
        _assertion(OWNER_SET, expected="data_platform", actual="data_platform"),
    ]

    assert verify(assertions=assertions) == verify(assertions=assertions)


def test_the_tool_exposes_no_way_to_write_to_the_catalog() -> None:
    """Read-only by construction, not by intention.

    The tool reports on the administrator's manual work; if it could perform
    that work itself, the whole reason the work is manual would be gone.
    """
    exported = [
        name
        for name in dir(verify_governance)
        if not name.startswith("_") and callable(getattr(verify_governance, name))
    ]

    for name in exported:
        assert not any(verb in name for verb in _WRITE_VERBS), name


def test_an_empty_assertion_set_is_malformed_input_not_a_vacuous_pass() -> None:
    """Nothing to check is a broken caller, and "all zero assertions held" is
    the most dangerous possible pass: it opens the gate having verified nothing.
    """
    report = verify(assertions=[])

    assert report["passed"] is False
    assert report["malformed"] is True
