"""A clock that never reads the host time.

Real timestamps would make every trace unique and destroy the byte-identical
replay guarantee that the whole regression story rests on. Time advances by a
fixed tick per observation instead.
"""

from __future__ import annotations

# 2026-01-01T00:00:00Z, chosen to be obviously synthetic in reports.
EPOCH = 1_767_225_600
TICK_SECONDS = 7


class DeterministicClock:
    def __init__(self, *, epoch: int = EPOCH, tick: int = TICK_SECONDS) -> None:
        self._epoch = epoch
        self._tick = tick
        self._ticks = 0

    def now(self) -> int:
        """Return the current synthetic unix time and advance."""
        value = self._epoch + self._ticks * self._tick
        self._ticks += 1
        return value

    def peek(self) -> int:
        """Current time without advancing."""
        return self._epoch + self._ticks * self._tick

    def reset(self) -> None:
        self._ticks = 0
