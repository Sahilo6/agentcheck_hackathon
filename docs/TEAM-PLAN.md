# agentcheck — team plan

**OOSC 4.0, IIIT Allahabad — 28–30 Aug 2026. Problem Statement 4.**
Two people. **A = Sahil** (engine). **B = teammate** (frontend, deck, demo assets).

The two tracks are decoupled by a single contract: `web/fixtures/sample-scorecard.json`.
B builds entirely against that file and never has to wait for A. When the schema
changes, A regenerates it and B pulls.

---

## Read this first

**`docs/PROGRESS.md`** (and its printable twin `docs/PROGRESS.pdf`) is the running
plain-language log of what has been built and what it means. It assumes no
knowledge of the code. Sahil updates it on every commit, so it is always the
fastest way to catch up after being away for a day.

Rebuild the PDF after editing the markdown:

```bash
python3 docs/build_progress.py
```

---

## Ground rules

1. **Feature freeze end of 27 Aug.** Hackathons are lost on the last day by teams
   still writing code. After the freeze, only rehearsal, deck, and bug fixes.
2. **Nothing live on the critical path of the demo.** Every number on stage comes
   from a cached run. Venue wifi will fail; assume it.
3. **Precision over recall, always.** One false finding on stage and the whole
   report stops being believable. A detector that misses something is survivable;
   one that cries wolf is not.
4. **Branch per feature, PR into `main`.** Both of us review. Keeps the git
   history presentable — it is an open-source conference and judges may look.
5. **Never commit an API key.** `.env` is gitignored. Use env vars.

---

## Day by day

### Fri 22 Aug — foundations ✅ DONE (A)

- [x] Repo, packaging, Apache-2.0, `.gitignore`
- [x] `spec/` — scenarios as checkable specs with a closed condition language
- [x] `world/` — stateful mock world, mutation journal, deterministic clock
- [x] `runtime/` — tools + JSON-Schema validation, agent protocol, runner loop
- [x] `detect/` — all 10 failure modes, every one a property check
- [x] `score/` — scorecard aggregation
- [x] 73 tests passing; naive agent 38%, hardened agent 100% on the same suite
- [x] `web/fixtures/sample-scorecard.json` — the contract for B

**B, today:** read this doc + `docs/FRONTEND-BRIEF.md`, scaffold the app, get the
fixture rendering as a raw table. Nothing pretty yet — just prove the data flows.

---

### Sat 23 Aug — scenario generation, CLI, reports, 2nd domain ✅ DONE (A)

Ran a day ahead, so Sunday and Monday's engine work landed today too.

- [x] `gen/mutations.py` — 8 adversarial mutations, composed in pairs, all in code
- [x] `gen/builtin.py` — hand-written seeds so the tool runs with **no API key**
- [x] `gen/seeds.py` + `llm.py` — optional LLM generation, cached, provider-agnostic
- [x] `history/` — JSONL run store, regression diff, CI gate verified both directions
- [x] `report/` — self-contained HTML, JSON, JUnit XML
- [x] `cli.py` — `demo | run | scenarios | taxonomy | mutations | generate`
- [x] GitHub Action + repo CI on 3.11/3.12/3.13
- [x] **Second domain: customer support.** Forced three real generality fixes
- [x] 211 tests passing
- [x] `docs/PROGRESS.md` + PDF — the plain-language log

**B, today:** app shell (nav, routing, dark theme). Scorecard page: pass rate,
severity strip, `by_mode` chart, scenario table. The fixture now has **four** runs
(naive + hardened × devops + support), so pull before you start.

---

### Sun 24 Aug — MCP adapter ✅ DONE early (A) · trace viewer (B)

**A**
- [x] MCP server adapter — `agentcheck mcp-serve` exposes a scenario's mock world
      over MCP, so any MCP-speaking agent is testable with no adapter written
- [x] `agentcheck score` — score a recorded MCP run offline
- [x] Equivalence proven: all 347 scenarios across both domains produce identical
      fingerprints in-process and over MCP
