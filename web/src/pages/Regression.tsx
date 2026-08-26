import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Empty, StatCard } from "../components/common";
import { data, diff, domains, runsFor } from "../data";

export default function Regression() {
  const [domain, setDomain] = useState(domains[0]);
  const runs = runsFor(domain);

  if (runs.length < 2) return <Empty>Need two runs of the same suite to compare.</Empty>;

  const [before, after] = runs;
  const result = diff(before, after);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Regression</h1>
          <p className="mt-1 text-slate-400">
            The identical {data.domains[domain].scenarios} scenarios, before and
            after adding guardrails.
          </p>
        </div>
        <div className="flex rounded-lg border border-ink-600 bg-ink-850 p-1">
          {domains.map((option) => (
            <button
              key={option}
              onClick={() => setDomain(option)}
              className={`rounded-md px-3.5 py-1.5 font-mono text-sm transition ${
                option === domain ? "bg-ink-700 text-slate-100" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      <div className="panel flex flex-wrap items-center justify-center gap-6 p-8 text-center">
        <div>
          <div className="mono text-sm text-slate-500">{before.agent_id}</div>
          <div className="text-5xl font-semibold text-critical">
            {Math.round(before.pass_rate * 100)}%
          </div>
        </div>
        <ArrowRight size={30} className="text-slate-600" />
        <div>
          <div className="mono text-sm text-slate-500">{after.agent_id}</div>
          <div className="text-5xl font-semibold text-pass">
            {Math.round(after.pass_rate * 100)}%
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard value={result.fixed.length} label="fixed" accent="#22c55e" />
        <StatCard
          value={result.newFailures.length}
          label="new failures"
          accent={result.newFailures.length ? "#ef4444" : "#22c55e"}
          hint={result.newFailures.length === 0 ? "nothing broke" : undefined}
        />
        <StatCard value={result.stillFailing.length} label="still failing" />
      </div>

      {/* The claim only holds because runs are deterministic. Worth stating on
          the page rather than assuming a viewer infers it. */}
      <div className="panel border-l-4 border-l-pass p-5 text-slate-300">
        Both runs executed the same suite at the same seed, so every scenario
        that changed verdict genuinely changed. None of this is resampling noise.
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Column
          title="Fixed"
          colour="#22c55e"
          ids={result.fixed}
          domain={domain}
          agentId={before.agent_id}
        />
        <Column
          title="New failures"
          colour="#ef4444"
          ids={result.newFailures}
          domain={domain}
          agentId={after.agent_id}
          empty="Nothing regressed."
        />
        <Column
          title="Still failing"
          colour="#eab308"
          ids={result.stillFailing}
          domain={domain}
          agentId={after.agent_id}
          empty="Nothing left failing."
        />
      </div>
    </div>
  );
}

function Column({
  title,
  colour,
  ids,
  domain,
  agentId,
  empty = "Nothing here.",
}: {
  title: string;
  colour: string;
  ids: string[];
  domain: string;
  agentId: string;
  empty?: string;
}) {
  return (
    <div className="panel overflow-hidden">
      <div className="border-b border-ink-600 px-5 py-3">
        <span className="font-semibold" style={{ color: colour }}>
          {title}
        </span>
        <span className="ml-2 text-slate-500">{ids.length}</span>
      </div>
      {ids.length === 0 ? (
        <div className="px-5 py-8 text-center text-sm text-slate-500">{empty}</div>
      ) : (
        <ul className="max-h-[420px] overflow-y-auto">
          {ids.map((id) => (
            <li key={id} className="border-b border-ink-700 last:border-0">
              <Link
                to={`/scenario/${domain}/${agentId}/${encodeURIComponent(id)}`}
                // Scenario ids are long unbroken tokens; without break-all they
                // overflow the column and get clipped at the panel edge.
                className="block break-all px-5 py-2 font-mono text-sm leading-snug text-slate-300 hover:bg-ink-850"
              >
                {id}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
