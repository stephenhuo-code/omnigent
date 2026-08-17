"""Tests for what may cross a pipely handoff.

A handoff must name things that cannot move underneath the receiver. A branch
keeps advancing after the handoff was written, and a workspace path only
resolves on the sender's machine, so both describe something the receiver
cannot reliably fetch — and the receiver would not find out until release.
"""

from omnigent.policies.pipely.handoff import check_deployment_scope, check_handoff

CODE_TAG = "pipely/orders_daily/v1.4.2"
ARTIFACT_TAG = "sha256:9f1c0b"
FROZEN_CONTRACT = "contract:orders_daily@3"


def test_a_handoff_naming_a_branch_is_refused() -> None:
    """A branch moves on after the handoff; the receiver would get later work."""
    result = check_handoff(
        references=[CODE_TAG, "refs/heads/feature/orders-rework"],
    )

    assert result["passed"] is False


def test_a_handoff_naming_a_workspace_path_is_refused() -> None:
    """A path resolves only on the sender's machine; the receiver has no such file."""
    result = check_handoff(
        references=[CODE_TAG, "/Users/dev/work/orders_daily/target/bundle.zip"],
    )

    assert result["passed"] is False


def test_a_handoff_of_only_immutable_references_is_admitted() -> None:
    """The positive side: what the sender verified is what the receiver fetches."""
    result = check_handoff(references=[CODE_TAG, ARTIFACT_TAG, FROZEN_CONTRACT])

    assert result["passed"] is True
    assert result["rejected"] == []


def test_deploying_a_job_the_artifact_covers_is_admitted() -> None:
    """Release stays inside what was handed over and verified."""
    result = check_deployment_scope(
        artifact_jobs=["orders_daily_load", "orders_daily_publish"],
        requested_jobs=["orders_daily_load"],
    )

    assert result["passed"] is True


def test_deploying_a_job_outside_the_artifact_names_what_is_out_of_scope() -> None:
    """The other side of the boundary, and it must say which job, not just "no".

    A bare refusal sends the operator hunting; naming the job points straight
    at the artifact that would have to be rebuilt.
    """
    result = check_deployment_scope(
        artifact_jobs=["orders_daily_load"],
        requested_jobs=["orders_daily_load", "orders_daily_backfill"],
    )

    assert result["passed"] is False
    assert result["out_of_scope"] == ["orders_daily_backfill"]
    assert "orders_daily_backfill" in result["reason"]
