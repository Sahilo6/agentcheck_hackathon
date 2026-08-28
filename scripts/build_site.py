#!/usr/bin/env python3
"""Build the public site: dashboard, deck, and a sample report at one URL.

    python3 scripts/build_site.py

The submission asks for a hosted prototype link. This assembles everything a
judge would want to click into a single static directory that can be served from
GitHub Pages, with no backend and no API key.

    site/
      index.html      the dashboard
      deck.html       the slides
      report.html     a real HTML report from a real run
      report-clean.html   the same suite against the hardened agent
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
WEB = ROOT / "web"

sys.path.insert(0, str(ROOT))


def run(argv: list[str], cwd: Path) -> None:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"failed: {' '.join(argv)}\n{result.stdout}\n{result.stderr}")


def build_reports() -> None:
    """Generate real reports rather than shipping a screenshot of one."""
    from agentcheck.demo import DEMO_AGENTS
    from agentcheck.engine import run_suite
    from agentcheck.gen.builtin import builtin_seeds
    from agentcheck.gen.mutations import expand
    from agentcheck.report import to_html
    from agentcheck.toolkits import toolset_for

    suite = expand(builtin_seeds("devops"))
    toolset = toolset_for("devops")
    naive, hardened = DEMO_AGENTS["devops"]

    for factory, name in ((naive, "report.html"), (hardened, "report-clean.html")):
        card = run_suite(suite, factory, toolset)
        (SITE / name).write_text(
            to_html(card, title=f"agentcheck: {card.agent_id}"), encoding="utf-8"
        )
        _, findings = card.deterministic_finding_share()
        print(f"  {name}: {card.passed}/{card.total} pass, {findings} findings")


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()

    print("building the dashboard...")
    if not (WEB / "node_modules").exists():
        run(["npm", "ci"], WEB)
    run(["npm", "run", "build"], WEB)
    shutil.copytree(WEB / "dist", SITE, dirs_exist_ok=True)

    print("generating the deck...")
    run([sys.executable, "docs/build_deck.py"], ROOT)
    shutil.copy(ROOT / "docs" / "deck.html", SITE / "deck.html")

    print("generating reports...")
    build_reports()

    # Pages serves 404.html for unknown paths; pointing it at the app means a
    # deep link still lands somewhere useful instead of a GitHub error page.
    shutil.copy(SITE / "index.html", SITE / "404.html")

    total = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"\nsite/ ready: {total / 1024 / 1024:.1f} MB")
    for f in sorted(SITE.glob("*.html")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
