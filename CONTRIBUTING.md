# Contributing to agentcheck

Thanks for looking. This is a young project and the shape of it is still
negotiable, so questions and disagreement are as useful as patches.

## Getting set up

```bash
git clone https://github.com/Sahilo6/agentcheck_hackathon
cd agentcheck_hackathon
pip install -e ".[dev]"
python -m pytest -q
```

No dependencies for the core, and none needed to run the tests. If something
here requires a network connection or an API key to work, that is a bug.

## The one rule

**Precision over recall.** A detector that misses a real failure is survivable. A
detector that reports a failure that did not happen is not: one bad finding makes
every other finding in the report suspect, and a reliability tool nobody trusts
gets switched off.

Concretely, this means every detector change needs a test proving a *correct*
agent does not trip it. `test_demo_suite.py` asserts that a well-behaved agent
produces **zero** findings across every scenario in both domains. If your change
breaks that, the change is wrong, not the test.

## Things worth knowing before you change something

**Scenarios are specs, not prompts.** A scenario carries a machine-checkable
postcondition. If you find yourself wanting to judge an outcome by reading it,
that is a sign the scenario needs a better postcondition, not that we need a
model in the loop.

**Detectors do not call models.** All ten are property checks over recorded
state. If you have a failure mode that genuinely needs judgement, it is welcome,
but it must be reported as model-assisted so a reader can tell measurement from
opinion. See `LLM_ASSISTED` in `detect/taxonomy.py`.

**Mutations change pressure, never the correct answer.** A mutation may make a
task harder to get right. It must not make a previously-correct action wrong, or
a failure no longer means the agent failed. There is a parametrized test
enforcing this over every mutation.

**Runs must stay reproducible.** Same scenario and same agent produce a
byte-identical trace. Anything that leaks real time, randomness, or host state
into a run breaks regression tracking, which then reports noise as regressions.
`world/clock.py` exists for this reason.

## Adding a failure mode

1. Read `docs/TAXONOMY.md`, particularly *Extending it*. A new mode has to be
   distinct, checkable, and actionable.
2. Add it to `TAXONOMY` in `detect/taxonomy.py` with remediation guidance.
3. Write the detector in `detect/detectors.py` as a pure function of
   `(spec, trace)`, and register it in `DETECTORS`.
4. Tests: one that reproduces the failure with a `ScriptedAgent`, and one that
   proves a correct agent does not trip it.
5. Add it to `docs/TAXONOMY.md`. `test_docs.py` will fail until you do, on
   purpose.

## Adding a domain

A domain is a toolkit plus seed scenarios. See `toolkits/support.py` and the
support section of `gen/builtin.py` for a worked example.

Adding one is the best way to find where the engine is secretly shaped around an
existing domain. Building the support domain surfaced three such places, all of
which were real bugs.

Every seed needs to satisfy the gate in `gen/seeds.py`: a normal task must not
already be satisfied at the start, and a trap must be. `test_demo_suite.py`
checks this for every shipped seed.

## Style

Match the surrounding code. Comments explain *why*, not *what*; the code already
says what it does. If a decision looks arbitrary, a sentence about the
alternative you rejected is worth more than a description of the mechanism.

## Good first issues

- A new mutation for the ladder. `injected_tool_output` is a good model to read.
- Domain vocabulary for `hallucinated_success`. The claim words in
  `_CLAIM_OPS` are English and ops-flavoured; a domain with different verbs will
  slip past it, which is exactly how we missed a support agent lying about
  emails until we built that domain.
- A third domain. Data analysis, code review, and scheduling all have
  interesting blast radii.
- Native tool-calling coverage for more providers in `llm.py`.

## Reporting a false positive

The most valuable bug report this project can get. Please include the scenario
id, the finding, and why the agent's behaviour was actually correct. A trace
fingerprint makes it reproducible.
