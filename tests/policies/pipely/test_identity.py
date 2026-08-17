"""Tests for which bot may write which asset in pipely.

Each bot is scoped to the assets its role owns. The decisive cases are the
ones just outside that scope: a bot that can reach a neighbouring pipeline's
assets has, in practice, no boundary at all.
"""

from omnigent.policies.pipely.identity import (
    check_environment,
    check_operation,
    check_write,
    deny_platform_operations,
    require_read_only,
)

RELEASE_BOT = "pipely_release"
ARCHITECT_BOT = "pipely_architect"
PIPELINE = "orders_daily"
SANDBOX_DOMAIN = "pipely_sandbox"
SCHEDULER_CREDENTIAL = "om_scheduler"
PLATFORM_OPERATION = "create_domain"


def test_the_release_bot_may_write_assets_of_its_own_pipeline() -> None:
    """The role's own pipeline is what release exists to touch."""
    decision = check_write(
        bot=RELEASE_BOT,
        bound_pipeline=PIPELINE,
        asset=f"{PIPELINE}.staging_orders",
    )

    assert decision["result"] == "ALLOW"


def test_the_release_bot_may_not_write_another_pipelines_assets() -> None:
    """A bot that can reach a neighbour's assets has no boundary in practice."""
    decision = check_write(
        bot=RELEASE_BOT,
        bound_pipeline=PIPELINE,
        asset="returns_hourly.staging_returns",
    )

    assert decision["result"] == "DENY"


def test_a_pipeline_whose_name_merely_starts_the_same_is_not_in_scope() -> None:
    """``orders_daily_archive`` is a different pipeline, not part of this one.

    Matching on the bare name hands the bot every pipeline whose name happens
    to begin the same way — a boundary that widens as neighbours are added.
    """
    decision = check_write(
        bot=RELEASE_BOT,
        bound_pipeline=PIPELINE,
        asset="orders_daily_archive.staging_orders",
    )

    assert decision["result"] == "DENY"


def test_the_architect_bot_may_write_inside_its_sandbox_domain() -> None:
    """The architect needs somewhere real to land intermediate and result tables."""
    decision = check_write(
        bot=ARCHITECT_BOT,
        bound_pipeline=PIPELINE,
        asset=f"{SANDBOX_DOMAIN}.orders_daily_intermediate",
    )

    assert decision["result"] == "ALLOW"


def test_the_architect_bot_may_not_write_governed_assets_outside_the_sandbox() -> None:
    """Development writes real tables, but never into governed space.

    The architect holds a write-capable token precisely so it can land tables;
    the sandbox Domain is what keeps that capability off production assets.
    """
    decision = check_write(
        bot=ARCHITECT_BOT,
        bound_pipeline=PIPELINE,
        asset=f"{PIPELINE}.published_orders",
    )

    assert decision["result"] == "DENY"


def test_a_scheduler_credential_cannot_reach_platform_administration() -> None:
    """Same deployment, different authority: running jobs is not governing them.

    The scheduler ships with the catalog, which makes it tempting to treat one
    credential as covering both. Platform administration stays with a human.
    """
    decision = check_operation(
        credential=SCHEDULER_CREDENTIAL,
        operation=PLATFORM_OPERATION,
    )

    assert decision["result"] == "DENY"


def test_a_read_only_bot_calling_a_write_tool_is_denied() -> None:
    """The declaration says read-only; the policy makes it so on every call.

    The MCP allow-list already omits write verbs, so this is the second of two
    independent mechanisms. That redundancy is the point: a bot mis-granted in
    OpenMetadata has nothing else stopping it, and a mis-granted read-only bot
    is exactly what the self-check exists to find.
    """
    decision = require_read_only(bot="governance")(
        {
            "type": "tool_call",
            "data": {"name": "update_table", "arguments": {}},
            "context": {"labels": {}},
        },
        {},
    )

    assert decision["result"] == "DENY"


def test_a_read_only_bot_may_still_read() -> None:
    """The other side: read-only must not collapse into no-access.

    Without this, a policy that denied everything would pass the test above
    while making the agent useless.
    """
    decision = require_read_only(bot="governance")(
        {
            "type": "tool_call",
            "data": {"name": "get_table", "arguments": {}},
            "context": {"labels": {}},
        },
        {},
    )

    assert decision["result"] == "ALLOW"


def test_a_platform_operation_on_the_scheduler_credential_is_denied_at_call_time() -> None:
    """The same rule as check_operation, but binding on every tool call.

    check_operation only answers when someone asks it. A policy on tool_call
    answers whether or not anyone remembered to.
    """
    decision = deny_platform_operations(credential=SCHEDULER_CREDENTIAL)(
        {
            "type": "tool_call",
            "data": {"name": PLATFORM_OPERATION, "arguments": {}},
            "context": {"labels": {}},
        },
        {},
    )

    assert decision["result"] == "DENY"


def test_a_platform_admin_credential_in_the_environment_refuses_startup() -> None:
    """The credential must not be present at all, not merely go unused.

    An agent with a shell can read its whole process environment, so keeping
    the credential out of the environment is the only boundary that holds.
    """
    result = check_environment(
        env={"OMNIGENT_OM_READER": "...", "OMNIGENT_OM_ADMIN": "..."},
    )

    assert result["may_start"] is False
    assert result["forbidden"] == ["OMNIGENT_OM_ADMIN"]
