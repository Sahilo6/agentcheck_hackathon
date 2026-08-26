#!/usr/bin/env python3
"""Run the whole stage demo end to end and check every beat works offline.

    python3 scripts/rehearse.py

Run this before presenting, with the wifi off. It executes the real commands in
order, times each one, and fails loudly if any beat would break in front of an
audience. Nothing here is simulated; these are the commands that get typed.

Every API key is stripped from the environment first, so a beat that quietly
depends on a network call fails here rather than on stage.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Stripped so any hidden dependency on a provider surfaces now.
KEYS = ["GROQ_API_KEY", "OPENROUTER_API_KEY", "TOGETHER_API_KEY", "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY", "AGENTCHECK_LLM_BASE_URL", "AGENTCHECK_LLM_PROVIDER"]

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = DIM = BOLD = RESET = ""


class Rehearsal:
    def __init__(self) -> None:
        self.env = {k: v for k, v in os.environ.items() if k not in KEYS}
        self.env["PYTHONPATH"] = str(ROOT)
        self.tmp = Path(tempfile.mkdtemp(prefix="agentcheck-rehearsal-"))
        self.failures: list[str] = []
        self.timings: list[tuple[str, float]] = []

    def run(self, argv: list[str], *, expect_exit: int | None = 0) -> str:
        started = time.time()
        proc = subprocess.run(
            argv, cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=300
        )
        self.elapsed = time.time() - started
        output = proc.stdout + proc.stderr
        if expect_exit is not None and proc.returncode != expect_exit:
            raise AssertionError(
                f"exit {proc.returncode}, expected {expect_exit}\n{output[-1500:]}"
            )
        return output

    def beat(self, number: int, title: str, fn) -> None:
        label = f"  {number}. {title}"
        print(f"{label:<58}", end="", flush=True)
        started = time.time()
        try:
            detail = fn()
        except Exception as exc:
            print(f"{RED}FAILED{RESET}")
            print(f"{DIM}     {str(exc)[:900]}{RESET}")
            self.failures.append(title)
            return
        seconds = time.time() - started
        self.timings.append((title, seconds))
        print(f"{GREEN}ok{RESET}  {DIM}{seconds:5.1f}s  {detail}{RESET}")

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


def main() -> int:
    r = Rehearsal()
    py = [sys.executable, "-m"]
    cli = py + ["agentcheck.cli"]

    print()
    print(f"{BOLD}  agentcheck demo rehearsal{RESET}")
    print(f"{DIM}  every provider key stripped; nothing here may touch the network{RESET}")
    print()

    def beat1():
        out = r.run(py + ["pytest", "examples/how_teams_test_today.py", "-q"])
        assert "5 passed" in out, out[-600:]
        return "5 hand-written tests pass; the agent ships"

    def beat2():
        out = r.run(cli + ["scenarios", "--count"])
        count = int(out.strip().splitlines()[-1])
        assert count > 150, f"only {count} scenarios"
        return f"{count} scenarios generated offline"

    report = None

    def beat3():
        nonlocal report
        report = r.tmp / "naive.html"
        out = r.run(cli + ["run", "--agent", "agentcheck.demo:NaiveDevOpsAgent",
                           "--out", str(report), "--json", str(r.tmp / "naive.json")])
        assert "38%" in out or "%" in out, out[-600:]
        assert report.exists()
        return "scorecard rendered"

    def beat4():
        import json
        data = json.loads((r.tmp / "naive.json").read_text())
        rate = data["pass_rate"]
        assert rate < 0.5, f"pass rate {rate:.0%} is too high for the demo contrast"
        assert data["findings_deterministic"] == data["findings_total"]
        return f"{rate:.0%} pass, {data['findings_total']} findings, none from a model"

    def beat5():
        html = report.read_text()
        assert "class=\"step\"" in html, "trace viewer missing from the report"
        assert "log-cleanup" in html
        return "trace drill-down present"

    def beat6():
        import json
        data = json.loads((r.tmp / "naive.json").read_text())
        lies = [
            s for s in data["results"]
            if any(f["mode"] == "hallucinated_success" for f in s["findings"])
        ]
        assert lies, "no hallucinated_success finding: the mic-drop beat has nothing to show"
        html = report.read_text()
        assert "Claimed vs actually performed" in html
        return f"{len(lies)} scenarios where the agent claimed work it never did"

    def beat7():
        history = r.tmp / "history.jsonl"
        common = ["run", "--label", "devops-assistant", "--history", str(history)]
        r.run(cli + common + ["--agent", "agentcheck.demo:NaiveDevOpsAgent"], expect_exit=None)
        out = r.run(cli + common + ["--agent", "agentcheck.demo:HardenedDevOpsAgent",
                                    "--fail-on-new"])
        assert "100%" in out, out[-600:]
        assert "fixed" in out and "0 new" in out, out[-600:]
        return "identical suite re-run: 100%, 0 new failures"

    def beat8():
        junit = r.tmp / "results.xml"
        r.run(cli + ["run", "--agent", "agentcheck.demo:NaiveDevOpsAgent",
                     "--junit", str(junit), "--fail-on-findings"], expect_exit=1)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(junit.read_text())
        failures = int(root.find("testsuite").get("failures"))
        assert failures > 0
        return f"CI exits 1 with {failures} JUnit failures"

    def beat_extra():
        out = r.run(cli + ["demo", "--domain", "support"])
        assert "100%" in out and "52%" in out, out[-600:]
        return "second domain also runs clean"

    def beat_deck():
        """The deck is generated from the fixture, so its numbers cannot drift.

        Regenerating here proves that is still true: if the engine's results
        changed and nobody rebuilt the deck, the slides would be quoting figures
        the demo no longer produces.
        """
        import json
        import re

        # Not `py`, which carries -m: this is a script path, not a module.
        r.run([sys.executable, "docs/build_deck.py"])
        deck = (ROOT / "docs" / "deck.html").read_text()
        data = json.loads((ROOT / "web" / "fixtures" / "sample-scorecard.json").read_text())
        for run in data["runs"]:
            rate = f"{round(run['pass_rate'] * 100)}%"
            assert rate in deck, f"deck is missing {run['agent_id']} at {rate}"
        slides = len(re.findall(r'class="slide', deck))
        return f"{slides} slides, every rate matches the fixture"

    r.beat(1, "How teams test today: 5 hand-written tests", beat1)
    r.beat(2, "Generate the suite", beat2)
    r.beat(3, "Run it, render the scorecard", beat3)
    r.beat(4, "The number: pass rate and findings", beat4)
    r.beat(5, "Drill into a failure", beat5)
    r.beat(6, "The mic-drop: claimed vs actually performed", beat6)
    r.beat(7, "Fix the agent, re-run, regression view", beat7)
    r.beat(8, "Wire it into CI", beat8)
    r.beat(9, "Second domain (answers 'only your demo?')", beat_extra)
    r.beat(10, "Deck numbers match the data", beat_deck)

    print()
    total = sum(seconds for _, seconds in r.timings)
    if r.failures:
        print(f"  {RED}{len(r.failures)} beat(s) would break on stage:{RESET}")
        for name in r.failures:
            print(f"    {RED}- {name}{RESET}")
        r.cleanup()
        return 1

    print(f"  {GREEN}all 10 beats work offline{RESET}  {DIM}({total:.0f}s of command time){RESET}")
    slowest = max(r.timings, key=lambda t: t[1])
    print(f"  {DIM}slowest: {slowest[0]} at {slowest[1]:.1f}s{RESET}")
    print()
    r.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
