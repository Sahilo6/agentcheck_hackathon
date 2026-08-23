"""Run history and regression diffing.

Regression tracking is only meaningful because runs are deterministic: the same
suite against the same agent produces the same fingerprints, so a scenario that
flips from pass to fail genuinely changed. Without that guarantee this would be
measuring sampling noise and calling it a regression.

Runs are appended to a JSONL file. One line per run, newest last, no database.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..score.scorecard import Scorecard
from ..spec.models import ScenarioSpec


def suite_hash(specs: Iterable[ScenarioSpec]) -> str:
    """Identify a suite by its scenarios.

    Comparing two runs of *different* suites would produce a meaningless diff,
    so the hash is recorded and checked before any regression claim is made.
    """
    material = json.dumps(
        sorted((s.id, s.task) for s in specs), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


@dataclass
class ScenarioOutcome:
    passed: bool
    worst_severity: str | None
    modes: list[str]
    fingerprint: str


@dataclass
class RunRecord:
    run_id: str
    agent_id: str
    at: str
    suite: str
    total: int
    passed: int
    pass_rate: float
    findings_total: int
    outcomes: dict[str, ScenarioOutcome] = field(default_factory=dict)

    def to_json(self) -> str:
        payload = asdict(self)
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        return cls(
            run_id=data["run_id"],
            agent_id=data["agent_id"],
            at=data["at"],
            suite=data["suite"],
            total=data["total"],
            passed=data["passed"],
            pass_rate=data["pass_rate"],
            findings_total=data.get("findings_total", 0),
            outcomes={
                sid: ScenarioOutcome(**out) for sid, out in data.get("outcomes", {}).items()
            },
        )


def build_record(
    card: Scorecard, *, specs: Iterable[ScenarioSpec] | None = None, at: str | None = None
) -> RunRecord:
    scenarios = list(specs) if specs is not None else [r.spec for r in card.results]
    stamp = at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    outcomes = {
        r.spec.id: ScenarioOutcome(
            passed=r.passed,
            worst_severity=r.worst_severity,
            modes=sorted({f.mode for f in r.findings}),
            fingerprint=r.trace.fingerprint(),
        )
        for r in card.results
    }
    det, total_findings = card.deterministic_finding_share()
    # Run ids are derived rather than random, and the per-scenario outcomes are
    # part of the material. A timestamp alone has second granularity, so two
    # different runs in the same second would collide and make the history
    # ambiguous. Including the outcomes also makes the id idempotent: re-recording
    # a genuinely identical run reuses its id instead of inventing a data point.
    outcome_digest = hashlib.sha256(
        json.dumps(
            {sid: [o.passed, o.fingerprint] for sid, o in sorted(outcomes.items())},
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    run_id = hashlib.sha256(
        f"{card.agent_id}:{suite_hash(scenarios)}:{stamp}:{outcome_digest}".encode("utf-8")
    ).hexdigest()[:12]
    return RunRecord(
        run_id=run_id,
        agent_id=card.agent_id,
        at=stamp,
        suite=suite_hash(scenarios),
        total=card.total,
        passed=card.passed,
        pass_rate=round(card.pass_rate, 4),
        findings_total=total_findings,
        outcomes=outcomes,
    )


def append_run(record: RunRecord, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(record.to_json() + "\n")


def load_runs(path: Path | str) -> list[RunRecord]:
    path = Path(path)
    if not path.exists():
        return []
    runs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            runs.append(RunRecord.from_dict(json.loads(line)))
    return runs


def previous_run(path: Path | str, *, agent_id: str | None = None) -> RunRecord | None:
    """The most recent prior run, optionally for one agent."""
    runs = load_runs(path)
    if agent_id is not None:
        runs = [r for r in runs if r.agent_id == agent_id]
    return runs[-1] if runs else None


@dataclass
class RegressionDiff:
    """What changed between two runs of the same suite."""

    baseline: RunRecord
    current: RunRecord
    fixed: list[str] = field(default_factory=list)
    new_failures: list[str] = field(default_factory=list)
    still_failing: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    # Same scenario, same verdict, different trace. Usually a nondeterministic
    # agent, and worth surfacing rather than hiding.
    drifted: list[str] = field(default_factory=list)

    @property
    def comparable(self) -> bool:
        return self.baseline.suite == self.current.suite

    @property
    def regressed(self) -> bool:
        return bool(self.new_failures)

    def summary(self) -> str:
        parts = [
            f"{len(self.fixed)} fixed",
            f"{len(self.new_failures)} new",
            f"{len(self.still_failing)} still failing",
        ]
        if self.added or self.removed:
            parts.append(f"{len(self.added)} added / {len(self.removed)} removed")
        if self.drifted:
            parts.append(f"{len(self.drifted)} drifted")
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": {"run_id": self.baseline.run_id, "at": self.baseline.at,
                         "pass_rate": self.baseline.pass_rate},
            "current": {"run_id": self.current.run_id, "at": self.current.at,
                        "pass_rate": self.current.pass_rate},
            "comparable": self.comparable,
            "regressed": self.regressed,
            "fixed": self.fixed,
            "new_failures": self.new_failures,
            "still_failing": self.still_failing,
            "added": self.added,
            "removed": self.removed,
            "drifted": self.drifted,
        }


def diff_runs(baseline: RunRecord, current: RunRecord) -> RegressionDiff:
    out = RegressionDiff(baseline=baseline, current=current)
    before, after = baseline.outcomes, current.outcomes

    for sid, now in after.items():
        was = before.get(sid)
        if was is None:
            out.added.append(sid)
            continue
        if was.passed and not now.passed:
            out.new_failures.append(sid)
        elif not was.passed and now.passed:
            out.fixed.append(sid)
        elif not now.passed:
            out.still_failing.append(sid)
        elif was.fingerprint != now.fingerprint:
            out.drifted.append(sid)

    out.removed = [sid for sid in before if sid not in after]

    for bucket in (out.fixed, out.new_failures, out.still_failing, out.added,
                   out.removed, out.drifted):
        bucket.sort()
    return out
