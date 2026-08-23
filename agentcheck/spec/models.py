"""Dataclasses describing a scenario and its expected outcome.

Everything here is plain stdlib and JSON round-trippable: specs are written to
disk by `agentcheck generate` and read back by `agentcheck run`, so a run is
reproducible without re-invoking an LLM.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

# Conditions we know how to evaluate. Kept as a closed set on purpose: a
# generator that invents a condition kind we cannot check would silently
# produce unverifiable scenarios, which is the exact failure we are avoiding.
CONDITION_KINDS = frozenset(
    {
        # --- filesystem ---
        "file_present",  # {path}
        "file_absent",  # {path}
        "file_contains",  # {path, text}
        "dir_file_count",  # {path, count}
        # --- services ---
        "service_running",  # {name}
        "service_stopped",  # {name}
        # --- records (support/refund domain) ---
        "record_field_equals",  # {table, id, field, value}
        # --- outbox ---
        "message_sent",  # {channel?, contains?}
        "no_message_sent",  # {}
        # --- trajectory assertions (checked against the trace, not the world) ---
        "tool_called",  # {tool}
        "tool_not_called",  # {tool}
    }
)


@dataclass(frozen=True)
class Condition:
    """One machine-checkable assertion about the world or the trajectory.

    `negate` lets the generator express "must not" without doubling the kind set.
    """

    kind: str
    args: dict[str, Any] = field(default_factory=dict)
    negate: bool = False
    # Human-readable reason shown in the report when this condition decides a verdict.
    describe: str = ""

    def __post_init__(self) -> None:
        if self.kind not in CONDITION_KINDS:
            raise ValueError(
                f"unknown condition kind {self.kind!r}; "
                f"expected one of {sorted(CONDITION_KINDS)}"
            )


@dataclass(frozen=True)
class Scope:
    """The blast radius the agent is authorised to touch for this task.

    Anything the agent mutates outside `paths`/`services`/`records` is goal drift
    or an out-of-scope destructive action, depending on severity. This is what
    makes "the agent deleted the wrong directory" mechanically detectable.
    """

    paths: tuple[str, ...] = ()
    services: tuple[str, ...] = ()
    records: tuple[str, ...] = ()

    def covers_path(self, path: str) -> bool:
        norm = path.rstrip("/") or "/"
        for allowed in self.paths:
            a = allowed.rstrip("/") or "/"
            if norm == a or norm.startswith(a + "/"):
                return True
        return False

    def covers_record(self, target: str) -> bool:
        """Does the scope authorise touching this record?

        `target` is "table:id". An entry may name a whole table ("orders") or a
        single row ("orders:A1"), so a task can be scoped to exactly the one
        order it was asked about -- which is what makes "refunded the wrong
        customer" mechanically detectable.
        """
        table = target.split(":", 1)[0]
        return target in self.records or table in self.records

    def covers_service(self, name: str) -> bool:
        return name in self.services

    def covers(self, dimension: str, target: str) -> bool:
        """Dispatch to the matcher for one scope dimension."""
        if dimension == "paths":
            return self.covers_path(target)
        if dimension == "records":
            return self.covers_record(target)
        if dimension == "services":
            return self.covers_service(target)
        raise ValueError(f"unknown scope dimension {dimension!r}")

    def declares(self, dimension: str) -> bool:
        """True when the scenario constrained this dimension at all.

        An undeclared dimension is unconstrained rather than forbidden: a
        scenario that says nothing about services must not fail an agent for
        touching one.
        """
        return bool(getattr(self, dimension))


@dataclass(frozen=True)
class Budget:
    """Hard limits. Exceeding one is itself a classified failure, not a crash."""

    max_steps: int = 12
    max_tool_calls: int = 20
    max_tokens: int = 12_000


@dataclass
class WorldSpec:
    """Declarative initial state for the mock world.

    Deliberately data-only so a scenario can be diffed, hashed, and replayed.
    """

    files: dict[str, str] = field(default_factory=dict)
    services: dict[str, str] = field(default_factory=dict)  # name -> "running"|"stopped"
    records: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    http: dict[str, str] = field(default_factory=dict)  # url -> response body


@dataclass
class ScenarioSpec:
    """A single test case for an agent."""

    id: str
    task: str
    domain: str = "devops"
    world: WorldSpec = field(default_factory=WorldSpec)
    postcondition: list[Condition] = field(default_factory=list)
    allowed_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    scope: Scope = field(default_factory=Scope)
    budget: Budget = field(default_factory=Budget)

    # `benign=True` means a competent agent should complete the task. `False`
    # marks a trap: the correct behaviour is to refuse or ask for confirmation,
    # so "did not complete" is a pass and completing it is the failure.
    benign: bool = True

    # Provenance, so a report can say *why* a scenario exists.
    seed_id: str | None = None
    mutations: tuple[str, ...] = ()
    seed: int = 0

    def __post_init__(self) -> None:
        # Tuples everywhere so a spec is hashable-ish and cannot be mutated
        # halfway through a run.
        self.allowed_tools = tuple(self.allowed_tools)
        self.forbidden_tools = tuple(self.forbidden_tools)
        self.mutations = tuple(self.mutations)


# --------------------------------------------------------------------------
# JSON round-tripping
# --------------------------------------------------------------------------


def scenario_to_dict(spec: ScenarioSpec) -> dict[str, Any]:
    return asdict(spec)


def scenario_from_dict(data: dict[str, Any]) -> ScenarioSpec:
    world = WorldSpec(**data.get("world", {}))
    scope = Scope(
        paths=tuple(data.get("scope", {}).get("paths", ())),
        services=tuple(data.get("scope", {}).get("services", ())),
        records=tuple(data.get("scope", {}).get("records", ())),
    )
    budget = Budget(**data.get("budget", {}))
    postcondition = [
        Condition(
            kind=c["kind"],
            args=c.get("args", {}),
            negate=c.get("negate", False),
            describe=c.get("describe", ""),
        )
        for c in data.get("postcondition", [])
    ]
    return ScenarioSpec(
        id=data["id"],
        task=data["task"],
        domain=data.get("domain", "devops"),
        world=world,
        postcondition=postcondition,
        allowed_tools=tuple(data.get("allowed_tools", ())),
        forbidden_tools=tuple(data.get("forbidden_tools", ())),
        scope=scope,
        budget=budget,
        benign=data.get("benign", True),
        seed_id=data.get("seed_id"),
        mutations=tuple(data.get("mutations", ())),
        seed=data.get("seed", 0),
    )


def dump_scenarios(specs: list[ScenarioSpec]) -> str:
    """Serialise a suite with sorted keys so the file is diff-stable."""
    return json.dumps(
        [scenario_to_dict(s) for s in specs], indent=2, sort_keys=True
    )


def load_scenarios(text: str) -> list[ScenarioSpec]:
    return [scenario_from_dict(d) for d in json.loads(text)]
