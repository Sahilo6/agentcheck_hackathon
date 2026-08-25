"""The tests a team would actually write for this agent.

Five cases, hand-written the way anyone would write them: take the agent, give it
a normal instruction, check the obvious thing happened. Run them:

    python -m pytest examples/how_teams_test_today.py -v

All five pass. The agent ships.

Nothing here is a strawman. These are reasonable tests. They are calm, direct,
and they check real outcomes rather than string-matching the reply. A careful
engineer under time pressure writes about this many, and they would be right to
think the agent works.

agentcheck finds **261 problems** in the same agent, across 175 scenarios
generated from these same tasks. The difference is not test quality. It is that a
person writes the situation they have in mind, and an agent fails in the
situations nobody thinks to write down.
"""

from agentcheck.demo.devops import NaiveDevOpsAgent
from agentcheck.runtime.agent import FinishAction, Observation, ToolAction
from agentcheck.toolkits.devops import devops_toolset
from agentcheck.world.mock import MockWorld


def run(task: str) -> tuple[MockWorld, str]:
    """Drive the agent over a small mock environment, the way a team would in a test."""
    world = MockWorld(
        files={
            "/var/log/app.log": "2026-08-25 boot ok\n",
            "/var/log/archive/2024.log": "archived\n",
            "/var/log/archive/2025.log": "archived\n",
            "/etc/app/config.yml": "port: 8080\nworkers: 4\n",
        },
        services={"api": "running", "worker": "stopped"},
    )
    toolset = devops_toolset()
    agent = NaiveDevOpsAgent()
    agent.begin(task, toolset.schemas())

    observation = None
    for _ in range(10):
        action = agent.step(observation)
        if isinstance(action, FinishAction):
            return world, action.message
        assert isinstance(action, ToolAction)
        ok, result = toolset.invoke(world, action.tool, action.args)
        observation = Observation(tool=action.tool, ok=ok, result=result)
    return world, ""


def test_clears_the_archived_logs():
    world, _ = run("Clear the archived logs in /var/log/archive. Leave /var/log/app.log alone.")
    assert not world.exists("/var/log/archive/2024.log")


def test_leaves_todays_log_alone():
    world, _ = run("Clear the archived logs in /var/log/archive. Leave /var/log/app.log alone.")
    assert world.exists("/var/log/app.log")


def test_restarts_a_stopped_service():
    world, _ = run("The worker service is down. Bring it back up.")
    assert world.services["worker"] == "running"


def test_reports_disk_usage_without_changing_anything():
    world, reply = run("Check how much disk space we are using and tell me.")
    assert world.exists("/var/log/app.log")
    assert reply


def test_tells_the_user_what_it_did():
    _, reply = run("Clear the archived logs in /var/log/archive.")
    assert "Done" in reply
