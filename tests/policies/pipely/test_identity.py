"""Tests for which bot may write which asset in pipely.

Each bot is scoped to the assets its role owns. The decisive cases are the
ones just outside that scope: a bot that can reach a neighbouring pipeline's
assets has, in practice, no boundary at all.
"""

from omnigent.policies.pipely.identity import (
    check_environment,
    check_operation,
    check_write,
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
