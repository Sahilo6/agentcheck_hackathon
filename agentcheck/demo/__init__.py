"""The before/after agent pairs that ship with agentcheck.

These live inside the package rather than in `examples/` for one practical
reason: `agentcheck demo` is the first command anyone runs, and it has to work
from a `pip install` and not only from a source checkout.

Each pair is the same agent written twice: once the way a team writes a first
draft, and once after a guardrail pass. Neither is scripted to fail on cue. They
fail for the reasons real agents fail, which is what makes the contrast worth
showing.
"""

from .devops import HardenedDevOpsAgent, NaiveDevOpsAgent
from .support import HardenedSupportAgent, NaiveSupportAgent

# domain -> (naive, hardened)
DEMO_AGENTS = {
    "devops": (NaiveDevOpsAgent, HardenedDevOpsAgent),
    "support": (NaiveSupportAgent, HardenedSupportAgent),
}

__all__ = [
    "DEMO_AGENTS",
    "HardenedDevOpsAgent",
    "HardenedSupportAgent",
    "NaiveDevOpsAgent",
    "NaiveSupportAgent",
]
