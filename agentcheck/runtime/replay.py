"""Record real runs to disk and replay them offline.

An LLM agent is nondeterministic, which breaks the guarantee the rest of
agentcheck depends on. Recording solves both problems at once:

  * the numbers come from a real model, so they mean something, and
  * the demo replays from disk with the network unplugged, so nothing live sits
    on the critical path of a presentation.

Replayed runs are scored by the same detectors as live ones. Nothing about the
scoring path changes, which is why a replayed report is worth the same as a
fresh one.
"""

from __future__ import annotations

import json
from pathlib import Path

from .trace import Trace


class MissingTraces(Exception):
    """Raised when a replay is asked for scenarios the store does not hold."""


class TraceStore:
    """Append-only JSONL of traces, keyed by scenario id.

    Later entries win, so re-recording one scenario updates it without a
    rewrite of the file.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(self, trace: Trace) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(trace.to_dict(), separators=(",", ":")) + "\n")

    def load(self) -> dict[str, Trace]:
        if not self.path.exists():
            return {}
        traces: dict[str, Trace] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            traces[data["scenario_id"]] = Trace.from_dict(data)
        return traces

    def __len__(self) -> int:
        return len(self.load())


def resolve_replay(
    store: TraceStore, scenario_ids: list[str], *, strict: bool = True
) -> dict[str, Trace]:
    """Load traces for the given scenarios.

    Strict by default: a partially-recorded replay would silently report on a
    subset while presenting a pass rate over the whole suite, which is a worse
    outcome than a clear failure.
    """
    available = store.load()
    missing = [sid for sid in scenario_ids if sid not in available]
    if missing and strict:
        raise MissingTraces(
            f"{len(missing)} of {len(scenario_ids)} scenarios are not in "
            f"{store.path}: {', '.join(missing[:5])}"
            f"{' ...' if len(missing) > 5 else ''}\n"
            "Record them first, or pass --replay-partial to score only what is there."
        )
    return {sid: available[sid] for sid in scenario_ids if sid in available}
