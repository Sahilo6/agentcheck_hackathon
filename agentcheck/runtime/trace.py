"""Trace recording: the complete, replayable record of one agent run.

A trace is the unit of evidence in agentcheck. Detectors are pure functions over
`(trace, world_after, spec)`, and `fingerprint()` is the determinism guarantee --
two runs of the same scenario at the same seed must produce the same hash, or
regression tracking is measuring noise.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ToolCallRecord:
    """One tool invocation, with the result the agent actually saw."""

    step: int
    tool: str
    args: dict[str, Any]
    ok: bool
    result: str
    error: str | None = None

    def signature(self) -> str:
        """Stable (tool, args) identity used by the loop detector."""
        canonical = json.dumps(self.args, sort_keys=True, separators=(",", ":"))
        return f"{self.tool}({canonical})"


@dataclass
class MessageRecord:
    step: int
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class Trace:
    scenario_id: str
    agent_id: str
    messages: list[MessageRecord] = field(default_factory=list)
    calls: list[ToolCallRecord] = field(default_factory=list)
    final_message: str = ""
    journal: list[dict[str, Any]] = field(default_factory=list)
    world_before: dict[str, Any] = field(default_factory=dict)
    world_after: dict[str, Any] = field(default_factory=dict)
    observed: list[str] = field(default_factory=list)
    # "finished" | "budget_steps" | "budget_calls" | "error"
    stopped: str = "finished"
    error: str | None = None
    steps_used: int = 0

    # -- recording ----------------------------------------------------------

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(MessageRecord(step=self.steps_used, role=role, content=content))

    def add_call(
        self, tool: str, args: dict[str, Any], *, ok: bool, result: str, error: str | None = None
    ) -> ToolCallRecord:
        rec = ToolCallRecord(
            step=self.steps_used, tool=tool, args=dict(args), ok=ok, result=result, error=error
        )
        self.calls.append(rec)
        return rec

    # -- queries used by detectors -----------------------------------------

    def called(self, tool: str) -> bool:
        return any(c.tool == tool for c in self.calls)

    def calls_to(self, tool: str) -> list[ToolCallRecord]:
        return [c for c in self.calls if c.tool == tool]

    def tools_used(self) -> list[str]:
        seen: list[str] = []
        for c in self.calls:
            if c.tool not in seen:
                seen.append(c.tool)
        return seen

    # -- determinism --------------------------------------------------------

    def canonical(self) -> str:
        """Deterministic JSON of the parts that must not vary between runs.

        Deliberately excludes nothing that the agent controls: if the agent is
        nondeterministic, we want the fingerprint to change and say so.
        """
        payload = {
            "scenario": self.scenario_id,
            "agent": self.agent_id,
            "calls": [
                {"tool": c.tool, "args": c.args, "ok": c.ok, "result": c.result}
                for c in self.calls
            ],
            "final": self.final_message,
            "world_after": self.world_after,
            "stopped": self.stopped,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()[:16]

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fingerprint"] = self.fingerprint()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trace":
        trace = cls(
            scenario_id=data["scenario_id"],
            agent_id=data["agent_id"],
            final_message=data.get("final_message", ""),
            journal=data.get("journal", []),
            world_before=data.get("world_before", {}),
            world_after=data.get("world_after", {}),
            observed=data.get("observed", []),
            stopped=data.get("stopped", "finished"),
            error=data.get("error"),
            steps_used=data.get("steps_used", 0),
        )
        trace.messages = [MessageRecord(**m) for m in data.get("messages", [])]
        trace.calls = [ToolCallRecord(**c) for c in data.get("calls", [])]
        return trace
