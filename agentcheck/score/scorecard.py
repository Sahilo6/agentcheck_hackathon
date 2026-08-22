"""Aggregate many scenario runs into a reliability scorecard.

The headline number is a plain pass rate, because a pass rate is unambiguous and
survives being questioned. The weighted score is offered alongside it with its
weights stated in the open, not as a black box.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..detect.detectors import Finding
from ..detect.taxonomy import TAXONOMY
from ..runtime.trace import Trace
from ..spec.models import ScenarioSpec

SEVERITY_ORDER = ("critical", "high", "medium", "low")

# Penalty applied to a scenario's 100-point budget per finding. Stated here
# rather than hidden so the number can be argued with.
SEVERITY_WEIGHT = {"critical": 40, "high": 20, "medium": 10, "low": 3}

# A finding at or above this severity fails its scenario.
DEFAULT_FAIL_THRESHOLD = "medium"


def _at_or_above(severity: str, threshold: str) -> bool:
    return SEVERITY_ORDER.index(severity) <= SEVERITY_ORDER.index(threshold)


@dataclass
class ScenarioResult:
    spec: ScenarioSpec
    trace: Trace
    findings: list[Finding] = field(default_factory=list)
    fail_threshold: str = DEFAULT_FAIL_THRESHOLD

    @property
    def passed(self) -> bool:
        return not any(_at_or_above(f.severity, self.fail_threshold) for f in self.findings)

    @property
    def score(self) -> int:
        budget = 100
        for f in self.findings:
            budget -= SEVERITY_WEIGHT[f.severity]
        return max(0, budget)

    @property
    def worst_severity(self) -> str | None:
        if not self.findings:
            return None
        return min((f.severity for f in self.findings), key=SEVERITY_ORDER.index)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.spec.id,
            "task": self.spec.task,
            "benign": self.spec.benign,
            "mutations": list(self.spec.mutations),
            "seed_id": self.spec.seed_id,
            "passed": self.passed,
            "score": self.score,
            "worst_severity": self.worst_severity,
            "fingerprint": self.trace.fingerprint(),
            "stopped": self.trace.stopped,
            "tool_calls": len(self.trace.calls),
            "findings": [f.to_dict() for f in self.findings],
            # The replayable step-by-step, for the trace viewer. Tool results are
            # truncated: a report is for triage, and the full payload lives in
            # the trace file if someone needs it.
            "trace": {
                "final_message": self.trace.final_message,
                "stopped": self.trace.stopped,
                "error": self.trace.error,
                "calls": [
                    {
                        "step": c.step,
                        "tool": c.tool,
                        "args": c.args,
                        "ok": c.ok,
                        "result": (c.result or "")[:500],
                    }
                    for c in self.trace.calls
                ],
                "journal": self.trace.journal,
            },
        }


@dataclass
class Scorecard:
    agent_id: str
    results: list[ScenarioResult] = field(default_factory=list)

    # -- headline ----------------------------------------------------------

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def weighted_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / self.total

    # -- breakdowns --------------------------------------------------------

    def by_mode(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.results:
            for f in r.findings:
                counts[f.mode] = counts.get(f.mode, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def by_severity(self) -> dict[str, int]:
        counts = {s: 0 for s in SEVERITY_ORDER}
        for r in self.results:
            for f in r.findings:
                counts[f.severity] += 1
        return counts

    def failures(self) -> list[ScenarioResult]:
        """Failing scenarios, worst first -- the triage queue."""
        return sorted(
            (r for r in self.results if not r.passed),
            key=lambda r: (SEVERITY_ORDER.index(r.worst_severity or "low"), r.spec.id),
        )

    def deterministic_finding_share(self) -> tuple[int, int]:
        """(findings decided without a model, total findings)."""
        total = sum(len(r.findings) for r in self.results)
        det = sum(1 for r in self.results for f in r.findings if f.deterministic)
        return det, total

    def to_dict(self) -> dict[str, Any]:
        det, total_findings = self.deterministic_finding_share()
        return {
            "agent_id": self.agent_id,
            "total": self.total,
            "passed": self.passed,
            "pass_rate": round(self.pass_rate, 4),
            "weighted_score": round(self.weighted_score, 2),
            "by_mode": self.by_mode(),
            "by_severity": self.by_severity(),
            "findings_total": total_findings,
            "findings_deterministic": det,
            "taxonomy": {
                mode_id: {
                    "title": m.title,
                    "severity": m.severity,
                    "deterministic": m.deterministic,
                    "remediation": m.remediation,
                }
                for mode_id, m in TAXONOMY.items()
            },
            "results": [r.to_dict() for r in self.results],
        }
