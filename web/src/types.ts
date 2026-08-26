/** Shapes of `fixtures/sample-scorecard.json`, produced by the Python engine.
 *
 * Regenerate the fixture with `python3 examples/make_sample_scorecard.py`. If a
 * field here stops matching, the fixture is the source of truth, not this file.
 */

export type Severity = "critical" | "high" | "medium" | "low";

export interface Finding {
  mode: string;
  title: string;
  severity: Severity;
  deterministic: boolean;
  summary: string;
  evidence: Record<string, unknown>;
}

export interface ToolCall {
  step: number;
  tool: string;
  args: Record<string, unknown>;
  ok: boolean;
  result: string;
}

export interface JournalEntry {
  seq: number;
  op: string;
  target: string;
  detail: Record<string, unknown>;
  destructive: boolean;
}

export interface Trace {
  final_message: string;
  stopped: string;
  error: string | null;
  calls: ToolCall[];
  journal: JournalEntry[];
}

export interface ScenarioResult {
  scenario_id: string;
  task: string;
  benign: boolean;
  mutations: string[];
  seed_id: string | null;
  passed: boolean;
  score: number;
  worst_severity: Severity | null;
  fingerprint: string;
  stopped: string;
  tool_calls: number;
  findings: Finding[];
  trace: Trace;
}

export interface TaxonomyEntry {
  title: string;
  severity: Severity;
  deterministic: boolean;
  remediation: string;
}

export interface Scorecard {
  agent_id: string;
  domain: string;
  total: number;
  passed: number;
  pass_rate: number;
  weighted_score: number;
  by_mode: Record<string, number>;
  by_severity: Record<Severity, number>;
  findings_total: number;
  findings_deterministic: number;
  taxonomy: Record<string, TaxonomyEntry>;
  results: ScenarioResult[];
}

export interface Fixture {
  generated_by: string;
  note: string;
  domains: Record<string, { seeds: number; scenarios: number; seed_ids: string[] }>;
  runs: Scorecard[];
}

