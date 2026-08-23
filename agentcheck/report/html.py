"""A self-contained HTML report.

No external assets, no CDN, no build step: one file that opens anywhere,
including on a conference wifi that is not working. Everything the report
asserts is traceable to the trace shown beside it.
"""

from __future__ import annotations

import html
import json
from typing import Any

from ..detect.taxonomy import TAXONOMY, deterministic_share
from ..history.store import RegressionDiff
from ..score.scorecard import SEVERITY_ORDER, Scorecard

_CSS = """
:root{--bg:#0b0f17;--panel:#131a26;--panel2:#0f1520;--line:#233046;--fg:#e6edf7;
--dim:#8ba0bd;--critical:#ef4444;--high:#f97316;--medium:#eab308;--low:#64748b;
--pass:#22c55e;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:28px;margin:0 0 4px}
h2{font-size:19px;margin:40px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.sub{color:var(--dim);margin:0 0 28px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px}
.card .n{font-size:32px;font-weight:650;line-height:1.1}
.card .l{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.06em;
margin-top:6px}
.bar{display:flex;height:10px;border-radius:6px;overflow:hidden;margin:18px 0 8px;
background:var(--panel2)}
.bar span{display:block}
.legend{display:flex;gap:18px;flex-wrap:wrap;color:var(--dim);font-size:13px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--dim);font-weight:500;font-size:12px;text-transform:uppercase;
letter-spacing:.05em}
.mono{font-family:var(--mono);font-size:13px}
.pill{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;
font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.chip{display:inline-block;padding:2px 8px;border-radius:5px;font-size:11px;
background:var(--panel2);border:1px solid var(--line);color:var(--dim);
margin:0 4px 4px 0;font-family:var(--mono)}
details{background:var(--panel);border:1px solid var(--line);border-radius:10px;
margin-bottom:10px;overflow:hidden}
details summary{padding:14px 18px;cursor:pointer;display:flex;gap:12px;
align-items:center;flex-wrap:wrap}
details summary::-webkit-details-marker{display:none}
details[open] summary{border-bottom:1px solid var(--line)}
.body{padding:18px}
.task{color:var(--dim);font-size:14px;margin-bottom:16px}
.finding{border-left:3px solid var(--line);padding:10px 14px;margin-bottom:10px;
background:var(--panel2);border-radius:0 8px 8px 0}
.finding .t{font-weight:600;margin-bottom:3px}
.finding .s{color:var(--dim);font-size:13px}
.rem{color:var(--dim);font-size:12.5px;margin-top:7px;font-style:italic}
pre{background:var(--panel2);border:1px solid var(--line);border-radius:8px;
padding:12px 14px;overflow-x:auto;font-family:var(--mono);font-size:12.5px;margin:8px 0}
.step{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}
.step:last-child{border-bottom:0}
.step .i{color:var(--dim);font-family:var(--mono);min-width:26px}
.claim{background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.35);
border-radius:8px;padding:12px 14px;margin-top:12px}
.claim .h{font-size:11px;text-transform:uppercase;letter-spacing:.06em;
color:var(--critical);font-weight:650;margin-bottom:5px}
.ok{color:var(--pass)}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--pass);
border-radius:0 10px 10px 0;padding:14px 18px;margin:18px 0;color:var(--dim);font-size:14px}
"""


def _sev_color(sev: str) -> str:
    return f"var(--{sev})"


def _esc(text: Any) -> str:
    return html.escape(str(text))


def _pill(sev: str) -> str:
    return (
        f'<span class="pill" style="background:{_sev_color(sev)}22;'
        f'color:{_sev_color(sev)}">{_esc(sev)}</span>'
    )


def _severity_bar(card: Scorecard) -> str:
    counts = card.by_severity()
    total = sum(counts.values())
    if not total:
        return '<div class="note">No findings. Every scenario came back clean.</div>'
    segments = "".join(
        f'<span style="width:{counts[s] / total * 100:.2f}%;background:{_sev_color(s)}"></span>'
        for s in SEVERITY_ORDER
        if counts[s]
    )
    legend = "".join(
        f'<span><i class="dot" style="background:{_sev_color(s)}"></i>'
        f"{counts[s]} {s}</span>"
        for s in SEVERITY_ORDER
        if counts[s]
    )
    return f'<div class="bar">{segments}</div><div class="legend">{legend}</div>'


def _trace_block(result) -> str:
    rows = []
    for call in result.trace.calls:
        args = ", ".join(f"{k}={json.dumps(v)}" for k, v in call.args.items())
        mark = '<span class="ok">ok</span>' if call.ok else '<span style="color:var(--critical)">err</span>'
        rows.append(
            f'<div class="step"><span class="i">{call.step}</span>'
            f'<span class="mono" style="flex:1">{_esc(call.tool)}({_esc(args)})'
            f'<br><span style="color:var(--dim)">&rarr; {_esc(call.result[:200])}</span></span>'
            f"<span>{mark}</span></div>"
        )
    trace_html = "".join(rows) or '<div class="step"><span style="color:var(--dim)">No tool calls.</span></div>'

    claim = ""
    if result.trace.final_message:
        halluc = [f for f in result.findings if f.mode == "hallucinated_success"]
        changed = [e["op"] for e in result.trace.journal] or ["nothing"]
        if halluc:
            # The centrepiece contrast: what it said, against what the journal
            # shows it did. This is a state check, not an opinion.
            claim = (
                f'<div class="claim"><div class="h">Claimed vs actually performed</div>'
                f'<div>&ldquo;{_esc(result.trace.final_message)}&rdquo;</div>'
                f'<div class="mono" style="margin-top:8px;color:var(--dim)">'
                f'world journal recorded: {_esc(", ".join(sorted(set(changed))))}</div></div>'
            )
        else:
            claim = (
                f'<div style="margin-top:12px;color:var(--dim)">'
                f'Agent said: &ldquo;{_esc(result.trace.final_message)}&rdquo;</div>'
            )
    return f"<pre style='padding:4px 14px'>{trace_html}</pre>{claim}"


