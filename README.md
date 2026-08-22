# agentcheck

**Continuous integration for autonomous agents.**

Generate realistic and adversarial scenarios for an agent, run them against a
stateful mock world, classify what went wrong against a documented taxonomy, and
track reliability across versions.

Built for [OOSC 4.0](https://oosc.iiita.ac.in/), IIIT Allahabad — Problem
Statement 4: *AI Agent Evaluation and Reliability Engine*.

---

## The premise

Teams ship agents against a handful of hand-written test prompts, so real failure
modes — tool-call loops, hallucinated confidence, unsafe destructive actions,
silent goal drift — only surface in production.

The usual response is to have an LLM write test prompts and another LLM score the
answers. That runs into one question it cannot answer: *how do you know the judge
is right?*

agentcheck takes a different position:

> **An agent cannot be evaluated from its final answer. Its trajectory has to be
> evaluated — and doing that rigorously means owning the environment. Once you own
> the environment, most failure detection needs no model at all: it is a property
> check against known ground truth.**

Three things follow, and a wrapper around an LLM judge cannot have any of them:

1. **Determinism.** Same scenario, same seed, same mock responses produce a
   byte-identical trace. Reruns are comparable, so regression tracking is signal
   rather than sampling noise.
2. **Programmatic oracles.** Because we control the world, we know the truth. We
   know the file still exists. We know `restart_service` was never called. So *"the
   agent said it restarted the service"* becomes a state check, not an opinion.
3. **Safety.** Destructive behaviour can only be tested at all if nothing real is
   destroyed.

**All 10 failure detectors are property checks. None of them calls a model.**

---

## Status

Early. The engine, mock world, detectors, and scorecard work end to end and are
covered by tests. Scenario generation, reports, history, CLI, and the web
dashboard are in progress.

```
$ python3 -m pytest -q
73 passed
```

---

## The failure taxonomy

| Mode | Detected by | Severity |
|---|---|---|
| `destructive_action` | irreversible tool called outside the task's authorised scope | critical |
| `hallucinated_success` | completion claimed, but the journal shows the action never happened | high |
| `goal_drift` | entities mutated outside the task's declared scope | high |
| `unsafe_argument` | traversal, wildcard delete, filesystem root | high |
| `task_incomplete` | postcondition unmet at end of run | medium |
| `tool_loop` | same call with same arguments repeated without progress | medium |
| `fabricated_data` | summary cites a path no tool ever returned | medium |
| `wrong_refusal` | declined a benign in-scope task without acting | medium |
| `schema_violation` | tool called with arguments its schema rejects | low |
| `budget_exceeded` | hit the step or call ceiling before finishing | low |

Full descriptions and remediation guidance live in
[`agentcheck/detect/taxonomy.py`](agentcheck/detect/taxonomy.py).

---

## How it fits together

```
ScenarioSpec ──▶ runner ──▶ MockWorld ──▶ Trace ──▶ detectors ──▶ Scorecard
   (checkable      (step      (stateful,    (replayable   (10 property
    postcondition)  loop)      journaled)    evidence)      checks)
```

A scenario is **not a prompt**. It is a spec carrying a machine-checkable
postcondition, the tools it permits, the blast radius it authorises, and a budget.
That is what makes a verdict possible instead of a guess.

---

## Install

```bash
git clone https://github.com/<owner>/agentcheck
cd agentcheck
pip install -e ".[dev]"
python3 -m pytest -q
```

The core has **no dependencies**. A test harness that drags in a dependency tree
is a test harness people skip installing.

---

## License

Apache-2.0.
