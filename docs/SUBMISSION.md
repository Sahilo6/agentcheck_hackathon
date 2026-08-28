# Submission checklist

**OOSC 4.0 · IIIT Allahabad · event runs 28–30 Aug 2026**
Written 26 Aug. Sahil = S, Neerav = N.

---

## 0. Confirmed requirements

Teams work remotely and submit a functional prototype. Before the deadline:

| # | Required | Status |
|---|---|---|
| 1 | **Prototype link** — live/hosted if possible, otherwise clear local-run instructions in the README | Hosting built, needs enabling. README rewritten with a one-minute local path. |
| 2 | **GitHub repo** with a well-documented README | Done, repo still private |
| 3 | **Demo video, MANDATORY**, max 10 minutes | Scripted, not recorded |

**Judged on:** innovation, technical implementation, feasibility, scalability,
code quality, documentation, presentation.

**Late submissions are not accepted.**

### What each criterion is answered by

| Criterion | Where it is answered |
|---|---|
| Innovation | The thesis: property checks over trajectories, not a model grading a model |
| Technical implementation | Deterministic mock world, 10 detectors, MCP equivalence, record/replay |
| Feasibility | `pip install` then one command, no API key, zero dependencies |
| Scalability | README *Design decisions* section: combinatorial expansion, independent scenarios, offline detection |
| Code quality | 303 tests, CI on three Python versions, clean-venv packaging job |
| Documentation | README, `TAXONOMY.md` as a standalone spec, `PROGRESS.md`, `CONTRIBUTING.md` |
| Presentation | The video, and `docs/deck.html` |

**Still unknown:** the exact deadline date and time. Find it on the Unstop
submission tab and put it at the top of this file.

---

## 1. What is already done

Do not redo any of this.

| | Where |
|---|---|
| Working engine, 303 tests | the repo |
| CLI: `demo`, `run`, `mcp-serve`, `score`, `taxonomy`, `mutations`, `scenarios` | `agentcheck/cli.py` |
| Two domains, both hardened agents produce zero findings | `agentcheck/demo/` |
| HTML / JSON / JUnit reports, regression gating, GitHub Action | `agentcheck/report/`, `action.yml` |
| README, taxonomy spec, CONTRIBUTING, LICENSE | repo root, `docs/` |
| Plain-language project log + PDF | `docs/PROGRESS.md`, `.pdf` |
| Dashboard, four pages | branch `feat/dashboard` |
| Deck, ten slides | `docs/deck.html` |
| Automated demo rehearsal, ten beats, offline | `scripts/rehearse.py` |

---

## 2. Needed from Sahil

### 2a. Groq API key — **tonight, 15 minutes**

The only item that materially strengthens the pitch. Every number we show comes
from agents we wrote. A judge can fairly ask *"of course it finds bugs, you wrote
the buggy agent."* Running against a real model answers that.

```bash
# free, no card: https://console.groq.com/keys
# .env is gitignored; a plain `export` does not survive into a new shell
echo 'GROQ_API_KEY=gsk_your_key' > .env
export $(grep -v '^#' .env | xargs)

python3 -m agentcheck.cli run --agent llm --provider groq \
  --record runs/llm-devops.jsonl --out reports/llm-devops.html

python3 -m agentcheck.cli run --agent llm --provider groq --domain support \
  --record runs/llm-support.jsonl --out reports/llm-support.html
```

Then send me the output and I will fold the real numbers into the deck, the
README and the progress log. Recorded traces replay offline forever, so this adds
no risk to the demo.

**Never paste the key into a chat or commit it.** `.env` and `runs/` are
gitignored; use the env var.

### 2b. Decide on the dashboard branch — **tonight**

`feat/dashboard` has a working four-page dashboard. Neerav may have his own.
Pick one. If his is further along, bin mine; if not, merge mine and let him
restyle it. Either is fine, but decide before the freeze so nobody polishes a
version that gets dropped.

### 2c. Make the repo public and turn on Pages — **before submitting**

It is an open-source conference, and the submission asks for a hosted link.

```bash
# check no key was ever committed
git log -p --all | grep -iE "gsk_|sk-[A-Za-z0-9]{20}" | head     # want: empty

gh repo edit Sahilo6/agentcheck_hackathon --visibility public \
  --accept-visibility-change-consequences
```

Then in the browser: **Settings → Pages → Source → GitHub Actions**. The
`pages.yml` workflow deploys on every push to `main` and publishes the dashboard,
the deck, and two real reports at:

```
https://sahilo6.github.io/agentcheck_hackathon/
```

That URL is the **prototype link** for the submission form. Check it loads before
you paste it anywhere.

### 2d. Push everything — **before the freeze**

```bash
git checkout main && git merge feat/dashboard   # if keeping the dashboard
python3 -m pytest -q && python3 scripts/rehearse.py
git push origin main
```

