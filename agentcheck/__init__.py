"""agentcheck -- continuous integration for autonomous agents.

Generates realistic and adversarial scenarios for an agent, runs them against a
stateful mock world, classifies failures against a documented taxonomy, and
tracks reliability across versions.

The design premise: an agent cannot be evaluated from its final answer alone.
Its trajectory has to be evaluated, and doing that rigorously means owning the
environment -- which in turn means most failure detection needs no LLM at all.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
