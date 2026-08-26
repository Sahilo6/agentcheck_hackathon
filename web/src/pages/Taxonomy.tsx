import { data } from "../data";
import { SeverityPill } from "../components/common";
import type { Severity, TaxonomyEntry } from "../types";

const ORDER: Severity[] = ["critical", "high", "medium", "low"];

export default function Taxonomy() {
  // Identical across runs; take it from the first.
  const taxonomy = data.runs[0].taxonomy;
  const modes = Object.entries(taxonomy).sort(
    ([, a], [, b]) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity),
  );
  const deterministic = modes.filter(([, m]) => m.deterministic).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Failure taxonomy</h1>
        <p className="mt-1 text-slate-400">
          Ten ways an agent fails at a task, and how each one is detected.
        </p>
      </div>

      {/* The page a sceptical judge opens. It answers "isn't this just an LLM
          wrapper?" before the question is asked. */}
      <div className="panel border-l-4 border-l-pass p-6">
        <div className="text-2xl font-semibold text-pass">
          {deterministic} of {modes.length} modes need no language model
        </div>
        <p className="mt-2 text-slate-400">
          Each is a property check against recorded world state. That is possible
          because the harness owns the environment the agent runs in, so ground
          truth is known rather than inferred.
        </p>
      </div>

      <div className="space-y-3">
        {modes.map(([id, mode]) => (
          <ModeCard key={id} id={id} mode={mode} />
        ))}
      </div>

      <p className="text-sm text-slate-500">
        Full specification, including what this taxonomy deliberately does not
        cover, is in <span className="mono">docs/TAXONOMY.md</span>.
      </p>
    </div>
  );
}

function ModeCard({ id, mode }: { id: string; mode: TaxonomyEntry }) {
  return (
    <div className="panel p-5">
      <div className="flex flex-wrap items-center gap-3">
        <SeverityPill severity={mode.severity} />
        <span className="mono text-lg text-slate-100">{id}</span>
        <span className="text-slate-400">{mode.title}</span>
        {mode.deterministic && (
          <span className="ml-auto rounded bg-pass/10 px-2.5 py-0.5 text-xs text-pass">
            no LLM
          </span>
        )}
      </div>
      <p className="mt-3 text-sm italic text-slate-400">Fix: {mode.remediation}</p>
    </div>
  );
}
