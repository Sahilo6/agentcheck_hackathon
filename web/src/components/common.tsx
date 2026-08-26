import type { ReactNode } from "react";
import type { Severity } from "../types";

const SEVERITY_HEX: Record<Severity, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#64748b",
};

export function severityHex(severity: Severity | null): string {
  return severity ? SEVERITY_HEX[severity] : "#64748b";
}

export function SeverityPill({ severity }: { severity: Severity | null }) {
  if (!severity) {
    return (
      <span className="inline-flex items-center rounded-full bg-pass/15 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-pass">
        pass
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide"
      style={{ backgroundColor: `${SEVERITY_HEX[severity]}22`, color: SEVERITY_HEX[severity] }}
    >
      {severity}
    </span>
  );
}

export function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="mr-1.5 mb-1.5 inline-block rounded border border-ink-600 bg-ink-850 px-2 py-0.5 font-mono text-xs text-slate-400">
      {children}
    </span>
  );
}

export function StatCard({
  value,
  label,
  accent,
  hint,
}: {
  value: ReactNode;
  label: string;
  accent?: string;
  hint?: string;
}) {
  return (
    <div className="panel p-5">
      <div className="text-4xl font-semibold leading-none" style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      <div className="label mt-2">{label}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

/** The differentiator badge. Given real estate on purpose. */
export function DeterministicBadge({ decided, total }: { decided: number; total: number }) {
  return (
    <div className="panel border-l-4 border-l-pass p-5">
      <div className="text-lg">
        <span className="font-semibold text-pass">
          {decided} of {total} findings
        </span>{" "}
        were decided by a property check against recorded world state.
      </div>
      <div className="mt-2 text-sm text-slate-400">
        No language model was consulted. Every finding can be re-derived from the
        trace offline, with the same answer every time.
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="panel p-8 text-center text-slate-500">{children}</div>;
}
