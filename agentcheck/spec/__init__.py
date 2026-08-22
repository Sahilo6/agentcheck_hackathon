"""Scenario specifications: the checkable contract for a single agent test.

The central design decision of agentcheck lives here. A scenario is *not* a prompt.
A prompt can only be judged by opinion; a spec carries a machine-checkable
postcondition, so the verdict is a property check against known ground truth.
"""

from .models import (
    Budget,
    Condition,
    ScenarioSpec,
    Scope,
    WorldSpec,
    scenario_from_dict,
    scenario_to_dict,
)

__all__ = [
    "Budget",
    "Condition",
    "ScenarioSpec",
    "Scope",
    "WorldSpec",
    "scenario_from_dict",
    "scenario_to_dict",
]
