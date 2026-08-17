"""Tests for the pipely artifact reference.

The artifact reference is what a handoff carries and what the gate grades
against, so it must pin everything the receiver needs and nothing the sender
can still change. Its two dangers are the same one twice: a mutable pointer
sneaking in, and an existing reference being edited after the fact.
"""

import pytest

from omnigent.tools.pipely.artifact_ref import build

CODE_TAG = "pipely/orders_daily/v1.4.2"
ARTIFACT_TAG = "sha256:9f1c0b"
THRESHOLDS = {"record_count": 5_000}
ASSERTIONS = {"owner_set": "data_platform"}


def test_a_reference_pins_code_artifact_thresholds_and_assertions() -> None:
    """All four, because each is something the receiver cannot re-derive."""
    ref = build(
        code_tag=CODE_TAG,
        artifact_tag=ARTIFACT_TAG,
        thresholds=THRESHOLDS,
        assertions=ASSERTIONS,
    )

    assert ref["code_tag"] == CODE_TAG
    assert ref["artifact_tag"] == ARTIFACT_TAG
    assert ref["thresholds"] == THRESHOLDS
    assert ref["assertions"] == ASSERTIONS


def test_building_a_reference_from_a_branch_is_refused() -> None:
    """A reference built on a branch pins nothing: the branch moves on.

    Refusing at build time is what keeps the mutable pointer out of the
    handoff, rather than catching it later when the receiver has already
    fetched the wrong revision.
    """
    with pytest.raises(ValueError, match="refs/heads/"):
        build(
            code_tag="refs/heads/feature/orders-rework",
            artifact_tag=ARTIFACT_TAG,
            thresholds=THRESHOLDS,
            assertions=ASSERTIONS,
        )


def test_an_existing_reference_cannot_be_edited() -> None:
    """The gate graded against these values; changing them rewrites history.

    An editable reference means a release can be re-pointed after approval
    without anyone re-approving it.
    """
    ref = build(
        code_tag=CODE_TAG,
        artifact_tag=ARTIFACT_TAG,
        thresholds=THRESHOLDS,
        assertions=ASSERTIONS,
    )

    with pytest.raises(TypeError):
        ref["code_tag"] = "pipely/orders_daily/v9.9.9"  # type: ignore[index]


def test_building_twice_from_the_same_inputs_gives_the_same_reference() -> None:
    """A reference that varied per call could not be compared across a handoff.

    The receiver checks the reference it was given against the one the gate
    graded; if building embedded a timestamp or a nonce those would never match.
    """
    first = build(
        code_tag=CODE_TAG,
        artifact_tag=ARTIFACT_TAG,
        thresholds=THRESHOLDS,
        assertions=ASSERTIONS,
    )
    second = build(
        code_tag=CODE_TAG,
        artifact_tag=ARTIFACT_TAG,
        thresholds=THRESHOLDS,
        assertions=ASSERTIONS,
    )

    assert dict(first) == dict(second)
