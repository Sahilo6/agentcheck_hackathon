"""Record and replay.

The demo must never depend on a live API call, and a replayed report must carry
exactly the same weight as a live one. Both properties are asserted here.
"""

import pytest

from agentcheck.engine import run_suite
from agentcheck.gen.builtin import builtin_seeds
from agentcheck.gen.mutations import expand
from agentcheck.runtime.replay import MissingTraces, TraceStore
from agentcheck.toolkits import toolset_for
from demo_agents import HardenedDevOpsAgent, NaiveDevOpsAgent

TOOLS = toolset_for("devops")


@pytest.fixture(scope="module")
def suite():
    return expand(builtin_seeds("devops"), pairs=False)


def test_replay_reproduces_the_live_scorecard_exactly(tmp_path, suite):
    store = tmp_path / "traces.jsonl"
    live = run_suite(suite, NaiveDevOpsAgent, TOOLS, record_to=store)

    # No agent passed at all: the traces are the only input.
    replayed = run_suite(suite, None, TOOLS, replay_from=store)

    assert replayed.pass_rate == live.pass_rate
    assert replayed.by_mode() == live.by_mode()
    assert replayed.by_severity() == live.by_severity()
    assert [r.trace.fingerprint() for r in replayed.results] == [
        r.trace.fingerprint() for r in live.results
    ]


def test_replay_preserves_the_recorded_agent_id(tmp_path, suite):
    store = tmp_path / "t.jsonl"
    run_suite(suite, HardenedDevOpsAgent, TOOLS, record_to=store)
    assert run_suite(suite, None, TOOLS, replay_from=store).agent_id == "devops-assistant-v2"


def test_partial_store_is_refused_by_default(tmp_path, suite):
    """A silent partial replay is worse than a loud failure.

    Scoring 20 of 175 scenarios while presenting a pass rate would be a
    misleading number, and nobody would notice it was wrong.
    """
    store = tmp_path / "t.jsonl"
    run_suite(suite[:5], NaiveDevOpsAgent, TOOLS, record_to=store)
    with pytest.raises(MissingTraces) as exc:
        run_suite(suite, None, TOOLS, replay_from=store)
    assert "not in" in str(exc.value)
    assert "--replay-partial" in str(exc.value)


def test_partial_replay_is_available_when_asked_for(tmp_path, suite):
    store = tmp_path / "t.jsonl"
    run_suite(suite[:5], NaiveDevOpsAgent, TOOLS, record_to=store)
    card = run_suite(suite, None, TOOLS, replay_from=store, replay_partial=True)
    assert card.total == 5


def test_rerecording_a_scenario_overwrites_it(tmp_path, suite):
    store = tmp_path / "t.jsonl"
    run_suite(suite, NaiveDevOpsAgent, TOOLS, record_to=store)
    run_suite(suite, HardenedDevOpsAgent, TOOLS, record_to=store)
    # Append-only file, later entries win, so the hardened run is what replays.
    card = run_suite(suite, None, TOOLS, replay_from=store)
    assert card.agent_id == "devops-assistant-v2"
    assert card.pass_rate == 1.0


def test_store_round_trips_traces(tmp_path, suite):
    store = TraceStore(tmp_path / "t.jsonl")
    live = run_suite(suite, NaiveDevOpsAgent, TOOLS)
    for result in live.results:
        store.append(result.trace)
    loaded = store.load()
    assert len(loaded) == len(live.results)
    for result in live.results:
        assert loaded[result.spec.id].fingerprint() == result.trace.fingerprint()


def test_missing_store_loads_empty(tmp_path):
    assert TraceStore(tmp_path / "nope.jsonl").load() == {}


def test_replaying_without_an_agent_needs_a_store(suite):
    with pytest.raises(ValueError, match="agent_factory is required"):
        run_suite(suite[:1], None, TOOLS)
