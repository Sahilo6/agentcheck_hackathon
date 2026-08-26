# agentcheck dashboard

The web view of a reliability run. Reads `fixtures/sample-scorecard.json`, which
is real output from the Python engine.

```bash
cd web
npm install
npm run dev        # http://localhost:5173
npm run build      # static files in dist/
npm run preview    # serve the build
```

## Why it works offline

The fixture is bundled into the build rather than fetched, and routing is
hash-based. That means the built `dist/` opens straight from the filesystem with
no server and no network, which is the same constraint the HTML report has:
conference wifi fails, and the demo cannot depend on it.

## Pages

| Route | What it is for |
|---|---|
| `/scorecard` | The opening shot. Pass rate, severity split, failure modes, every scenario |
| `/scenario/:domain/:agent/:id` | The drill-down, including the claimed-vs-performed panel |
| `/regression` | Before and after guardrails: fixed, new failures, still failing |
| `/taxonomy` | The ten failure modes. The page a sceptical judge opens |

## The component that matters

`ClaimedVsPerformed` in `src/pages/ScenarioDetail.tsx`. It puts what the agent
*said* beside what the world actually *recorded*. When those disagree, the tool
has proven a lie by checking state rather than asking a model, and that contrast
is the whole argument in one view.

If time runs short, cut pages in this order: Taxonomy, Regression, polish. Never
cut the trace viewer.

## Refreshing the data

```bash
python3 examples/make_sample_scorecard.py > web/fixtures/sample-scorecard.json
```

The fixture is the contract. If a field in `src/types.ts` stops matching it, the
fixture is right and the types are stale.

## Notes for working on it

- **Never invent numbers.** Everything on screen comes from the fixture. Made-up
  demo data is the fastest way to lose a technical audience.
- **Design for a projector.** Base font is 17px on purpose. A dense dashboard
  that looks sharp on a laptop is unreadable from the back of a room.
- **No entry animations on the numbers.** A reader should take in the scorecard
  the instant it loads. Chart animation is explicitly disabled for this reason,
  and it also stops bars vanishing from screenshots.
- Severity colours are fixed across every view: critical `#ef4444`, high
  `#f97316`, medium `#eab308`, low `#64748b`. A colour always means one thing.
