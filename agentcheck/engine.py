"""Top-level entry point: run a suite of scenarios and score the result."""

from __future__ import annotations

from typing import Callable, Iterable

from .detect.detectors import detect_all
from .runtime.agent import Agent
from .runtime.runner import run_scenario
from .runtime.tools import Toolset
from .score.scorecard import DEFAULT_FAIL_THRESHOLD, ScenarioResult, Scorecard
from .spec.models import ScenarioSpec

ProgressFn = Callable[[int, int, ScenarioResult], None]


def run_suite(
    specs: Iterable[ScenarioSpec],
    agent_factory: Callable[[], Agent],
    toolset: Toolset,
    *,
    fail_threshold: str = DEFAULT_FAIL_THRESHOLD,
    on_progress: ProgressFn | None = None,
) -> Scorecard:
    """Run every scenario against a fresh agent instance and score the results.

    `agent_factory` rather than a single agent: state leaking between scenarios
    would make results depend on ordering, which would quietly destroy
    reproducibility.
    """
    specs = list(specs)
    results: list[ScenarioResult] = []
    agent_id = "unknown"

    for index, spec in enumerate(specs, start=1):
        agent = agent_factory()
        agent_id = getattr(agent, "id", agent_id)
        trace = run_scenario(spec, agent, toolset)
        findings = detect_all(spec, trace)
        result = ScenarioResult(
            spec=spec, trace=trace, findings=findings, fail_threshold=fail_threshold
        )
        results.append(result)
        if on_progress:
            on_progress(index, len(specs), result)

    return Scorecard(agent_id=agent_id, results=results)
