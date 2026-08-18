"""Artifact reference for pipely.

What a handoff carries and what the quality gate grades against. Everything in
it is immutable by construction, so the receiver fetches what the sender
verified rather than whatever the branch has become since.

Carries FR-023 (no writable source location crosses a handoff), FR-101
(thresholds and assertions are frozen alongside the version), and FR-102
(a frozen reference is not editable — changes go to a new version).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from omnigent.policies.pipely.handoff import check_handoff


def build(
    *,
    code_tag: str,
    artifact_tag: str,
    thresholds: dict[str, Any],
    assertions: dict[str, Any],
) -> Mapping[str, Any]:
    """Build the artifact reference for one verified pipeline version.

    :param code_tag: Immutable tag naming the source revision.
    :param artifact_tag: Content digest of the built artifact.
    :param thresholds: The frozen thresholds the gate will grade against.
    :param assertions: The frozen governance assertions to verify.
    :returns: The artifact reference.
    """
    # Refuse at build time so the mutable pointer never enters the handoff,
    # rather than catching it once the receiver has fetched the wrong revision.
    rejected = check_handoff(references=[code_tag, artifact_tag])["rejected"]
    if rejected:
        raise ValueError(f"An artifact reference cannot be built on {rejected[0]}.")
    # Immutable: the gate graded against these values, and an editable
    # reference lets a release be re-pointed after approval without re-approval.
    return MappingProxyType(
        {
            "code_tag": code_tag,
            "artifact_tag": artifact_tag,
            "thresholds": MappingProxyType(dict(thresholds)),
            "assertions": MappingProxyType(dict(assertions)),
        }
    )
