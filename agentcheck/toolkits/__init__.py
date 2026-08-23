"""Built-in toolkits, indexed by domain.

Two domains ship so the engine's generality is demonstrated rather than asserted:
DevOps blast radius is measured in paths, support blast radius is measured in
records and money, and nothing between them is shared except the harness.
"""

from typing import Callable

from ..runtime.tools import Toolset
from .devops import devops_toolset
from .support import support_toolset

TOOLSETS: dict[str, Callable[[], Toolset]] = {
    "devops": devops_toolset,
    "support": support_toolset,
}


def toolset_for(domain: str) -> Toolset:
    if domain not in TOOLSETS:
        raise KeyError(f"no toolkit for domain {domain!r}; have {sorted(TOOLSETS)}")
    return TOOLSETS[domain]()


__all__ = ["TOOLSETS", "toolset_for", "devops_toolset", "support_toolset"]
