/** Loading and shaping the fixture.
 *
 * The whole dataset is bundled into the build rather than fetched, so the
 * dashboard works with no server and no network. That is the same constraint the
 * HTML report has: conference wifi fails, and the demo cannot depend on it.
 */

import fixture from "../fixtures/sample-scorecard.json";
import type { Fixture, ScenarioResult, Scorecard, Severity } from "./types";

export const data = fixture as unknown as Fixture;

export const domains = Object.keys(data.domains);

/** Runs are ordered naive-then-hardened per domain, as the generator writes them. */
export function runsFor(domain: string): Scorecard[] {
  return data.runs.filter((r) => r.domain === domain);
}

export function findRun(domain: string, agentId: string): Scorecard | undefined {
  return data.runs.find((r) => r.domain === domain && r.agent_id === agentId);
}

export function findScenario(
  run: Scorecard,
  scenarioId: string,
): ScenarioResult | undefined {
  return run.results.find((s) => s.scenario_id === scenarioId);
}

/** Failing scenarios, worst first. The triage order. */
export function failures(run: Scorecard): ScenarioResult[] {
  const rank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
  return run.results
    .filter((s) => !s.passed)
    .sort(
      (a, b) =>
        rank[a.worst_severity ?? "low"] - rank[b.worst_severity ?? "low"] ||
        a.scenario_id.localeCompare(b.scenario_id),
    );
}

export interface RegressionDiff {
  fixed: string[];
  newFailures: string[];
  stillFailing: string[];
}

/** Compare two runs of the identical suite.
 *
 * Only meaningful because runs are deterministic: the same scenario against the
 * same agent produces a byte-identical trace, so a scenario that flips verdict
 * genuinely changed rather than being resampled.
 */
export function diff(before: Scorecard, after: Scorecard): RegressionDiff {
  const previous = new Map(before.results.map((s) => [s.scenario_id, s.passed]));
  const out: RegressionDiff = { fixed: [], newFailures: [], stillFailing: [] };
  for (const scenario of after.results) {
    const was = previous.get(scenario.scenario_id);
    if (was === undefined) continue;
    if (!was && scenario.passed) out.fixed.push(scenario.scenario_id);
    else if (was && !scenario.passed) out.newFailures.push(scenario.scenario_id);
    else if (!scenario.passed) out.stillFailing.push(scenario.scenario_id);
  }
  return out;
}

/** Pass rate over unmutated seeds versus mutated variants.
 *
 * The gap is the argument: the tests a person writes by hand are the ones the
 * agent passes.
 */
export function baseVsMutated(run: Scorecard): { base: number; mutated: number } {
  const base = run.results.filter((s) => s.mutations.length === 0);
  const mutated = run.results.filter((s) => s.mutations.length > 0);
  const rate = (rows: ScenarioResult[]) =>
    rows.length ? rows.filter((s) => s.passed).length / rows.length : 0;
  return { base: rate(base), mutated: rate(mutated) };
}

export function severityCounts(run: Scorecard): { severity: Severity; count: number }[] {
  return (["critical", "high", "medium", "low"] as Severity[])
    .map((severity) => ({ severity, count: run.by_severity[severity] ?? 0 }))
    .filter((row) => row.count > 0);
}
