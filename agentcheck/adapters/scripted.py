"""A scripted agent: fixed actions, no model, no network.

Used for testing the harness and the detectors. Because every detector is a pure
function over a trace, a scripted agent can reproduce any failure mode exactly,
which means the taxonomy is covered by fast deterministic tests instead of by
hoping a live model misbehaves on cue.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..runtime.agent import Action, FinishAction, Observation


class ScriptedAgent:
    """Replays a fixed list of actions, then finishes."""

    def __init__(
        self,
        actions: Iterable[Action],
        *,
        id: str = "scripted",
        final: str = "Done.",
    ) -> None:
        self._actions = list(actions)
        self.id = id
        self._final = final
        self._index = 0
        self.seen: list[Observation | None] = []

    def begin(self, task: str, tools: list[dict[str, Any]]) -> None:
        self._index = 0
        self.seen = []

    def step(self, observation: Observation | None) -> Action:
        self.seen.append(observation)
        if self._index >= len(self._actions):
            return FinishAction(self._final)
        action = self._actions[self._index]
        self._index += 1
        return action


class LoopingAgent:
    """Repeats one action forever -- the tool-call-loop failure mode."""

    def __init__(self, action: Action, *, id: str = "looper") -> None:
        self._action = action
        self.id = id

    def begin(self, task: str, tools: list[dict[str, Any]]) -> None:
        pass

    def step(self, observation: Observation | None) -> Action:
        return self._action
