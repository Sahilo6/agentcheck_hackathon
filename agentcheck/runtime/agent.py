"""The contract an agent under test must satisfy.

Kept deliberately small -- three methods -- so that wrapping an existing agent
(LangChain, a raw LLM loop, an MCP client) is a short adapter rather than a
rewrite. The harness drives the loop; the agent only decides the next move.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolAction:
    """The agent wants to call a tool."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinishAction:
    """The agent considers the task complete (or declines to continue)."""

    message: str


Action = ToolAction | FinishAction


@dataclass(frozen=True)
class Observation:
    """What the agent sees after a tool call."""

    tool: str
    ok: bool
    result: str


@runtime_checkable
class Agent(Protocol):
    """An agent under test."""

    id: str

    def begin(self, task: str, tools: list[dict[str, Any]]) -> None:
        """Start a fresh episode. Must clear any state from a previous run."""
        ...

    def step(self, observation: Observation | None) -> Action:
        """Decide the next action given the most recent tool result.

        `observation` is None on the first step.
        """
        ...
