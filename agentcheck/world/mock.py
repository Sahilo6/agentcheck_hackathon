"""A small, fully in-memory world: filesystem, services, records, outbox, http.

Every mutation is appended to a journal. The journal is what powers the
detectors -- "what did this agent actually change?" is answerable exactly,
which is how out-of-scope deletion and goal drift stop being judgement calls.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from .clock import DeterministicClock

# Operations that destroy or externally commit something. Used by the
# destructive-action detector and surfaced in reports.
DESTRUCTIVE_OPS = frozenset(
    {"delete_file", "stop_service", "update_record", "send_message", "run_command"}
)


@dataclass(frozen=True)
class WorldEvent:
    """One recorded mutation of world state."""

    seq: int
    op: str
    target: str
    at: int
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def destructive(self) -> bool:
        return self.op in DESTRUCTIVE_OPS


class WorldError(Exception):
    """Raised for operations the world rejects (missing file, unknown service)."""


class MockWorld:
    """Stateful mock environment.

    Construct from a `WorldSpec`; mutate through the `*_op` methods that the
    tool layer calls. Nothing here touches the real filesystem or network.
    """

    def __init__(
        self,
        *,
        files: dict[str, str] | None = None,
        services: dict[str, str] | None = None,
        records: dict[str, list[dict[str, Any]]] | None = None,
        http: dict[str, str] | None = None,
        clock: DeterministicClock | None = None,
    ) -> None:
        self.files: dict[str, str] = dict(files or {})
        self.services: dict[str, str] = dict(services or {})
        self.records: dict[str, list[dict[str, Any]]] = copy.deepcopy(records or {})
        self.http: dict[str, str] = dict(http or {})
        self.outbox: list[dict[str, Any]] = []
        self.clock = clock or DeterministicClock()
        self._journal: list[WorldEvent] = []
        # Reads are tracked separately: they are not mutations, but the
        # fabricated-data detector needs to know what the agent was actually
        # shown before it can call a claim invented.
        self.observed: list[str] = []

    # -- construction -------------------------------------------------------

    @classmethod
    def from_spec(cls, spec: Any, *, clock: DeterministicClock | None = None) -> "MockWorld":
        return cls(
            files=spec.files,
            services=spec.services,
            records=spec.records,
            http=spec.http,
            clock=clock,
        )

    # -- journal ------------------------------------------------------------

    @property
    def journal(self) -> list[WorldEvent]:
        return list(self._journal)

    def _record(self, op: str, target: str, **detail: Any) -> None:
        self._journal.append(
            WorldEvent(
                seq=len(self._journal),
                op=op,
                target=target,
                at=self.clock.now(),
                detail=detail,
            )
        )

    # -- snapshot / restore -------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """A deep, JSON-safe copy of state. Used for before/after diffing."""
        return {
            "files": dict(sorted(self.files.items())),
            "services": dict(sorted(self.services.items())),
            "records": copy.deepcopy(self.records),
            "outbox": copy.deepcopy(self.outbox),
        }

    def restore(self, snap: dict[str, Any]) -> None:
        self.files = dict(snap["files"])
        self.services = dict(snap["services"])
        self.records = copy.deepcopy(snap["records"])
        self.outbox = copy.deepcopy(snap["outbox"])

    # -- filesystem ---------------------------------------------------------

    @staticmethod
    def _norm(path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        # Collapse duplicate slashes but keep it dumb: this is a mock, and
        # resolving `..` here would hide traversal attempts we want to observe.
        while "//" in path:
            path = path.replace("//", "/")
        return path.rstrip("/") or "/"

    def exists(self, path: str) -> bool:
        p = self._norm(path)
        return p in self.files or self.is_dir(p)

    def is_dir(self, path: str) -> bool:
        p = self._norm(path)
        if p == "/":
            return True
        prefix = p + "/"
        return any(f.startswith(prefix) for f in self.files)

    def list_op(self, path: str) -> list[str]:
        p = self._norm(path)
        prefix = "/" if p == "/" else p + "/"
        children: set[str] = set()
        for f in self.files:
            if f.startswith(prefix):
                rest = f[len(prefix) :]
                children.add(rest.split("/", 1)[0])
        if not children and p not in self.files:
            raise WorldError(f"no such directory: {path}")
        self.observed.append(p)
        return sorted(children)

    def read_op(self, path: str) -> str:
        p = self._norm(path)
        if p not in self.files:
            raise WorldError(f"no such file: {path}")
        self.observed.append(p)
        return self.files[p]

    def write_op(self, path: str, content: str) -> None:
        p = self._norm(path)
        self.files[p] = content
        self._record("write_file", p, bytes=len(content))

    def delete_op(self, path: str) -> list[str]:
        """Delete a file, or a directory tree.

        Recursive directory deletion is deliberate: it is the mechanism behind
        the most consequential real-world agent failure we want to reproduce.
        Returns the paths removed so the journal carries the true blast radius.
        """
        p = self._norm(path)
        removed: list[str]
        if p in self.files:
            removed = [p]
        else:
            prefix = "/" if p == "/" else p + "/"
            removed = sorted(f for f in self.files if f.startswith(prefix))
            if not removed:
                raise WorldError(f"no such file or directory: {path}")
        for f in removed:
            del self.files[f]
        self._record("delete_file", p, removed=removed, count=len(removed))
        return removed

    # -- services -----------------------------------------------------------

    def service_status_op(self, name: str) -> str:
        if name not in self.services:
            raise WorldError(f"unknown service: {name}")
        self.observed.append(f"service:{name}")
        return self.services[name]

    def start_service_op(self, name: str) -> None:
        if name not in self.services:
            raise WorldError(f"unknown service: {name}")
        self.services[name] = "running"
        self._record("start_service", name)

    def stop_service_op(self, name: str) -> None:
        if name not in self.services:
            raise WorldError(f"unknown service: {name}")
        self.services[name] = "stopped"
        self._record("stop_service", name)

    def restart_service_op(self, name: str) -> None:
        if name not in self.services:
            raise WorldError(f"unknown service: {name}")
        self.services[name] = "running"
        self._record("restart_service", name)

    # -- records ------------------------------------------------------------

    def find_record(self, table: str, record_id: str) -> dict[str, Any] | None:
        for row in self.records.get(table, []):
            if str(row.get("id")) == str(record_id):
                return row
        return None

    def read_record_op(self, table: str, record_id: str) -> dict[str, Any]:
        row = self.find_record(table, record_id)
        if row is None:
            raise WorldError(f"no such record: {table}/{record_id}")
        self.observed.append(f"{table}:{record_id}")
        return dict(row)

    def update_record_op(self, table: str, record_id: str, field_: str, value: Any) -> None:
        row = self.find_record(table, record_id)
        if row is None:
            raise WorldError(f"no such record: {table}/{record_id}")
        before = row.get(field_)
        row[field_] = value
        self._record(
            "update_record",
            f"{table}:{record_id}",
            field=field_,
            before=before,
            after=value,
        )

    # -- outbox -------------------------------------------------------------

    def send_op(self, channel: str, body: str) -> None:
        self.outbox.append({"channel": channel, "body": body, "at": self.clock.now()})
        self._record("send_message", channel, body=body)

    # -- http ---------------------------------------------------------------

    def fetch_op(self, url: str) -> str:
        if url not in self.http:
            raise WorldError(f"unreachable: {url}")
        self.observed.append(url)
        return self.http[url]

    # -- shell --------------------------------------------------------------

    def run_command_op(self, command: str) -> str:
        """Interpret a tiny subset of shell so `rm -rf` has real consequences.

        A mock that merely echoed the command back would let a destructive
        agent look harmless. Anything unrecognised is reported as unsupported
        rather than silently succeeding.
        """
        self._record("run_command", command, command=command)
        parts = command.strip().split()
        if not parts:
            return ""
        if parts[0] == "rm":
            targets = [p for p in parts[1:] if not p.startswith("-")]
            removed: list[str] = []
            for t in targets:
                try:
                    removed.extend(self.delete_op(t))
                except WorldError:
                    continue
            return f"removed {len(removed)} file(s)"
        if parts[0] == "ls":
            target = parts[1] if len(parts) > 1 else "/"
            try:
                return "\n".join(self.list_op(target))
            except WorldError as exc:
                return f"ls: {exc}"
        if parts[0] == "cat" and len(parts) > 1:
            try:
                return self.read_op(parts[1])
            except WorldError as exc:
                return f"cat: {exc}"
        if parts[0] == "df":
            used = sum(len(c) for c in self.files.values())
            return f"Filesystem 1K-blocks Used Available Use%\n/dev/sda1 100000 {used} {100000 - used} 87%"
        return f"{parts[0]}: unsupported in sandbox"
