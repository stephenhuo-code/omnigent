"""Handoff admissibility for pipely.

Only immutable references may cross a handoff, so that what the receiver
fetches is what the sender verified.
"""

from __future__ import annotations

from typing import Any, TypeAlias

_Json: TypeAlias = dict[str, Any]  # type: ignore[explicit-any]

#: A branch keeps advancing after the handoff was written; a workspace path
#: resolves only on the sender's machine. Neither survives the trip.
_MUTABLE_PREFIXES = ("refs/heads/", "/")


def check_deployment_scope(
    *,
    artifact_jobs: list[str],
    requested_jobs: list[str],
) -> _Json:
    """Judge whether a release stays inside what the artifact covers.

    :param artifact_jobs: The job definitions the handed-over artifact contains.
    :param requested_jobs: The job definitions the release would deploy.
    :returns: Report with ``passed``, ``out_of_scope``, and ``reason``.
    """
    out_of_scope = [job for job in requested_jobs if job not in artifact_jobs]
    # Naming the jobs points at the artifact that would have to be rebuilt; a
    # bare refusal only sends the operator hunting.
    reason = (
        ""
        if not out_of_scope
        else (f"These jobs are not in the handed-over artifact: {', '.join(out_of_scope)}.")
    )
    return {"passed": not out_of_scope, "out_of_scope": out_of_scope, "reason": reason}


def check_handoff(*, references: list[str]) -> _Json:
    """Judge whether every reference in a handoff is safe to hand on.

    :param references: The references the handoff carries.
    :returns: Report with ``passed`` and ``rejected``.
    """
    rejected = [ref for ref in references if ref.startswith(_MUTABLE_PREFIXES)]
    return {"passed": not rejected, "rejected": rejected}
