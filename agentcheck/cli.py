"""Command line interface.

Design goal: something useful in one command with no configuration. `agentcheck
demo` runs the whole before/after story offline, because a tool that needs an API
key and a config file before it shows you anything does not get a second look.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

from . import __version__
from .detect.detectors import detect_all
from .detect.taxonomy import TAXONOMY, deterministic_share
from .engine import run_suite
from .gen.builtin import SEEDS_BY_DOMAIN, builtin_seeds
from .gen.mutations import MUTATIONS, expand
from .history.store import (
    append_run,
    build_record,
    diff_runs,
    previous_run,
)
from .report import to_html, to_json, to_junit
from .runtime.trace import Trace
from .spec.models import scenario_from_dict, scenario_to_dict
from .score.scorecard import SEVERITY_ORDER, Scorecard
from .toolkits import toolset_for

# -- terminal helpers -------------------------------------------------------

_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


BOLD = lambda s: _c(s, "1")
DIM = lambda s: _c(s, "2")
RED = lambda s: _c(s, "31")
GREEN = lambda s: _c(s, "32")
YELLOW = lambda s: _c(s, "33")
ORANGE = lambda s: _c(s, "35")

_SEV_COLOR = {"critical": RED, "high": ORANGE, "medium": YELLOW, "low": DIM}


def _sev(text: str) -> str:
    return _SEV_COLOR.get(text, DIM)(text)


# The before/after agent pairs shipped for each domain, used by `agentcheck demo`.
DEMO_PAIRS: dict[str, tuple[str, str, str]] = {
    "devops": ("demo_agents", "NaiveDevOpsAgent", "HardenedDevOpsAgent"),
    "support": ("support_agents", "NaiveSupportAgent", "HardenedSupportAgent"),
}


# -- shared plumbing --------------------------------------------------------


def _load_agent_factory(spec: str):
    """Import an agent from a 'module:Attribute' string.

    This is the general adapter: anything importable that satisfies the three
    method Agent protocol can be tested without touching agentcheck's code.
    """
    module_name, _, attr = spec.partition(":")
    if not attr:
        raise SystemExit(f"--agent must look like 'module:ClassName', got {spec!r}")
    for extra in (Path.cwd(), Path.cwd() / "examples"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise SystemExit(f"could not import {module_name!r}: {exc}")
    try:
        return getattr(module, attr)
    except AttributeError:
        raise SystemExit(f"{module_name!r} has no attribute {attr!r}")


def _build_suite(args) -> list:
    seeds = builtin_seeds(args.domain)
    if args.seeds_only:
        return seeds
    return expand(seeds, pairs=not args.no_pairs)


def _print_scorecard(card: Scorecard, *, top: int = 5) -> None:
    rate = card.pass_rate
    colour = GREEN if rate >= 0.9 else (YELLOW if rate >= 0.6 else RED)
    print()
    print(f"  {BOLD(card.agent_id)}")
    print(
        f"  {colour(f'{rate:.0%} pass')}  "
        f"{card.passed}/{card.total} scenarios  "
        f"{DIM(f'weighted score {card.weighted_score:.0f}')}"
    )

    counts = card.by_severity()
    if any(counts.values()):
        parts = [f"{_sev(s)} {counts[s]}" for s in SEVERITY_ORDER if counts[s]]
        print("  " + "  ".join(parts))
        print()
        for mode, n in card.by_mode().items():
            print(f"    {n:>4}  {_sev(TAXONOMY[mode].severity):<20} {mode}")
    else:
        print(f"  {GREEN('no findings')}")

    det, total = card.deterministic_finding_share()
    if total:
        print()
        print(DIM(f"  {det}/{total} findings decided without a model"))

    failures = card.failures()
    if failures:
        print()
        print(f"  {BOLD('worst failures')}")
        for result in failures[:top]:
            print(f"    {_sev(result.worst_severity or 'low'):<20} {result.spec.id}")
            for finding in result.findings[:2]:
                print(DIM(f"        {finding.summary}"))
    print()


# -- commands ---------------------------------------------------------------


def cmd_run(args) -> int:
    suite = _build_suite(args)
    factory = _load_agent_factory(args.agent)
    toolset = toolset_for(args.domain)

    total = len(suite)
    print(f"Running {BOLD(str(total))} scenarios against {BOLD(args.agent)} ...")

    def progress(index, count, result):
        if not _COLOR:
            return
        mark = GREEN("*") if result.passed else RED("x")
        sys.stdout.write(f"\r  {mark} {index}/{count}")
        sys.stdout.flush()

    card = run_suite(suite, factory, toolset, on_progress=progress)
    if _COLOR:
        sys.stdout.write("\r" + " " * 40 + "\r")

    _print_scorecard(card)

    diff = None
    if args.history:
        # Regression compares one logical agent across versions. The class name
        # usually changes when the agent is rewritten, so --label pins a stable
        # identity for the history lineage.
        if args.label:
            card.agent_id = args.label
        record = build_record(card, specs=suite)
        baseline = previous_run(args.history, agent_id=card.agent_id)
        if baseline is not None:
            diff = diff_runs(baseline, record)
            if not diff.comparable:
                print(YELLOW("  baseline ran a different suite; not comparable"))
            else:
                print(f"  {BOLD('vs previous run')}: {diff.summary()}")
                for sid in diff.new_failures[:5]:
                    print(RED(f"    new failure: {sid}"))
            print()
        append_run(record, args.history)

    if args.out:
        Path(args.out).write_text(to_html(card, title=f"agentcheck: {card.agent_id}", diff=diff))
        print(DIM(f"  html   {args.out}"))
    if args.json:
        Path(args.json).write_text(to_json(card))
        print(DIM(f"  json   {args.json}"))
    if args.junit:
        Path(args.junit).write_text(to_junit(card))
        print(DIM(f"  junit  {args.junit}"))
    if args.out or args.json or args.junit:
        print()

    if args.fail_on_new:
        # Regression gating: only NEW failures break the build. Failing on the
        # existing backlog would make the tool impossible to adopt on a codebase
        # that already has problems.
        if diff is None:
            print(DIM("  no baseline yet; recorded this run as the baseline"))
            return 0
        if diff.regressed:
            print(RED(f"  FAIL: {len(diff.new_failures)} new failure(s) since the baseline"))
            return 1
        print(GREEN("  OK: no new failures"))
        return 0

    return 1 if args.fail_on_findings and card.passed < card.total else 0


def cmd_demo(args) -> int:
    """The before/after story, offline, in one command."""
    suite = _build_suite(args)
    toolset = toolset_for(args.domain)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))
    module_name, naive_name, hardened_name = DEMO_PAIRS[args.domain]
    try:
        module = importlib.import_module(module_name)
        naive = getattr(module, naive_name)
        hardened = getattr(module, hardened_name)
    except (ImportError, AttributeError):
        raise SystemExit(
            "demo agents not found. Run this from a source checkout, "
            "or use `agentcheck run --agent module:Class`."
        )

    print()
    print(BOLD(f"  {len(suite)} scenarios from {len(builtin_seeds(args.domain))} seeds"))
    print(DIM("  generated offline by the mutation ladder, no API calls"))

    cards = []
    for factory in (naive, hardened):
        card = run_suite(suite, factory, toolset)
        cards.append(card)
        _print_scorecard(card, top=3)

    before, after = cards
    print(BOLD("  the gap"))
    print(
        f"    {RED(f'{before.pass_rate:.0%}')} -> {GREEN(f'{after.pass_rate:.0%}')}"
        f"  on the identical suite, after adding guardrails"
    )
    base = [r for r in before.results if not r.spec.mutations]
    mutated = [r for r in before.results if r.spec.mutations]
    if base and mutated:
        base_rate = sum(r.passed for r in base) / len(base)
        mut_rate = sum(r.passed for r in mutated) / len(mutated)
        print(
            f"    hand-written-style scenarios pass at {GREEN(f'{base_rate:.0%}')}, "
            f"adversarial variants at {RED(f'{mut_rate:.0%}')}"
        )
    print(DIM("    the second agent produced zero findings across every scenario"))
    print()

    if args.out:
        Path(args.out).write_text(to_html(before, title=f"agentcheck: {before.agent_id}"))
        print(DIM(f"  html  {args.out}"))
        print()
    return 0


def cmd_scenarios(args) -> int:
    suite = _build_suite(args)
    if args.count:
        print(len(suite))
        return 0
    for spec in suite:
        chips = f" [{', '.join(spec.mutations)}]" if spec.mutations else ""
        print(f"{spec.id}{DIM(chips)}")
        if args.verbose:
            print(DIM(f"    {spec.task}"))
            for cond in spec.postcondition:
                print(DIM(f"      expect {cond.kind} {cond.args}"))
    return 0


def cmd_taxonomy(args) -> int:
    det, total = deterministic_share()
    print()
    print(BOLD("  failure taxonomy"))
    print(DIM(f"  {det} of {total} modes are decided without a model"))
    print()
    for mode in sorted(TAXONOMY.values(), key=lambda m: SEVERITY_ORDER.index(m.severity)):
        flag = GREEN("no LLM") if mode.deterministic else YELLOW("model-assisted")
        print(f"  {_sev(mode.severity):<20} {BOLD(mode.id)}  {flag}")
        print(DIM(f"      {mode.description}"))
        print(DIM(f"      fix: {mode.remediation}"))
        print()
    return 0


def cmd_mutations(args) -> int:
    print()
    print(BOLD("  adversarial mutations"))
    print(DIM("  applied by code, not by a model, so expansion is free and repeatable"))
    print()
    for mutation in MUTATIONS:
        print(f"  {BOLD(mutation.name)}")
        print(DIM(f"      {mutation.description}"))
        print(DIM(f"      probes: {mutation.probes}"))
    print()
    return 0


def cmd_generate(args) -> int:
    from .gen.seeds import generate_seeds

    report = generate_seeds(
        toolset_for(args.domain),
        domain=args.domain,
        count=args.count,
        provider=args.provider,
        model=args.model,
        refresh=args.refresh,
    )
    print(f"  {report.summary()}")
    for spec in report.seeds:
        print(f"    {spec.id}: {spec.task[:80]}")
    for bad in report.rejected:
        print(YELLOW(f"    rejected {bad.get('id', '?')}: {bad['reason']}"))
    return 0


def _find_scenario(args):
    suite = _build_suite(args)
    for spec in suite:
        if spec.id == args.scenario:
            return spec
    matches = [s.id for s in suite if args.scenario in s.id][:8]
    hint = ("\n  did you mean:\n    " + "\n    ".join(matches)) if matches else ""
    raise SystemExit(f"no scenario {args.scenario!r} in domain {args.domain!r}{hint}")


def cmd_mcp_serve(args) -> int:
    """Stand up one scenario as an MCP server on stdio.

    Everything the agent sees arrives over the wire, so any MCP client works
    without writing an adapter. Logging goes to stderr because stdout is the
    protocol channel.
    """
    from .mcp.server import ScenarioServer

    spec = _find_scenario(args)
    server = ScenarioServer(spec, toolset_for(args.domain), agent_id=args.label or "mcp-client")
    print(f"agentcheck mcp: serving {spec.id} ({args.domain})", file=sys.stderr)

    trace = server.serve(sys.stdin, sys.stdout)

    findings = detect_all(spec, trace)
    print(
        f"agentcheck mcp: {len(trace.calls)} tool call(s), "
        f"{len(findings)} finding(s), stopped={trace.stopped}",
        file=sys.stderr,
    )
    for finding in findings:
        print(f"  [{finding.severity}] {finding.mode}: {finding.summary}", file=sys.stderr)

    if args.out:
        Path(args.out).write_text(
            json.dumps(
                {"spec": scenario_to_dict(spec), "trace": trace.to_dict()},
                indent=2,
                sort_keys=True,
            )
        )
        print(f"agentcheck mcp: wrote {args.out}", file=sys.stderr)
    return 1 if findings else 0


def cmd_score(args) -> int:
    """Score a run recorded by `mcp-serve`, offline."""
    payload = json.loads(Path(args.run).read_text())
    spec = scenario_from_dict(payload["spec"])
    trace = Trace.from_dict(payload["trace"])
    findings = detect_all(spec, trace)

    print()
    print(f"  {BOLD(spec.id)}  {DIM(spec.task[:90])}")
    print(f"  fingerprint {trace.fingerprint()}  stopped={trace.stopped}  "
          f"{len(trace.calls)} tool call(s)")
    print()
    if not findings:
        print(f"  {GREEN('no findings')}")
    for finding in findings:
        print(f"  {_sev(finding.severity):<20} {finding.mode}")
        print(DIM(f"      {finding.summary}"))
    print()
    return 1 if findings else 0


# -- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentcheck",
        description="Continuous integration for autonomous agents.",
    )
    parser.add_argument("--version", action="version", version=f"agentcheck {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_suite_args(p):
        p.add_argument("--domain", default="devops", choices=sorted(SEEDS_BY_DOMAIN))
        p.add_argument("--seeds-only", action="store_true",
                       help="skip the mutation ladder (base scenarios only)")
        p.add_argument("--no-pairs", action="store_true",
                       help="apply mutations singly, not in combination")

    p_run = sub.add_parser("run", help="run a suite against an agent")
    add_suite_args(p_run)
    p_run.add_argument("--agent", required=True, metavar="module:Class")
    p_run.add_argument("--out", metavar="FILE", help="write an HTML report")
    p_run.add_argument("--json", metavar="FILE", help="write a JSON report")
    p_run.add_argument("--junit", metavar="FILE", help="write JUnit XML for CI")
    p_run.add_argument("--history", metavar="FILE", help="append to a run history JSONL")
    p_run.add_argument("--label", metavar="NAME",
                       help="stable agent name for history (defaults to the class id)")
    p_run.add_argument("--fail-on-new", action="store_true",
                       help="exit 1 only if new failures appeared since the baseline")
    p_run.add_argument("--fail-on-findings", action="store_true",
                       help="exit 1 if any scenario fails")
    p_run.set_defaults(func=cmd_run)

    p_demo = sub.add_parser("demo", help="run the before/after contrast offline")
    add_suite_args(p_demo)
    p_demo.add_argument("--out", metavar="FILE", help="write an HTML report")
    p_demo.set_defaults(func=cmd_demo)

    p_scen = sub.add_parser("scenarios", help="list the generated suite")
    add_suite_args(p_scen)
    p_scen.add_argument("-v", "--verbose", action="store_true")
    p_scen.add_argument("--count", action="store_true", help="print the count only")
    p_scen.set_defaults(func=cmd_scenarios)

    p_tax = sub.add_parser("taxonomy", help="print the failure taxonomy")
    p_tax.set_defaults(func=cmd_taxonomy)

    p_mut = sub.add_parser("mutations", help="print the adversarial mutation ladder")
    p_mut.set_defaults(func=cmd_mutations)

    p_gen = sub.add_parser("generate", help="generate seed scenarios with an LLM")
    p_gen.add_argument("--domain", default="devops")
    p_gen.add_argument("--count", type=int, default=12)
    p_gen.add_argument("--provider", help="groq, openrouter, together, ollama")
    p_gen.add_argument("--model")
    p_gen.add_argument("--refresh", action="store_true", help="ignore the cache")
    p_gen.set_defaults(func=cmd_generate)

    p_mcp = sub.add_parser(
        "mcp-serve",
        help="serve one scenario as an MCP server on stdio (for any MCP agent)",
    )
    add_suite_args(p_mcp)
    p_mcp.add_argument("--scenario", required=True, help="scenario id to serve")
    p_mcp.add_argument("--label", help="name recorded as the agent under test")
    p_mcp.add_argument("--out", metavar="FILE", help="write the recorded run as JSON")
    p_mcp.set_defaults(func=cmd_mcp_serve)

    p_score = sub.add_parser("score", help="score a run recorded by mcp-serve")
    p_score.add_argument("run", metavar="FILE")
    p_score.set_defaults(func=cmd_score)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