### 2e. Fill in the submission form — **by the confirmed deadline**

I have drafted the text you will likely need in section 5 below.

---

## 3. Needed from Neerav

### 3a. Design pass, dashboard **or** deck — **by 27 Aug noon**

Both exist and work. Neither is designed by someone who designs. Pick **one** and
make it good; doing both badly is worse than doing one well.

My honest read: **the deck matters more.** It is on screen for most of the
judging, whereas the dashboard appears for maybe forty seconds. The deck is one
self-contained HTML file (`docs/deck.html`), or lift the content into Figma,
Canva or Slides if that is faster.

If touching the deck HTML: the numbers are generated by
`python3 docs/build_deck.py`, so change the styling, not the figures. If it moves
to Slides, the figures must be copied faithfully — `scripts/rehearse.py` checks
the HTML deck against the data, and nothing checks a Slides deck.

### 3b. The demo video — **MANDATORY, 27 Aug afternoon**

Cap is **10 minutes**, not 3. Aim for 8:00–8:30.

**Full shot-by-shot script with timings: [docs/VIDEO-SCRIPT.md](VIDEO-SCRIPT.md).**
Follow it section by section; it maps each segment to the criteria it answers.

Record with wifi off. QuickTime → File → New Screen Recording is enough.

Upload unlisted to YouTube or Drive, then **check the link from a logged-out
browser** before submitting. A permissions failure here is a rejected submission.

### 3c. Read the project log — **tonight, 20 minutes**

`docs/PROGRESS.pdf`. Written in plain language specifically so he can answer
questions about parts he did not build. If a judge asks him something and he
cannot answer, that costs us more than a rough UI does.

---

## 4. Needed from both — 27 Aug

- [ ] **Feature freeze at noon.** Bug fixes only after.
- [ ] `python3 scripts/rehearse.py` → all ten beats green
- [ ] Rehearse the live demo **three times, timed**, wifi off
- [ ] Agree who says what. Two people talking over each other reads worse than
      one person presenting.
- [ ] Decide the answer to *"how much of this did AI write?"* in advance. Be
      straight about it, then defend any design decision on the spot. That is the
      real test, and evasiveness fails it harder than the honest answer does.
- [ ] Both laptops charged, demo working on **both**, backup video on both

---

## 5. Draft submission text

Adjust once the real form is known.

**One-line pitch**

> Continuous integration for autonomous agents: generate adversarial scenarios,
> run them in a deterministic mock world, and prove what the agent actually did.

**Abstract (~100 words)**

> Teams ship AI agents against a handful of hand-written prompts, so real failure
> modes surface in production. The usual fix is to have one model grade another,
> which cannot answer the question "how do you know the grader is right?"
>
> agentcheck takes a different position: an agent cannot be judged by its final
> answer, only by its trajectory, and judging trajectories rigorously means
> owning the environment. It runs agents inside a stateful mock world, records
> every state change, and classifies failures against a ten-mode taxonomy. All
> ten detectors are property checks; none calls a model. Runs are reproducible,
> so regressions are real signal rather than sampling noise.

**Key numbers** (all reproducible via `agentcheck demo`)

- 175 devops scenarios from 7 hand-written seeds, expanded by code, no API calls
- Naive agent 38% pass, 261 findings; the same agent with guardrails 100%, zero
- Second domain, customer support: 52% → 100%, same result
- Hand-written-style scenarios pass at 71%, their adversarial variants at 36%
- 10 of 10 failure modes decided without a language model
- 303 tests

**Links**

- Prototype: `https://sahilo6.github.io/agentcheck_hackathon/`
- Repo: `https://github.com/Sahilo6/agentcheck_hackathon`
- Video: _paste the unlisted link here once uploaded_
- Taxonomy spec: `docs/TAXONOMY.md`
- Try it: `pip install -e .` then `agentcheck demo` (no API key needed)

---

## 6. Timeline

| When | Who | What |
|---|---|---|
| **Tonight 26th** | S | Confirm the real requirements and deadline ← *unblocks everything* |
| Tonight 26th | S | Groq key, record real model runs, send me the output |
| Tonight 26th | S | Decide which dashboard survives |
| Tonight 26th | N | Read `docs/PROGRESS.pdf` |
| **27th morning** | N | Design pass on the deck (or the dashboard) |
| 27th morning | S | Fold real model numbers into deck, README, log |
| **27th noon** | both | 🔒 **FREEZE** |
| 27th afternoon | N | Record the demo video, wifi off |
| 27th afternoon | both | Rehearse ×3, timed |
| 27th evening | S | Repo public, push, submit |
| 28th–30th | both | Present |

**If the deadline turns out to be sooner than this:** submit what exists now. It
is complete and it works. The Groq run and the design passes make it stronger,
they do not make it valid.
