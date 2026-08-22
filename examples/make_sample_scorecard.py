"""Generate the scorecard fixture the web dashboard builds against.

Regenerate whenever the scorecard schema changes, so the frontend always has a
truthful contract:

    python3 examples/make_sample_scorecard.py > web/fixtures/sample-scorecard.json

Everything here is deterministic and offline: built-in seeds, code-driven
mutations, and heuristic agents. No API key, no network, identical every run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from agentcheck.engine import run_suite  # noqa: E402
from agentcheck.gen.builtin import builtin_seeds  # noqa: E402
from agentcheck.gen.mutations import expand  # noqa: E402
from agentcheck.toolkits.devops import devops_toolset  # noqa: E402
from demo_agents import HardenedDevOpsAgent, NaiveDevOpsAgent  # noqa: E402


def main() -> None:
    seeds = builtin_seeds()
    suite = expand(seeds)
    toolset = devops_toolset()

    payload = {
        "generated_by": "examples/make_sample_scorecard.py",
        "note": (
            "Deterministic fixture for the web dashboard. Two versions of the same "
            "agent run against an identical suite. Regenerate after schema changes."
        ),
        "suite": {
            "seeds": len(seeds),
            "scenarios": len(suite),
            "seed_ids": [s.id for s in seeds],
        },
        "runs": [],
    }

    for factory in (NaiveDevOpsAgent, HardenedDevOpsAgent):
        card = run_suite(suite, factory, toolset)
        payload["runs"].append(card.to_dict())

    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
