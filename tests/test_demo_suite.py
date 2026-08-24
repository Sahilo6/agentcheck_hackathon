"""Guards on the end-to-end demo, across both shipped domains.

These lock in the claims made on stage. If a change to a detector, a mutation,
or a seed breaks either one, this fails before the demo does.

Running the same assertions over two domains is the point: DevOps blast radius
is measured in paths, support blast radius is measured in records and money, and
the engine shares nothing between them except the harness.
"""

import pytest

from agentcheck.engine import run_suite
from agentcheck.gen.builtin import SEEDS_BY_DOMAIN, builtin_seeds
from agentcheck.gen.mutations import expand
from agentcheck.gen.seeds import _already_satisfied
from agentcheck.toolkits import toolset_for
from agentcheck.demo.devops import HardenedDevOpsAgent, NaiveDevOpsAgent
from agentcheck.demo.support import HardenedSupportAgent, NaiveSupportAgent

DOMAINS = {
    "devops": (NaiveDevOpsAgent, HardenedDevOpsAgent),
    "support": (NaiveSupportAgent, HardenedSupportAgent),
}

_cache: dict = {}


def run_for(domain, which):
    key = (domain, which)
    if key not in _cache:
        suite = expand(builtin_seeds(domain))
        naive, hardened = DOMAINS[domain]
        factory = naive if which == "naive" else hardened
        _cache[key] = (suite, run_suite(suite, factory, toolset_for(domain)))
    return _cache[key]


@pytest.mark.parametrize("domain", sorted(DOMAINS))
def test_suite_is_large_enough_to_be_worth_running(domain):
    suite, _ = run_for(domain, "naive")
    assert len(suite) >= 150


@pytest.mark.parametrize("domain", sorted(DOMAINS))
def test_hardened_agent_produces_no_findings_at_all(domain):
    """The no-false-positives guarantee.

    A correct agent must survive every adversarial mutation without tripping a
    single detector. This is the most important assertion in the project: one
    bogus finding on stage and every real finding stops being believable.
    """
    _, card = run_for(domain, "hardened")
    assert card.findings_total_is_zero(), [
        (r.spec.id, [f.mode for f in r.findings]) for r in card.failures()
    ]


@pytest.mark.parametrize("domain", sorted(DOMAINS))
def test_naive_agent_fails_a_large_share(domain):
    _, card = run_for(domain, "naive")
    assert card.pass_rate < 0.6, f"{domain}: naive scored {card.pass_rate:.0%}"


@pytest.mark.parametrize("domain", sorted(DOMAINS))
def test_the_gap_between_versions_is_the_story(domain):
    _, naive = run_for(domain, "naive")
    _, hardened = run_for(domain, "hardened")
    assert hardened.pass_rate - naive.pass_rate > 0.35


@pytest.mark.parametrize("domain", sorted(DOMAINS))
def test_hand_written_style_tests_would_have_missed_most_of_this(domain):
    """The framing for demo beat 1.

    Unmutated seeds are the tests a person writes by hand. They must pass at a
    higher rate than the mutated suite, or the pitch does not hold.
    """
    _, card = run_for(domain, "naive")
    base = [r for r in card.results if not r.spec.mutations]
    mutated = [r for r in card.results if r.spec.mutations]
    base_rate = sum(r.passed for r in base) / len(base)
    mutated_rate = sum(r.passed for r in mutated) / len(mutated)
    assert base_rate > mutated_rate, (
        f"{domain}: base {base_rate:.0%} vs mutated {mutated_rate:.0%}"
    )


@pytest.mark.parametrize("domain", sorted(DOMAINS))
def test_every_finding_is_decided_without_a_model(domain):
    _, card = run_for(domain, "naive")
    det, total = card.deterministic_finding_share()
    assert total > 0 and det == total


@pytest.mark.parametrize("domain", sorted(DOMAINS))
def test_the_suite_is_reproducible(domain):
    suite, _ = run_for(domain, "naive")
    naive, _ = DOMAINS[domain]
    a = run_suite(suite, naive, toolset_for(domain))
    b = run_suite(suite, naive, toolset_for(domain))
    assert [r.trace.fingerprint() for r in a.results] == [
        r.trace.fingerprint() for r in b.results
    ]


# -- seed hygiene, both domains --------------------------------------------


@pytest.mark.parametrize(
    "seed",
    [s for d in sorted(SEEDS_BY_DOMAIN) for s in SEEDS_BY_DOMAIN[d]],
    ids=lambda s: f"{s.domain}-{s.id}",
)
def test_seed_gate_matches_its_kind(seed):
    satisfied = _already_satisfied(seed)
    if seed.benign:
        assert not satisfied, f"{seed.id} passes before the agent acts"
    else:
        # A trap's postcondition is a preservation invariant: true at t=0, and
        # it must survive. Requiring it false would make traps unexpressible.
        assert satisfied, f"{seed.id} is a trap that a correct refusal would fail"


def test_both_domains_ship_a_trap():
    for domain in SEEDS_BY_DOMAIN:
        assert any(not s.benign for s in SEEDS_BY_DOMAIN[domain]), domain
