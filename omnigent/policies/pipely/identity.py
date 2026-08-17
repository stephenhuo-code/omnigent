"""Bot write scoping for pipely.

Every bot writes only what its role owns. The scope is decided here rather
than trusted to the target system, so a token that turns out broader than
intended is still contained.
"""

from __future__ import annotations

from typing import Any, TypeAlias

_Json: TypeAlias = dict[str, Any]  # type: ignore[explicit-any]

ARCHITECT_BOT = "pipely_architect"
#: Where the architect lands intermediate and result tables. Real assets in a
#: Domain of their own, so development never writes into governed space.
SANDBOX_DOMAIN = "pipely_sandbox"

#: Credentials that must never appear in any Agent's process environment.
FORBIDDEN_ENV_NAMES = frozenset({"OMNIGENT_OM_ADMIN", "OM_ADMIN_TOKEN"})

#: Operations reserved for a human platform administrator. No Agent credential
#: reaches these, whatever else that credential can do.
PLATFORM_OPERATIONS = frozenset(
    {
        "create_domain",
        "delete_domain",
        "grant_role",
        "revoke_role",
        "create_policy",
        "delete_policy",
    }
)


def check_environment(*, env: dict[str, str]) -> _Json:
    """Judge whether an Agent's process environment is safe to start with.

    :param env: The environment variables the Agent would be started with.
    :returns: Report with ``may_start`` and ``forbidden``.
    """
    # An Agent with a shell reads its whole process environment, so absence is
    # the only boundary that holds. Going unused is not good enough.
    forbidden = sorted(name for name in env if name in FORBIDDEN_ENV_NAMES)
    return {"may_start": not forbidden, "forbidden": forbidden}


def check_operation(*, credential: str, operation: str) -> _Json:
    """Judge whether *credential* may perform *operation*.

    :param credential: The credential the call is made with.
    :param operation: The operation being attempted.
    :returns: ALLOW / DENY decision dict.
    """
    # The scheduler ships with the catalog, which makes one credential look
    # like it covers both. Running jobs is not governing them.
    if operation in PLATFORM_OPERATIONS:
        return {
            "result": "DENY",
            "reason": (
                f"{operation} is a platform administration operation; "
                f"{credential} may not perform it."
            ),
        }
    return {"result": "ALLOW"}


def check_write(*, bot: str, bound_pipeline: str, asset: str) -> _Json:
    """Judge whether *bot* may write *asset*.

    :param bot: The bot attempting the write.
    :param bound_pipeline: The pipeline this session is bound to.
    :param asset: The fully-qualified asset being written.
    :returns: ALLOW / DENY decision dict.
    """
    # The architect works in a sandbox Domain; release works in the pipeline it
    # was handed. Scoping per role keeps a broader-than-intended token contained.
    scope = SANDBOX_DOMAIN if bot == ARCHITECT_BOT else bound_pipeline
    if asset.startswith(f"{scope}."):
        return {"result": "ALLOW"}
    return {
        "result": "DENY",
        "reason": f"{bot} may write only within {scope}; {asset} lies outside it.",
    }
