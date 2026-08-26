import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Check, Fingerprint, X } from "lucide-react";
import { Chip, Empty, SeverityPill, severityHex } from "../components/common";
import { findRun, findScenario } from "../data";
import type { Finding, ScenarioResult, Scorecard } from "../types";

/** "1 step", "3 steps". Small thing, but "1 steps" on a projector is the kind of
 * detail an audience notices and a presenter cannot unsee. */
function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

export default function ScenarioDetail() {
  const { domain = "", agentId = "", scenarioId = "" } = useParams();
  const run = findRun(domain, agentId);
  const scenario = run && findScenario(run, decodeURIComponent(scenarioId));

  if (!run || !scenario) {
    return <Empty>Scenario not found.</Empty>;
  }

  return (
    <div className="space-y-6">
      <Link
        to="/scorecard"
        className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200"
      >
        <ArrowLeft size={15} /> back to scorecard
      </Link>

      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold">{scenario.scenario_id}</h1>
          <SeverityPill severity={scenario.passed ? null : scenario.worst_severity} />
          {!scenario.benign && (
            <span className="rounded border border-medium/40 bg-medium/10 px-2 py-0.5 text-xs text-medium">
              trap: refusing is correct
            </span>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <Fingerprint size={14} />
            <span className="mono">{scenario.fingerprint}</span>
            <span>reproducible</span>
          </span>
          <span>·</span>
          <span>{plural(scenario.tool_calls, "tool call")}</span>
          <span>·</span>
          <span className="mono">{scenario.stopped}</span>
        </div>
      </div>

      <div className="panel p-6">
        <div className="label mb-2">the task the agent was given</div>
        <p className="text-lg leading-relaxed text-slate-200">{scenario.task}</p>
        <div className="mt-4">
          {scenario.mutations.length === 0 ? (
            <span className="text-sm text-slate-500">
              No mutations. This is the scenario as a person would write it.
            </span>
          ) : (
            scenario.mutations.map((m) => <Chip key={m}>{m}</Chip>)
          )}
        </div>
      </div>

      <ClaimedVsPerformed scenario={scenario} />

      {scenario.findings.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">
            Findings <span className="text-slate-500">({scenario.findings.length})</span>
          </h2>
          <div className="space-y-3">
            {scenario.findings.map((finding, index) => (
              <FindingCard key={index} finding={finding} run={run} />
            ))}
          </div>
        </section>
      )}

      <TraceViewer scenario={scenario} />
    </div>
  );
}

/** The centrepiece.
 *
 * What the agent said, next to what the world actually recorded. When those
 * disagree the tool has proven a lie by checking state, not by asking a model
 * for an opinion, and that contrast is the whole argument in one view.
 */
function ClaimedVsPerformed({ scenario }: { scenario: ScenarioResult }) {
  const lied = scenario.findings.some((f) => f.mode === "hallucinated_success");
  const { final_message: claim, journal } = scenario.trace;
  if (!claim) return null;

  const performed = [...new Set(journal.map((e) => e.op))];

  return (
    <div
      className={`panel overflow-hidden ${lied ? "border-critical/50" : ""}`}
      style={lied ? { boxShadow: "0 0 0 1px #ef444455" } : undefined}
    >
      {lied && (
        <div className="flex items-center gap-2 border-b border-critical/40 bg-critical/10 px-6 py-3 text-critical">
          <AlertTriangle size={17} />
          <span className="font-semibold">
            The agent reported work the world state shows it never did.
          </span>
        </div>
      )}
      <div className="grid gap-px bg-ink-600 md:grid-cols-2">
        <div className="bg-ink-800 p-6">
          <div className="label mb-3">what the agent said</div>
          <blockquote
            className={`border-l-2 pl-4 text-lg italic leading-relaxed ${
              lied ? "border-critical text-slate-200" : "border-ink-600 text-slate-300"
            }`}
          >
            {claim}
          </blockquote>
        </div>
        <div className="bg-ink-800 p-6">
          <div className="label mb-3">what the world recorded</div>
          {performed.length === 0 ? (
            <div className="font-mono text-lg text-critical">nothing changed</div>
          ) : (
            <ul className="space-y-1.5">
              {performed.map((op) => (
                <li key={op} className="flex items-center gap-2 font-mono text-slate-300">
                  <Check size={15} className="shrink-0 text-pass" />
                  {op}
                </li>
              ))}
            </ul>
          )}
          {lied && (
            <p className="mt-4 text-sm text-slate-400">
              Checked against the journal of state changes, not by asking a model
              whether the summary sounded truthful.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function FindingCard({ finding, run }: { finding: Finding; run: Scorecard }) {
  const colour = severityHex(finding.severity);
  const remediation = run.taxonomy[finding.mode]?.remediation;

  return (
    <div className="panel border-l-4 p-5" style={{ borderLeftColor: colour }}>
      <div className="flex flex-wrap items-center gap-3">
        <SeverityPill severity={finding.severity} />
        <span className="font-semibold">{finding.title}</span>
        <span className="mono text-slate-500">{finding.mode}</span>
        {finding.deterministic && (
          <span className="ml-auto rounded bg-pass/10 px-2 py-0.5 text-xs text-pass">
            no LLM
          </span>
        )}
      </div>
      <p className="mt-2.5 text-slate-300">{finding.summary}</p>

      {Object.keys(finding.evidence).length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm text-slate-400 hover:text-slate-200">
            evidence
          </summary>
          {/* Evidence shape varies per mode, so it is rendered generically
              rather than with per-mode templates that would drift. */}
          <pre className="mt-2 overflow-x-auto rounded-lg border border-ink-600 bg-ink-850 p-3 font-mono text-xs text-slate-300">
            {JSON.stringify(finding.evidence, null, 2)}
          </pre>
        </details>
      )}

      {remediation && (
        <p className="mt-3 border-t border-ink-700 pt-3 text-sm italic text-slate-400">
          Fix: {remediation}
        </p>
      )}
    </div>
  );
}

function TraceViewer({ scenario }: { scenario: ScenarioResult }) {
  const { calls } = scenario.trace;
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">
        Trace <span className="text-slate-500">({plural(calls.length, "step")})</span>
      </h2>
      {calls.length === 0 ? (
        <Empty>The agent took no action.</Empty>
      ) : (
        <div className="panel divide-y divide-ink-700">
          {calls.map((call, index) => (
            <div key={index} className="flex gap-4 p-4">
              <div className="w-7 shrink-0 pt-0.5 text-right font-mono text-sm text-slate-600">
                {index + 1}
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-mono text-slate-200">
                  <span className={call.ok ? "" : "text-critical"}>{call.tool}</span>
                  <span className="text-slate-500">
                    (
                    {Object.entries(call.args)
                      .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
                      .join(", ")}
                    )
                  </span>
                </div>
                <div
                  className={`mt-1 overflow-x-auto whitespace-pre-wrap break-words font-mono text-sm ${
                    call.ok ? "text-slate-400" : "text-critical/90"
                  }`}
                >
                  {call.result}
                </div>
              </div>
              <div className="shrink-0 pt-1">
                {call.ok ? (
                  <Check size={16} className="text-pass" />
                ) : (
                  <X size={16} className="text-critical" />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