- [x] 237 tests passing

**B**
- [ ] **Trace viewer** — the drill-down for demo beats 5 and 6. Step-by-step tool
      calls, args, results, and what the agent *claimed* beside what it did
- [ ] Finding cards: severity, taxonomy title, summary, expandable evidence

---

### Mon 25 Aug — real agents (A) · regression view (B)

**A**
- [ ] LLM-backed agent adapter (Groq free tier, **fresh key**)
- [ ] Run real naive vs hardened agents; cache the traces
- [ ] Hunt false positives against real model output
- [ ] Stretch: run against a real third-party open-source agent

**B**
- [ ] Regression view: v1 vs v2, fixed / new / still-failing
- [ ] Taxonomy page (the credibility page judges will open)

---

### Tue 26 Aug — real agents (A) · polish (B)

**A**
- [ ] LLM-backed agent adapter (Groq free tier, provider-agnostic, **fresh key**)
- [ ] Run the real naive vs hardened agents; record and cache the traces
- [ ] Tune detector thresholds against real output — hunt false positives
- [ ] Stretch: run against a real third-party open-source agent

**B**
- [ ] Visual polish, responsive check, README demo gif
- [ ] Wire the dashboard to real cached runs

---

### Wed 27 Aug — 🔒 FREEZE. Rehearse.

- [ ] **Feature freeze at noon.** Bug fixes only after this.
- [ ] Full demo rehearsal ×3, timed
- [ ] **Record the backup video** — end to end, wifi off
- [ ] Deck (see structure below)
- [ ] README, taxonomy spec doc, CONTRIBUTING, a few good-first-issues
- [ ] Repo public

---

### 28–30 Aug — present

---

## The demo (8 beats, ~4 min)

1. **"Here's how teams test agents today."** 5 hand-written prompts, all green. Ship it.
2. `agentcheck generate` → reads tool schemas → 200+ scenarios. Show one spec.
3. `agentcheck run` → live progress in the mock world.
4. **Scorecard: ~38% pass.** Taxonomy breakdown. Let the room react.
5. **Drill in:** under time pressure it deleted `/var/log` — the parent directory.
   Replay the trace to the exact step.
6. **The mic-drop:** it reported *"restarted the api service"*. The journal shows
   `restart_service` was never called. **Caught by a state check, not an opinion.**
7. **Close the loop:** add guardrails → re-run the *identical* scenarios
   (deterministic!) → **100%**. Regression view shows what got fixed.
8. `agentcheck ci` → GitHub Action failing a PR.

Arc: *today's testing is theatre → here's what's really broken → here's proof →
here's the fix working → here's it in your CI tomorrow.*

## Deck (8 slides)

1. Title — "agentcheck: CI for autonomous agents"
2. The problem — 70% real-world task failure; teams test with 5 prompts
3. Why LLM-judges are not enough — *"how do you know the judge is right?"*
4. **Our thesis** — own the environment; evaluate the trajectory, not the answer
5. **The taxonomy table** — 10 modes, all 10 deterministic ← the credibility slide
6. Architecture — spec → runner → world → trace → detectors → scorecard
7. Live demo
8. Open source: Apache-2.0, `pip install agentcheck`, GitHub Action, taxonomy spec

## Anticipated questions

| Question | Answer |
|---|---|
| "Isn't this just an LLM wrapper?" | All 10 detectors are property checks. The only LLM call is scenario *generation*, and it is cached. |
| "Does it only work on your demo agent?" | Two domains shipped (devops + support) that share nothing but the harness. Building the second one exposed and fixed three places where the engine was secretly file-shaped. |
| "How do you know the mock is realistic?" | We don't claim sim-to-real. We claim it is *controlled*, which is what makes the oracle possible — same reason OS and DB test suites use fixtures. |
| "What about nondeterministic models?" | The fingerprint changes when the agent varies, and we report that as a finding rather than hiding it. |
| "How much did AI write?" | Be straight about it. Then defend any design decision on the spot — that is the actual test. |
