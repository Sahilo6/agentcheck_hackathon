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

from agentcheck.engine import run_suite  # noqa: E402
from agentcheck.gen.builtin import builtin_seeds  # noqa: E402
from agentcheck.gen.mutations import expand  # noqa: E402
from agentcheck.toolkits import toolset_for  # noqa: E402
from agentcheck.demo.devops import HardenedDevOpsAgent, NaiveDevOpsAgent  # noqa: E402
from agentcheck.demo.support import HardenedSupportAgent, NaiveSupportAgent  # noqa: E402

DOMAINS = {
    "devops": (NaiveDevOpsAgent, HardenedDevOpsAgent),
    "support": (NaiveSupportAgent, HardenedSupportAgent),
}


def main() -> None:
    payload = {
        "generated_by": "examples/make_sample_scorecard.py",
        "note": (
            "Deterministic fixture for the web dashboard. Two versions of the same "
            "agent run against an identical suite, in two independent domains. "
            "Regenerate after schema changes."
        ),
        "domains": {},
        "runs": [],
    }

    for domain, (naive, hardened) in DOMAINS.items():
        seeds = builtin_seeds(domain)
        suite = expand(seeds)
        toolset = toolset_for(domain)
        payload["domains"][domain] = {
            "seeds": len(seeds),
            "scenarios": len(suite),
            "seed_ids": [s.id for s in seeds],
        }
        for factory in (naive, hardened):
            card = run_suite(suite, factory, toolset)
            entry = card.to_dict()
            entry["domain"] = domain
            payload["runs"].append(entry)

    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
