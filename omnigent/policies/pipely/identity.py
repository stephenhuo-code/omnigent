"""Bot write scoping for pipely.

Every bot writes only what its role owns. The scope is decided here rather
than trusted to the target system, so a token that turns out broader than
intended is still contained.

Carries FR-003 and FR-063 (platform admin credentials never enter an
agent's environment or tool config), FR-011 and FR-035 (the audit and
verification agents are read-only), FR-057 (a scheduler credential runs
jobs but does not govern them), FR-103 (the architect writes only inside
the sandbox Domain), and FR-105 (the release bot is scoped per pipeline).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

_Json: TypeAlias = dict[str, Any]  # type: ignore[explicit-any]

ARCHITECT_BOT = "pipely_architect"
#: Where the architect lands intermediate and result tables. Real assets in a
#: Domain of their own, so development never writes into governed space.
SANDBOX_DOMAIN = "pipely_sandbox"

#: Verbs that mutate. Matched as prefixes so a tool added later — a
#: ``create_glossary``, an ``update_owner`` — is denied without an edit here.
WRITE_VERBS = (
    "create",
    "update",
    "delete",
    "patch",
    "put",
    "post",
    "set_",
    "add_",
    "remove_",
    "grant",
    "revoke",
)

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


def require_read_only(*, bot: str) -> Callable[[_Json, _Json], _Json]:
    """Factory: refuse any write call made by a read-only *bot*.

    A second, independent mechanism alongside the MCP allow-list. A bot
    mis-granted in the catalog has nothing else stopping it.

    :param bot: The read-only bot this agent calls with.
    :returns: An evaluator ``fn(event, config)`` returning a V0 decision.
    """

    def _evaluate(event: _Json, config: _Json) -> _Json:  # noqa: ARG001
        """Judge one tool call against the bot's read-only boundary.

        :param event: V0 ``tool_call`` event.
        :param config: Runtime config dict (unused).
        :returns: ALLOW / DENY decision dict.
        """
        name = str(event.get("data", {}).get("name") or "")
        # Judged on the VERB, not on a list of known write tools. A list would
        # silently admit whatever tool is added next; a verb test denies it.
        if any(name.startswith(verb) for verb in WRITE_VERBS):
            return {
                "result": "DENY",
                "reason": f"{bot} is read-only; {name} would write.",
            }
        return {"result": "ALLOW"}

    return _evaluate


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


def deny_platform_operations(*, credential: str) -> Callable[[_Json, _Json], _Json]:
    """Factory: refuse platform-administration operations on every tool call.

    :func:`check_operation` answers when asked; this answers whether or not
    anyone remembered to ask.

    :param credential: The credential this agent calls with.
    :returns: An evaluator ``fn(event, config)`` returning a V0 decision.
    """

    def _evaluate(event: _Json, config: _Json) -> _Json:  # noqa: ARG001
        """Judge one tool call against the platform-operation boundary.

        :param event: V0 ``tool_call`` event.
        :param config: Runtime config dict (unused).
        :returns: ALLOW / DENY decision dict.
        """
        # Delegates so the set of platform operations is defined in one place.
        return check_operation(
            credential=credential,
            operation=str(event.get("data", {}).get("name") or ""),
        )

    return _evaluate


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
