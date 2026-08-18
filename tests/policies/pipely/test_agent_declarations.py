"""Assertions about what the pipely agent definitions declare.

Configuration has no runtime logic, but what it declares is the strongest
boundary this feature has: an agent with no ``os_env`` has no shell and no file
tools, which is not a rule the model can be talked out of. These tests parse the
real package, so a later edit that widens a boundary fails here rather than in
production.
"""

from pathlib import Path

import pytest

from omnigent.policies.pipely.gates import READY_GATE
from omnigent.policies.pipely.identity import FORBIDDEN_ENV_NAMES, WRITE_VERBS
from omnigent.spec.parser import parse
from omnigent.spec.types import AgentSpec

PACKAGE = Path(__file__).resolve().parents[3] / "examples" / "pipely"

#: The three sub-agents that must never have a shell.
NO_SHELL_AGENTS = ("governance", "operations", "consumer")


@pytest.fixture(scope="module")
def spec() -> AgentSpec:
    """Parse the real pipely package once for the whole module."""
    return parse(PACKAGE, expand_env=False)


def _sub_agent(spec: AgentSpec, name: str) -> AgentSpec:
    """Return the sub-agent called *name*, failing loudly if it is absent."""
    found = next((a for a in spec.sub_agents if a.name == name), None)
    assert found is not None, f"{name} is not declared in the package"
    return found


@pytest.mark.parametrize("name", NO_SHELL_AGENTS)
def test_the_no_shell_sub_agents_declare_no_os_env(spec: AgentSpec, name: str) -> None:
    """No ``os_env`` means no shell and no file tools — a boundary by absence.

    These three read the catalog, release, and verify. None of them has any
    business running a command, and an agent that cannot run one cannot be
    persuaded to run one by anything carried in a data sample.
    """
    assert _sub_agent(spec, name).os_env is None


def test_the_architect_has_a_shell_and_a_guard_on_it(spec: AgentSpec) -> None:
    """The architect needs a shell — codex runs there — so it needs a guard.

    A shell without a blast-radius guard is the one combination in this package
    that could reach outside its worktree, force-push, or hard-reset.
    """
    architect = _sub_agent(spec, "architect")

    assert architect.os_env is not None
    guarded = {p.name for p in (architect.guardrails.policies or []) if p.name == "worktree_guard"}
    assert guarded == {"worktree_guard"}


def test_the_orchestrator_shares_to_named_users_not_to_anyone(spec: AgentSpec) -> None:
    """Gate approvals must reach two named people who did not start the session.

    ``none`` leaves the gates undeliverable and ``public`` exposes the flow to
    anyone holding the link. This flag is also the only thing that can enable
    the approve grant at all — ``sys_session_share`` confers an access level
    and cannot confer approval authority.
    """
    assert spec.agent_session_sharing.value == "non-public"


def test_the_approval_window_outlives_a_human_stepping_away(spec: AgentSpec) -> None:
    """A gate waits on a person who may be asleep or waiting on a change window.

    Anything short of a day auto-denies gates that were merely not answered
    yet, and an auto-denied gate reads exactly like a rejected one.
    """
    assert spec.guardrails.ask_timeout >= 86_400


@pytest.mark.parametrize("name", NO_SHELL_AGENTS)
def test_every_catalog_connection_declares_an_allow_list(spec: AgentSpec, name: str) -> None:
    """An absent allow-list exposes every tool the server has.

    That is the difference between "this agent may read" and "this agent may do
    whatever OpenMetadata offers", and it is one omitted key apart.
    """
    for server in _sub_agent(spec, name).mcp_servers:
        assert server.tools, f"{name}/{server.name} exposes every tool on the server"


@pytest.mark.parametrize("name", ("governance", "consumer"))
def test_the_read_only_agents_are_given_no_write_verb(spec: AgentSpec, name: str) -> None:
    """A read-only agent that was handed one write verb is not read-only.

    The policy denies these too, but a verb that is never registered cannot be
    called at all — this is the boundary that holds even if the policy is
    misconfigured.
    """
    for server in _sub_agent(spec, name).mcp_servers:
        offending = [t for t in (server.tools or []) if t.startswith(WRITE_VERBS)]
        assert offending == [], f"{name}/{server.name} exposes {offending}"


