import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Chip, DeterministicBadge, SeverityPill, StatCard, severityHex } from "../components/common";
import { baseVsMutated, data, domains, runsFor, severityCounts } from "../data";
import type { Severity } from "../types";

export default function Scorecard() {
  const [domain, setDomain] = useState(domains[0]);
  const runs = useMemo(() => runsFor(domain), [domain]);
  const [agentId, setAgentId] = useState(runs[0]?.agent_id ?? "");

  const run = runs.find((r) => r.agent_id === agentId) ?? runs[0];
  const gap = baseVsMutated(run);
  const severity = severityCounts(run);

  const modeRows = Object.entries(run.by_mode).map(([mode, count]) => ({
    mode,
    count,
    severity: run.taxonomy[mode]?.severity ?? ("low" as Severity),
  }));

  function switchDomain(next: string) {
    setDomain(next);
    setAgentId(runsFor(next)[0].agent_id);
  }

  return (
    <div className="space-y-8">
      {/* Domain and version switch. Two unrelated domains is the answer to
          "does this only work on your demo agent?", so it is a control rather
          than a footnote. */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Reliability scorecard</h1>
          <p className="mt-1 text-slate-400">
            {data.domains[domain].scenarios} scenarios generated from{" "}
            {data.domains[domain].seeds} hand-written seeds, offline.
          </p>
        </div>
        <div className="flex gap-2">
          <Selector options={domains} value={domain} onChange={switchDomain} />
          <Selector
            options={runs.map((r) => r.agent_id)}
            value={run.agent_id}
            onChange={setAgentId}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          value={`${Math.round(run.pass_rate * 100)}%`}
          label="pass rate"
          accent={run.pass_rate >= 0.9 ? "#22c55e" : run.pass_rate >= 0.6 ? "#eab308" : "#ef4444"}
        />
        <StatCard value={`${run.passed}/${run.total}`} label="scenarios passed" />
        <StatCard
          value={run.findings_total}
          label="findings"
          accent={run.findings_total ? "#f97316" : "#22c55e"}
        />
        <StatCard value={Math.round(run.weighted_score)} label="weighted score" />
      </div>

      {severity.length > 0 ? (
        <div className="panel p-5">
          <div className="flex h-3 overflow-hidden rounded-full bg-ink-850">
            {severity.map(({ severity: s, count }) => (
              <div
                key={s}
                style={{
                  width: `${(count / run.findings_total) * 100}%`,
                  backgroundColor: severityHex(s),
                }}
              />
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-5 text-sm text-slate-400">
            {severity.map(({ severity: s, count }) => (
              <span key={s} className="flex items-center gap-2">
                <i className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: severityHex(s) }} />
                {count} {s}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <div className="panel border-l-4 border-l-pass p-5 text-lg">
          <span className="font-semibold text-pass">No findings.</span> This agent
          survived every adversarial scenario without tripping a single detector.
        </div>
      )}

      {run.findings_total > 0 && (
        <DeterministicBadge decided={run.findings_deterministic} total={run.findings_total} />
      )}

      {/* The pitch, as a number. The tests a person writes by hand are the ones
          the agent passes. */}
      {gap.base !== gap.mutated && (
        <div className="panel p-6">
          <div className="label">where the failures hide</div>
          <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xl">
            <span>Hand-written style scenarios pass at</span>
            <span className="text-2xl font-semibold text-pass">
              {Math.round(gap.base * 100)}%
            </span>
            <span>, their adversarial variants at</span>
            <span className="text-2xl font-semibold text-critical">
              {Math.round(gap.mutated * 100)}%
            </span>
          </div>
          <p className="mt-2 text-sm text-slate-400">
            A person writes down the situation they are picturing. Agents fail in
            the situations nobody pictures.
          </p>
        </div>
      )}

      {modeRows.length > 0 && (
        <div className="panel p-6">
          <h2 className="mb-4 text-lg font-semibold">Failure modes</h2>
          <ResponsiveContainer width="100%" height={Math.max(160, modeRows.length * 46)}>
            <BarChart data={modeRows} layout="vertical" margin={{ left: 8, right: 24 }}>
              <XAxis type="number" stroke="#64748b" fontSize={13} />
              <YAxis
                type="category"
                dataKey="mode"
                stroke="#94a3b8"
                fontSize={13}
                width={190}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "#ffffff08" }}
                contentStyle={{
                  background: "#131a26",
                  border: "1px solid #233046",
                  borderRadius: 8,
                  fontSize: 14,
                }}
              />
              {/* No entry animation. A judge should be able to read the chart
                  the instant the page loads, and an animating bar is also the
                  first thing to go missing in a screenshot or a slow render. */}
              <Bar dataKey="count" radius={[0, 5, 5, 0]} isAnimationActive={false}>
                {modeRows.map((row) => (
                  <Cell key={row.mode} fill={severityHex(row.severity)} />
                ))}
                <LabelList dataKey="count" position="right" fill="#cbd5e1" fontSize={13} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <ScenarioTable domain={domain} run={run} />
    </div>
  );
}

function Selector({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="flex rounded-lg border border-ink-600 bg-ink-850 p-1">
      {options.map((option) => (
        <button
          key={option}
          onClick={() => onChange(option)}
          className={`rounded-md px-3.5 py-1.5 font-mono text-sm transition ${
            option === value ? "bg-ink-700 text-slate-100" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

function ScenarioTable({ domain, run }: { domain: string; run: ReturnType<typeof runsFor>[number] }) {
  const [onlyFailures, setOnlyFailures] = useState(true);
  const rows = onlyFailures ? run.results.filter((s) => !s.passed) : run.results;

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-ink-600 px-6 py-4">
        <h2 className="text-lg font-semibold">
          Scenarios <span className="text-slate-500">({rows.length})</span>
        </h2>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-400">
          <input
            type="checkbox"
            checked={onlyFailures}
            onChange={(e) => setOnlyFailures(e.target.checked)}
            className="accent-slate-400"
          />
          failures only
        </label>
      </div>
      {/* 175 rows, so it scrolls in place rather than pushing the page down. */}
      <div className="max-h-[560px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-ink-850">
            <tr className="label">
              <th className="px-6 py-2.5 text-left font-medium">Scenario</th>
              <th className="px-3 py-2.5 text-left font-medium">Mutations</th>
              <th className="px-3 py-2.5 text-left font-medium">Verdict</th>
              <th className="px-6 py-2.5 text-right font-medium">Findings</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((scenario) => (
              <tr key={scenario.scenario_id} className="border-t border-ink-700 hover:bg-ink-850">
                <td className="px-6 py-2.5">
                  <Link
                    to={`/scenario/${domain}/${run.agent_id}/${encodeURIComponent(scenario.scenario_id)}`}
                    className="break-all font-mono text-slate-200 underline-offset-2 hover:underline"
                  >
                    {scenario.scenario_id}
                  </Link>
                </td>
                <td className="px-3 py-2.5">
                  {scenario.mutations.length === 0 ? (
                    <span className="text-xs text-slate-600">hand-written</span>
                  ) : (
                    scenario.mutations.map((m) => <Chip key={m}>{m}</Chip>)
                  )}
                </td>
                <td className="px-3 py-2.5">
                  <SeverityPill severity={scenario.passed ? null : scenario.worst_severity} />
                </td>
                <td className="px-6 py-2.5 text-right text-slate-400">
                  {scenario.findings.length || "-"}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-6 py-10 text-center text-slate-500">
                  Nothing failed.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
