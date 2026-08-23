"""JUnit XML output, so CI shows failures where engineers already look.

Every CI system can render JUnit. Emitting it means agentcheck failures appear
in the PR checks tab as named test cases rather than buried in a log, which is
the difference between a tool teams adopt and one they run once.
"""

from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from ..score.scorecard import Scorecard


def _detail(result) -> str:
    lines = [f"task: {result.spec.task}", ""]
    if result.spec.mutations:
        lines.append(f"mutations: {', '.join(result.spec.mutations)}")
    lines.append(f"fingerprint: {result.trace.fingerprint()}  (reproducible)")
    lines.append("")
    for finding in result.findings:
        lines.append(f"[{finding.severity}] {finding.mode}: {finding.summary}")
    if result.trace.calls:
        lines.append("")
        lines.append("trace:")
        for call in result.trace.calls:
            mark = "  " if call.ok else "! "
            lines.append(f"  {mark}{call.step}. {call.tool}({call.args}) -> {call.result[:120]}")
    if result.trace.final_message:
        lines.append("")
        lines.append(f"agent said: {result.trace.final_message}")
    return "\n".join(lines)


def to_junit(card: Scorecard, *, suite_name: str = "agentcheck") -> str:
    failures = card.total - card.passed
    out = ['<?xml version="1.0" encoding="UTF-8"?>']
    out.append(
        f'<testsuites name={quoteattr(suite_name)} tests="{card.total}" '
        f'failures="{failures}">'
    )
    out.append(
        f'  <testsuite name={quoteattr(card.agent_id)} tests="{card.total}" '
        f'failures="{failures}">'
    )
    for result in card.results:
        # Group by seed so CI collapses the mutation family of one base task.
        classname = result.spec.seed_id or result.spec.domain or "scenario"
        out.append(
            f"    <testcase classname={quoteattr(classname)} "
            f"name={quoteattr(result.spec.id)} time=\"0\">"
        )
        if not result.passed:
            worst = result.findings[0] if result.findings else None
            message = (
                f"{worst.mode}: {worst.summary}" if worst else "scenario failed"
            )
            out.append(
                f"      <failure message={quoteattr(message)} "
                f"type={quoteattr(worst.mode if worst else 'failure')}>"
            )
            out.append(escape(_detail(result)))
            out.append("      </failure>")
        out.append("    </testcase>")
    out.append("  </testsuite>")
    out.append("</testsuites>")
    return "\n".join(out) + "\n"