def test_only_operations_can_reach_the_scheduler(spec: AgentSpec) -> None:
    """Running jobs is release's job alone, and structurally so.

    Sub-agents parse with their own root, so a scheduler connection declared
    only under operations is unreachable from the others — nobody has to
    remember the rule.
    """
    with_scheduler = {
        agent.name
        for agent in spec.sub_agents
        for server in agent.mcp_servers
        if server.name == "airflow"
    }

    assert with_scheduler == {"operations"}


def test_no_agent_is_handed_a_platform_admin_credential(spec: AgentSpec) -> None:
    """The forbidden credential must appear nowhere: not in an environment, not
    in a header, not in a tool config. The architect has a shell and can read
    its whole process environment, so "present but unused" is not a boundary.
    """
    everywhere: list[str] = []
    for agent in [spec, *spec.sub_agents]:
        for server in agent.mcp_servers:
            everywhere.extend(server.headers.values())
            everywhere.extend(server.env.values())

    for value in everywhere:
        for forbidden in FORBIDDEN_ENV_NAMES:
            assert forbidden not in value, f"{forbidden} reached a tool config"


def test_nothing_an_agent_does_can_advance_the_release_gate(spec: AgentSpec) -> None:
    """G3 is a human's decision — they merge the change request — so no policy
    in this package may grant it. If one did, the flow would sail past the
    checkpoint that exists to put a person in front of the merge.

    Written as a scan of every declared policy rather than of the two I happen
    to remember: a grant added later is exactly what this must catch.
    """
    granted: list[str] = []
    for agent in [spec, *spec.sub_agents]:
        for policy in agent.guardrails.policies or []:
            arguments = getattr(getattr(policy, "function", None), "arguments", None) or {}
            if arguments.get("grants") == READY_GATE:
                granted.append(f"{agent.name}/{policy.name}")

    assert granted == [], f"these would advance {READY_GATE} without a human: {granted}"


def _env_example_names() -> set[str]:
    """Return every variable name the shipped ``.env.example`` declares."""
    text = (PACKAGE / ".env.example").read_text(encoding="utf-8")
    return {
        line.split("=", 1)[0].strip()
        for line in text.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }


def test_the_environment_template_offers_no_platform_admin_credential() -> None:
    """The template is where an operator learns what to configure.

    Listing the admin credential here — even commented as optional — is how it
    ends up in a real ``.env``, and from there in the architect's process
    environment, which its shell can read.
    """
    declared = _env_example_names()

    assert declared.isdisjoint(FORBIDDEN_ENV_NAMES)


def test_the_change_request_and_git_credentials_are_separate_entries() -> None:
    """Executing governance and pushing code are different authorities.

    One entry covering both would mean the credential that opens a pull request
    could also act on the catalog — and no configuration change could separate
    them again without editing code.
    """
    declared = _env_example_names()

    assert "OMNIGENT_GIT_TOKEN" in declared
    assert "OMNIGENT_OM_BOOTSTRAP_READER" in declared
    assert "OMNIGENT_AIRFLOW_TOKEN" in declared
    # The scheduler credential is its own entry, not folded into the catalog's.
    assert "OMNIGENT_OM_RELEASE" in declared


def test_every_verdict_policy_lives_on_the_agent_that_owns_its_tool(spec: AgentSpec) -> None:
    """A tool_result policy only fires for the agent whose spec declares it.

    Sub-agents are separate specs and the runner builds each session's policy
    set from its own guardrails (runner/policy.py::from_spec). Only runtime
    session policies are inherited from the root conversation — agent policies
    are not. So a verdict policy declared on the orchestrator, watching a tool
    that runs inside a sub-agent, never runs at all: the label is never
    written, and the gate it guards can never open.
    """
    owner_of_tool = {
        tool.name: agent.name for agent in spec.sub_agents for tool in agent.local_tools
    }

    misplaced: list[str] = []
    for agent in [spec, *spec.sub_agents]:
        for policy in agent.guardrails.policies or []:
            watched = (getattr(getattr(policy, "function", None), "arguments", None) or {}).get(
                "tool"
            )
            if watched is None:
                continue
            owner = owner_of_tool.get(str(watched))
            if owner is not None and owner != agent.name:
                misplaced.append(f"{agent.name}/{policy.name} watches {watched} owned by {owner}")

    assert misplaced == [], "these verdict policies will never fire: " + "; ".join(misplaced)
