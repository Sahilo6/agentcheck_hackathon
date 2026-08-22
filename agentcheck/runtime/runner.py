"""The step loop: run one scenario against one agent inside a mock world.

The runner is intentionally the only place that touches both the agent and the
world. Everything it learns is written into the trace, so detectors never need
to re-run anything -- which is what makes replay and offline scoring possible.
"""

from __future__ import annotations

from ..spec.models import ScenarioSpec
from ..world.clock import DeterministicClock
from ..world.mock import MockWorld
from .agent import Agent, FinishAction, Observation, ToolAction
from .tools import Toolset
from .trace import Trace


def run_scenario(spec: ScenarioSpec, agent: Agent, toolset: Toolset) -> Trace:
    """Execute one scenario and return the complete trace.

    Budget exhaustion is recorded as a stop reason rather than raised: running
    out of steps is a real, classifiable failure mode, not an infrastructure
    error.
    """
    world = MockWorld.from_spec(spec.world, clock=DeterministicClock())
    trace = Trace(scenario_id=spec.id, agent_id=getattr(agent, "id", "unknown"))
    trace.world_before = world.snapshot()
    trace.add_message("user", spec.task)

    # Only expose the tools this scenario permits, when it says so. A scenario
    # that lists no allowed_tools hands over the whole toolset -- the harder,
    # more realistic case, where nothing stops the agent reaching for a
    # destructive tool except its own judgement.
    visible = [
        s
        for s in toolset.schemas()
        if not spec.allowed_tools or s["name"] in spec.allowed_tools
    ]

    agent.begin(spec.task, visible)

    observation: Observation | None = None
    try:
        while True:
            if trace.steps_used >= spec.budget.max_steps:
                trace.stopped = "budget_steps"
                break
            if len(trace.calls) >= spec.budget.max_tool_calls:
                trace.stopped = "budget_calls"
                break

            action = agent.step(observation)
            trace.steps_used += 1

            if isinstance(action, FinishAction):
                trace.final_message = action.message
                trace.add_message("assistant", action.message)
                trace.stopped = "finished"
                break

            if not isinstance(action, ToolAction):
                trace.stopped = "error"
                trace.error = f"agent returned {type(action).__name__}, expected an Action"
                break

            ok, result = toolset.invoke(world, action.tool, action.args)
            trace.add_call(
                action.tool,
                action.args,
                ok=ok,
                result=result,
                error=None if ok else result,
            )
            observation = Observation(tool=action.tool, ok=ok, result=result)

    except Exception as exc:  # a crashing agent is a finding, not a harness bug
        trace.stopped = "error"
        trace.error = f"{type(exc).__name__}: {exc}"

    trace.world_after = world.snapshot()
    trace.journal = [
        {"seq": e.seq, "op": e.op, "target": e.target, "detail": e.detail, "destructive": e.destructive}
        for e in world.journal
    ]
    trace.observed = list(world.observed)
    return trace
