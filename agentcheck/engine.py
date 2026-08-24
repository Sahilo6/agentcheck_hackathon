"""Top-level entry point: run a suite of scenarios and score the result."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from .detect.detectors import detect_all
from .runtime.agent import Agent
from .runtime.replay import TraceStore, resolve_replay
from .runtime.runner import run_scenario
from .runtime.tools import Toolset
from .score.scorecard import DEFAULT_FAIL_THRESHOLD, ScenarioResult, Scorecard
from .spec.models import ScenarioSpec

ProgressFn = Callable[[int, int, ScenarioResult], None]


def run_suite(
    specs: Iterable[ScenarioSpec],
    agent_factory: Callable[[], Agent] | None,
    toolset: Toolset,
    *,
    fail_threshold: str = DEFAULT_FAIL_THRESHOLD,
    on_progress: ProgressFn | None = None,
    record_to: Path | str | None = None,
    replay_from: Path | str | None = None,
    replay_partial: bool = False,
) -> Scorecard:
    """Run every scenario against a fresh agent instance and score the results.

    `agent_factory` rather than a single agent: state leaking between scenarios
    would make results depend on ordering, which would quietly destroy
    reproducibility.

    Pass `replay_from` to score traces recorded earlier instead of executing the
    agent. Scoring is identical either way -- the detectors never know which
    path produced a trace -- so a replayed report carries the same weight as a
    live one, and the demo can run with the network off.
    """
    specs = list(specs)
    results: list[ScenarioResult] = []
    agent_id = "unknown"

    replayed = None
    if replay_from is not None:
        replayed = resolve_replay(
            TraceStore(replay_from), [s.id for s in specs], strict=not replay_partial
        )
        specs = [s for s in specs if s.id in replayed]

    store = TraceStore(record_to) if record_to is not None else None

    for index, spec in enumerate(specs, start=1):
        if replayed is not None:
            trace = replayed[spec.id]
            agent_id = trace.agent_id or agent_id
        else:
            if agent_factory is None:
                raise ValueError("agent_factory is required unless replaying")
            agent = agent_factory()
            agent_id = getattr(agent, "id", agent_id)
            trace = run_scenario(spec, agent, toolset)
            if store is not None:
                store.append(trace)

        findings = detect_all(spec, trace)
        result = ScenarioResult(
            spec=spec, trace=trace, findings=findings, fail_threshold=fail_threshold
        )
        results.append(result)
        if on_progress:
            on_progress(index, len(specs), result)

    return Scorecard(agent_id=agent_id, results=results)