def _finding_block(finding) -> str:
    evidence = ""
    if finding.evidence:
        evidence = f"<pre>{_esc(json.dumps(finding.evidence, indent=2)[:1400])}</pre>"
    remediation = TAXONOMY[finding.mode].remediation
    return (
        f'<div class="finding" style="border-left-color:{_sev_color(finding.severity)}">'
        f'<div class="t">{_pill(finding.severity)} {_esc(finding.title)}</div>'
        f'<div class="s">{_esc(finding.summary)}</div>'
        f"{evidence}"
        f'<div class="rem">Fix: {_esc(remediation)}</div></div>'
    )


def _scenario_block(result) -> str:
    chips = "".join(f'<span class="chip">{_esc(m)}</span>' for m in result.spec.mutations)
    sev = result.worst_severity or "low"
    return (
        f"<details><summary>"
        f"{_pill(sev)}<span class='mono'>{_esc(result.spec.id)}</span>"
        f"<span style='margin-left:auto;color:var(--dim);font-size:12px'>"
        f"{len(result.findings)} finding(s) &middot; "
        f"{len(result.trace.calls)} tool call(s)</span>"
        f"</summary><div class='body'>"
        f"<div class='task'>{_esc(result.spec.task)}</div>"
        f"<div>{chips}</div>"
        f"{''.join(_finding_block(f) for f in result.findings)}"
        f"<h3 style='font-size:13px;color:var(--dim);text-transform:uppercase;"
        f"letter-spacing:.05em;margin:18px 0 4px'>Trace "
        f"<span class='mono' style='text-transform:none;letter-spacing:0'>"
        f"({_esc(result.trace.fingerprint())})</span></h3>"
        f"{_trace_block(result)}"
        f"</div></details>"
    )


def to_html(
    card: Scorecard,
    *,
    title: str = "agentcheck report",
    diff: RegressionDiff | None = None,
    max_scenarios: int = 40,
) -> str:
    det_modes, total_modes = deterministic_share()
    det_found, total_found = card.deterministic_finding_share()

    failures = card.failures()
    shown = failures[:max_scenarios]
    truncated = (
        f'<p class="sub">Showing the {len(shown)} most severe of {len(failures)} '
        f"failing scenarios.</p>"
        if len(failures) > len(shown)
        else ""
    )

    mode_rows = "".join(
        f"<tr><td class='mono'>{_esc(mode)}</td>"
        f"<td>{_pill(TAXONOMY[mode].severity)}</td>"
        f"<td>{count}</td>"
        f"<td style='color:var(--dim)'>{_esc(TAXONOMY[mode].description)}</td></tr>"
        for mode, count in card.by_mode().items()
    ) or "<tr><td colspan='4' style='color:var(--dim)'>No findings.</td></tr>"

    regression = ""
    if diff is not None:
        if not diff.comparable:
            regression = (
                '<div class="note" style="border-left-color:var(--medium)">'
                "Baseline ran a different suite, so these runs are not comparable. "
                "No regression claim is made.</div>"
            )
        else:
            regression = (
                f'<div class="cards">'
                f'<div class="card"><div class="n ok">{len(diff.fixed)}</div>'
                f'<div class="l">fixed</div></div>'
                f'<div class="card"><div class="n" style="color:'
                f'{"var(--critical)" if diff.new_failures else "var(--pass)"}">'
                f'{len(diff.new_failures)}</div><div class="l">new failures</div></div>'
                f'<div class="card"><div class="n">{len(diff.still_failing)}</div>'
                f'<div class="l">still failing</div></div>'
                f'<div class="card"><div class="n">{len(diff.drifted)}</div>'
                f'<div class="l">trace drift</div></div></div>'
                f'<p class="sub" style="margin-top:14px">Baseline '
                f'<span class="mono">{_esc(diff.baseline.run_id)}</span> '
                f'({diff.baseline.pass_rate:.0%}) &rarr; current '
                f'<span class="mono">{_esc(diff.current.run_id)}</span> '
                f"({diff.current.pass_rate:.0%}).</p>"
            )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title><style>{_CSS}</style></head><body><div class="wrap">
<h1>{_esc(title)}</h1>
<p class="sub">Agent <span class="mono">{_esc(card.agent_id)}</span> &middot;
{card.total} scenarios</p>

<div class="cards">
  <div class="card"><div class="n">{card.pass_rate:.0%}</div><div class="l">pass rate</div></div>
  <div class="card"><div class="n">{card.passed}/{card.total}</div><div class="l">scenarios passed</div></div>
  <div class="card"><div class="n">{total_found}</div><div class="l">findings</div></div>
  <div class="card"><div class="n">{card.weighted_score:.0f}</div><div class="l">weighted score</div></div>
</div>

{_severity_bar(card)}

<div class="note">
<strong>{det_found} of {total_found} findings</strong> were decided by a property
check against recorded world state. {det_modes} of {total_modes} failure modes in
the taxonomy use no model at all &mdash; a report you can re-derive from the trace
offline, with the same answer every time.
</div>

{f'<h2>Regression</h2>{regression}' if regression else ''}

<h2>Failure modes</h2>
<table><thead><tr><th>Mode</th><th>Severity</th><th>Count</th><th>What it means</th></tr></thead>
<tbody>{mode_rows}</tbody></table>

<h2>Failing scenarios</h2>
{truncated}
{''.join(_scenario_block(r) for r in shown) or '<div class="note">Nothing failed.</div>'}

</div></body></html>
"""
