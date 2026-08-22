"""Guards on the end-to-end demo.

These lock in the two claims made on stage. If a change to a detector, a
mutation, or a seed breaks either one, this fails before the demo does.
"""

import pytest

from agentcheck.engine import run_suite
from agentcheck.gen.builtin import builtin_seeds
from agentcheck.gen.mutations import expand
from agentcheck.toolkits.devops import devops_toolset
from demo_agents import HardenedDevOpsAgent, NaiveDevOpsAgent


@pytest.fixture(scope="module")
def suite():
    return expand(builtin_seeds())


@pytest.fixture(scope="module")
def naive(suite):
    return run_suite(suite, NaiveDevOpsAgent, devops_toolset())


@pytest.fixture(scope="module")
def hardened(suite):
    return run_suite(suite, HardenedDevOpsAgent, devops_toolset())


def test_suite_is_large_enough_to_be_worth_running(suite):
    assert len(suite) >= 150, "the mutation ladder should expand 7 seeds past 150 scenarios"


def test_hardened_agent_produces_no_findings_at_all(hardened):
    """The no-false-positives guarantee.

    A correct agent must survive every adversarial mutation without tripping a
    single detector. This is the most important assertion in the project: one
    bogus finding on stage and every real finding stops being believable.
    """
    assert hardened.findings_total_is_zero(), [
        (r.spec.id, [f.mode for f in r.findings]) for r in hardened.failures()
    ]


def test_naive_agent_fails_the_majority(naive):
    assert naive.pass_rate < 0.5, (
        f"the naive agent scored {naive.pass_rate:.0%}; the demo contrast needs it low"
    )


def test_the_gap_between_versions_is_the_story(naive, hardened):
    assert hardened.pass_rate - naive.pass_rate > 0.4


def test_hand_written_style_tests_would_have_missed_most_of_this(naive):
    """The framing for demo beat 1.

    Unmutated seeds are the tests a human would write by hand. If those pass at
    a much higher rate than the mutated suite, the pitch holds: happy-path
    testing hides these failures.
    """
    base = [r for r in naive.results if not r.spec.mutations]
    mutated = [r for r in naive.results if r.spec.mutations]
    base_rate = sum(r.passed for r in base) / len(base)
    mutated_rate = sum(r.passed for r in mutated) / len(mutated)
    assert base_rate > mutated_rate, (
        f"hand-written-style scenarios pass at {base_rate:.0%} vs {mutated_rate:.0%} mutated"
    )


def test_every_finding_is_decided_without_a_model(naive):
    det, total = naive.deterministic_finding_share()
    assert total > 0
    assert det == total, "a finding was produced by something other than a property check"


def test_the_suite_is_reproducible(suite):
    a = run_suite(suite, NaiveDevOpsAgent, devops_toolset())
    b = run_suite(suite, NaiveDevOpsAgent, devops_toolset())
    assert [r.trace.fingerprint() for r in a.results] == [
        r.trace.fingerprint() for r in b.results
    ]
