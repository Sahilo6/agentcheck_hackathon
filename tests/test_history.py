"""Run history and regression diffing.

The CI gate lives or dies here: a regression that does not fail the build is
worse than no gate at all, because it looks like coverage.
"""

from agentcheck.engine import run_suite
from agentcheck.gen.builtin import builtin_seeds
from agentcheck.gen.mutations import expand
from agentcheck.history.store import (
    append_run,
    build_record,
    diff_runs,
    load_runs,
    previous_run,
    suite_hash,
)
from agentcheck.toolkits.devops import devops_toolset
from agentcheck.demo.devops import HardenedDevOpsAgent, NaiveDevOpsAgent

TOOLS = devops_toolset()


def card_for(factory, suite):
    return run_suite(suite, factory, TOOLS)


def test_suite_hash_is_stable_and_content_addressed():
    a, b = expand(builtin_seeds()), expand(builtin_seeds())
    assert suite_hash(a) == suite_hash(b)
    assert suite_hash(a[:10]) != suite_hash(a)


def test_regression_diff_reports_fixes(tmp_path):
    suite = expand(builtin_seeds(), pairs=False)
    before = build_record(card_for(NaiveDevOpsAgent, suite), specs=suite, at="2026-08-23T10:00:00")
    after = build_record(card_for(HardenedDevOpsAgent, suite), specs=suite, at="2026-08-23T11:00:00")

    diff = diff_runs(before, after)
    assert diff.comparable
    assert diff.fixed, "the hardened agent should fix scenarios"
    assert diff.new_failures == []
    assert diff.regressed is False


def test_regression_diff_catches_a_regression():
    suite = expand(builtin_seeds(), pairs=False)
    good = build_record(card_for(HardenedDevOpsAgent, suite), specs=suite, at="2026-08-23T10:00:00")
    bad = build_record(card_for(NaiveDevOpsAgent, suite), specs=suite, at="2026-08-23T11:00:00")

    diff = diff_runs(good, bad)
    assert diff.regressed is True
    assert diff.new_failures
    assert diff.fixed == []


def test_runs_of_different_suites_are_not_comparable():
    # Diffing across suites would produce a confident, meaningless answer.
    full = expand(builtin_seeds(), pairs=False)
    partial = full[:8]
    a = build_record(card_for(NaiveDevOpsAgent, full), specs=full, at="2026-08-23T10:00:00")
    b = build_record(card_for(NaiveDevOpsAgent, partial), specs=partial, at="2026-08-23T11:00:00")
    assert diff_runs(a, b).comparable is False


def test_trace_drift_is_surfaced_not_hidden():
    """Same verdict, different trace.

    Usually a nondeterministic agent. Reporting it is the honest move: if runs
    are drifting, the regression signal is weaker than it looks.
    """
    suite = expand(builtin_seeds(), pairs=False)
    card = card_for(NaiveDevOpsAgent, suite)
    baseline = build_record(card, specs=suite, at="2026-08-23T10:00:00")

    current = build_record(card, specs=suite, at="2026-08-23T11:00:00")
    for outcome in current.outcomes.values():
        if outcome.passed:
            outcome.fingerprint = "deadbeefdeadbeef"
            break

    diff = diff_runs(baseline, current)
    assert len(diff.drifted) == 1
    assert diff.regressed is False


def test_added_and_removed_scenarios_are_tracked():
    suite = expand(builtin_seeds(), pairs=False)
    card = card_for(NaiveDevOpsAgent, suite)
    full = build_record(card, specs=suite, at="2026-08-23T10:00:00")

    trimmed = build_record(card, specs=suite, at="2026-08-23T11:00:00")
    dropped = sorted(trimmed.outcomes)[0]
    del trimmed.outcomes[dropped]

    diff = diff_runs(full, trimmed)
    assert diff.removed == [dropped]
    assert diff.added == []


def test_history_round_trips_through_jsonl(tmp_path):
    suite = expand(builtin_seeds(), pairs=False)
    path = tmp_path / "history.jsonl"
    first = build_record(card_for(NaiveDevOpsAgent, suite), specs=suite, at="2026-08-23T10:00:00")
    second = build_record(card_for(HardenedDevOpsAgent, suite), specs=suite, at="2026-08-23T11:00:00")
    append_run(first, path)
    append_run(second, path)

    runs = load_runs(path)
    assert len(runs) == 2
    assert runs[0].outcomes.keys() == first.outcomes.keys()
    assert runs[1].pass_rate == second.pass_rate


def test_previous_run_filters_by_agent(tmp_path):
    suite = expand(builtin_seeds(), pairs=False)
    path = tmp_path / "h.jsonl"
    naive = build_record(card_for(NaiveDevOpsAgent, suite), specs=suite, at="2026-08-23T10:00:00")
    hardened = build_record(card_for(HardenedDevOpsAgent, suite), specs=suite, at="2026-08-23T11:00:00")
    append_run(naive, path)
    append_run(hardened, path)

    assert previous_run(path).agent_id == hardened.agent_id
    assert previous_run(path, agent_id=naive.agent_id).run_id == naive.run_id
    assert previous_run(path, agent_id="nobody") is None


def test_missing_history_file_is_not_an_error(tmp_path):
    assert load_runs(tmp_path / "nope.jsonl") == []
    assert previous_run(tmp_path / "nope.jsonl") is None


def test_run_ids_do_not_collide_within_one_second():
    # Timestamps have second granularity, so the outcomes must contribute to the
    # id or two runs in the same second become indistinguishable in the history.
    suite = expand(builtin_seeds(), pairs=False)
    stamp = "2026-08-23T10:00:00"
    a = build_record(card_for(NaiveDevOpsAgent, suite), specs=suite, at=stamp)
    b = build_record(card_for(HardenedDevOpsAgent, suite), specs=suite, at=stamp)
    assert a.run_id != b.run_id


def test_identical_runs_reuse_their_id():
    suite = expand(builtin_seeds(), pairs=False)
    card = card_for(NaiveDevOpsAgent, suite)
    stamp = "2026-08-23T10:00:00"
    assert (
        build_record(card, specs=suite, at=stamp).run_id
        == build_record(card, specs=suite, at=stamp).run_id
    )
