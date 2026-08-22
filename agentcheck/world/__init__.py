"""The mock world an agent under test acts upon.

Owning the environment is what separates agentcheck from an LLM-as-judge wrapper.
Because every tool call lands in a world whose state we control, we know the
ground truth at the end of a run -- so "the agent said it restarted the service"
can be checked against whether it actually did, rather than being scored by
another model's opinion.
"""

from .mock import MockWorld, WorldEvent
from .clock import DeterministicClock

__all__ = ["MockWorld", "WorldEvent", "DeterministicClock"]
