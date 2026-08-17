"""Tests for the pipely quality gate.

This is the tool whose real return value moves the G2 gate, so its verdict is
load-bearing in a way a report is not. Thresholds run in both directions —
more records is better, more anomalies is worse — and the boundary cases are
where a gate silently stops gating.
"""

from omnigent.tools.pipely.quality_gate import evaluate

MIN = "min"
MAX = "max"


def _check(name: str, *, actual: float, threshold: float, direction: str) -> dict[str, object]:
    """Build one gate check with its observed value and its threshold."""
    return {
        "name": name,
        "actual": actual,
        "threshold": threshold,
        "direction": direction,
    }


#: The five checks a pass must include, each comfortably satisfied. Tests that
#: are about one check override just that one, so no test accidentally passes
#: by leaving a check out.
_PASSING_SET = {
    "record_count": (10_000, 5_000, MIN),
    "anomaly_rate": (0.001, 0.01, MAX),
    "schema_match": (1.0, 1.0, MIN),
    "golden_cases": (12, 12, MIN),
    "query_latency": (0.4, 2.0, MAX),
}


def _full_set(**overrides: tuple[float, float, str]) -> list[dict[str, object]]:
    """Build all five checks, replacing any named in *overrides*."""
    merged = {**_PASSING_SET, **overrides}
    return [
        _check(name, actual=actual, threshold=threshold, direction=direction)
        for name, (actual, threshold, direction) in merged.items()
    ]


def _contract_for(checks: list[dict[str, object]]) -> dict[str, object]:
    """Build the frozen contract that matches *checks*' own thresholds."""
    return {str(c["name"]): c["threshold"] for c in checks}


def _run(**overrides: tuple[float, float, str]) -> dict[str, object]:
    """Evaluate the full check set under a contract that matches it."""
    checks = _full_set(**overrides)
    return evaluate(checks=checks, contract=_contract_for(checks))


def test_every_check_comfortably_inside_its_threshold_passes() -> None:
    """The positive path, with thresholds running in both directions."""
    assert _run()["passed"] is True


def test_a_value_sitting_exactly_on_its_threshold_passes() -> None:
    """The threshold is inclusive in both directions.

    This is what decides ``>=`` versus ``>``; a single test on one side of a
    threshold cannot tell them apart.
    """
    report = _run(
        record_count=(5_000, 5_000, MIN),
        anomaly_rate=(0.01, 0.01, MAX),
    )

    assert report["passed"] is True


def test_a_value_one_step_the_wrong_side_of_its_threshold_fails() -> None:
    """The far side of the same boundary, checked in both directions."""
    too_few = _run(record_count=(4_999, 5_000, MIN))
    too_many = _run(anomaly_rate=(0.011, 0.01, MAX))

    assert too_few["passed"] is False
    assert too_many["passed"] is False


def test_each_check_reports_its_actual_value_alongside_its_threshold() -> None:
    """A bare verdict cannot be acted on, or argued with.

    Whoever reads a failed gate needs to see how far off it was to decide
    between fixing the pipeline and revisiting the threshold.
    """
    report = _run(record_count=(4_999, 5_000, MIN))

    (check,) = [c for c in report["checks"] if c["name"] == "record_count"]
    assert check["actual"] == 4_999
    assert check["threshold"] == 5_000
    assert check["met"] is False


def test_a_run_missing_any_of_the_five_required_checks_does_not_pass() -> None:
    """A gate that silently drops a check still reports green, having stopped
    gating on it. Every one of the five must be present for a pass to mean
    what it claims.
    """
    four_of_five = [
        _check(name, actual=1, threshold=0, direction=MIN)
        for name in ("record_count", "anomaly_rate", "schema_match", "golden_cases")
    ]

    report = evaluate(checks=four_of_five, contract=_contract_for(four_of_five))

    assert report["passed"] is False
    assert report["absent_checks"] == ["query_latency"]


def test_thresholds_come_from_the_frozen_contract_not_from_the_repository() -> None:
    """Reading thresholds from a writable checkout lets the graded set its own
    pass mark: the same commit that fails the gate can lower the bar and pass.
    The frozen contract in the artifact reference is what the gate reads.
    """
    contract = {"record_count": 5_000}
    repository = {"record_count": 1}

    report = evaluate(
        checks=_full_set(record_count=(2_000, repository["record_count"], MIN)),
        contract=contract,
    )

    assert report["passed"] is False
    (record_count,) = [c for c in report["checks"] if c["name"] == "record_count"]
    assert record_count["threshold"] == 5_000


def test_a_missing_frozen_contract_is_malformed_not_an_unthresholded_pass() -> None:
    """Without the contract there is nothing to grade against.

    Falling back to whatever the caller supplied would quietly restore exactly
    the self-set pass mark the frozen contract exists to prevent.
    """
    report = evaluate(checks=_full_set(), contract=None)

    assert report["passed"] is False
    assert report["malformed"] is True
