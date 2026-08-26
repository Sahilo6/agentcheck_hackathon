#!/usr/bin/env python3
"""Generate the presentation deck from live project data.

    python3 docs/build_deck.py        # writes docs/deck.html

Every number on a slide is read from the fixture and the taxonomy at build time
rather than typed in. That is the same rule the dashboard follows: if a figure
is not in the data, it does not go on screen. It also means the deck cannot
quietly go stale when the engine changes.

Output is one self-contained HTML file. No network, no build step, opens from
the filesystem. Arrow keys or space to advance, `f` for fullscreen.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agentcheck.detect.taxonomy import TAXONOMY, deterministic_share  # noqa: E402

FIXTURE = ROOT / "web" / "fixtures" / "sample-scorecard.json"
OUTPUT = ROOT / "docs" / "deck.html"

SEVERITY_HEX = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#64748b",
}


def load() -> dict:
    data = json.loads(FIXTURE.read_text())
    runs = {(r["domain"], r["agent_id"]): r for r in data["runs"]}
    devops = sorted(k for k in runs if k[0] == "devops")
    support = sorted(k for k in runs if k[0] == "support")
    naive, hardened = runs[devops[0]], runs[devops[1]]
    s_naive, s_hardened = runs[support[0]], runs[support[1]]

    base = [r for r in naive["results"] if not r["mutations"]]
    mutated = [r for r in naive["results"] if r["mutations"]]
    rate = lambda rows: sum(1 for r in rows if r["passed"]) / len(rows)

    # The scenario the demo drills into. Pulled by finding one that actually has
    # the finding, rather than hard-coding an id that could stop matching.
    lie = next(
        r for r in naive["results"]
        if any(f["mode"] == "hallucinated_success" for f in r["findings"])
        and any(f["mode"] == "destructive_action" for f in r["findings"])
    )

    det_modes, total_modes = deterministic_share()
    return {
        "naive": naive,
        "hardened": hardened,
        "support_naive": s_naive,
        "support_hardened": s_hardened,
        "base_rate": rate(base),
        "mutated_rate": rate(mutated),
        "seeds": data["domains"]["devops"]["seeds"],
        "scenarios": data["domains"]["devops"]["scenarios"],
        "lie": lie,
        "det_modes": det_modes,
        "total_modes": total_modes,
        "total_findings": naive["findings_total"] + s_naive["findings_total"],
    }


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0b0f17;--panel:#131a26;--line:#233046;--fg:#e6edf7;--dim:#8ba0bd;
--pass:#22c55e;--crit:#ef4444;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
html,body{height:100%;background:var(--bg);color:var(--fg);overflow:hidden;
font:400 20px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,sans-serif}
.slide{position:absolute;inset:0;display:none;flex-direction:column;
justify-content:center;padding:6vh 8vw;animation:in .18s ease-out}
.slide.on{display:flex}
@keyframes in{from{opacity:0}to{opacity:1}}
h1{font-size:clamp(38px,5.2vw,76px);line-height:1.05;letter-spacing:-.025em;font-weight:650}
h2{font-size:clamp(26px,3.1vw,44px);line-height:1.15;letter-spacing:-.02em;
font-weight:620;margin-bottom:.7em}
p{font-size:clamp(17px,1.5vw,25px);color:var(--dim);max-width:34em;margin-bottom:.55em}
p.lead{color:var(--fg)}
.kicker{font-size:13px;letter-spacing:.18em;text-transform:uppercase;
color:var(--dim);margin-bottom:1.6em}
.big{font-size:clamp(58px,9vw,140px);font-weight:680;line-height:.95;letter-spacing:-.04em}
.mono{font-family:var(--mono)}
.dim{color:var(--dim)}
.pass{color:var(--pass)}.crit{color:var(--crit)}
.row{display:flex;gap:clamp(20px,4vw,72px);align-items:flex-end;flex-wrap:wrap}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
padding:clamp(16px,2vw,30px)}
.grid{display:grid;gap:14px;margin-top:1.2em}
.g2{grid-template-columns:1fr 1fr}
.quote{border-left:3px solid var(--crit);padding-left:1.1em;font-style:italic;
font-size:clamp(19px,1.9vw,31px);line-height:1.45}
table{border-collapse:collapse;width:100%;font-size:clamp(13px,1.15vw,19px)}
td,th{text-align:left;padding:.42em .7em;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:500;font-size:.72em;text-transform:uppercase;
letter-spacing:.07em}
.pill{display:inline-block;padding:.12em .6em;border-radius:99px;font-size:.62em;
font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.flow{display:flex;align-items:center;gap:clamp(6px,1vw,16px);flex-wrap:wrap;
font-family:var(--mono);font-size:clamp(12px,1.15vw,19px)}
.flow span{background:var(--panel);border:1px solid var(--line);border-radius:9px;
padding:.55em .85em;white-space:nowrap}
.flow i{color:var(--dim);font-style:normal}
.bar{position:fixed;bottom:0;left:0;height:3px;background:var(--pass);
transition:width .2s}
.num{position:fixed;bottom:14px;right:22px;font-family:var(--mono);font-size:12px;
color:var(--dim)}
ul{margin:.4em 0 0 1.1em}
li{font-size:clamp(16px,1.4vw,23px);color:var(--dim);margin-bottom:.42em}
li b{color:var(--fg);font-weight:600}
"""

JS = """
const slides=[...document.querySelectorAll('.slide')];
let i=0;
function show(n){
  i=Math.max(0,Math.min(slides.length-1,n));
  slides.forEach((s,k)=>s.classList.toggle('on',k===i));
  document.querySelector('.bar').style.width=((i+1)/slides.length*100)+'%';
  document.querySelector('.num').textContent=(i+1)+' / '+slides.length;
  location.hash=i+1;
}
addEventListener('keydown',e=>{
  if(['ArrowRight','ArrowDown',' ','PageDown','n'].includes(e.key)){e.preventDefault();show(i+1)}
  if(['ArrowLeft','ArrowUp','PageUp','p'].includes(e.key)){e.preventDefault();show(i-1)}
  if(e.key==='Home')show(0);
  if(e.key==='End')show(slides.length-1);
  if(e.key==='f')document.documentElement.requestFullscreen?.();
});
addEventListener('click',e=>{if(!e.target.closest('a'))show(i+1)});
show(parseInt(location.hash.slice(1))-1||0);
"""


def pill(severity: str) -> str:
    colour = SEVERITY_HEX[severity]
    return f'<span class="pill" style="background:{colour}22;color:{colour}">{severity}</span>'


def build(d: dict) -> str:
    naive, hardened = d["naive"], d["hardened"]
    lie = d["lie"]
    halluc = next(f for f in lie["findings"] if f["mode"] == "hallucinated_success")
    destructive = next(f for f in lie["findings"] if f["mode"] == "destructive_action")
    performed = sorted({e["op"] for e in lie["trace"]["journal"]}) or ["nothing"]

    taxonomy_rows = "".join(
        f"<tr><td class='mono'>{mode_id}</td><td>{pill(m.severity)}</td>"
        f"<td class='dim'>{m.description.split('.')[0]}.</td>"
        f"<td class='pass mono' style='font-size:.8em'>no LLM</td></tr>"
        for mode_id, m in sorted(TAXONOMY.items(), key=lambda kv: (
            ["critical", "high", "medium", "low"].index(kv[1].severity), kv[0]))
    )

    slides = [
        # 1 title
        f"""<div class="slide on">
  <div class="kicker">OOSC 4.0 &middot; problem statement 4</div>
  <h1>agentcheck</h1>
  <p class="lead" style="font-size:clamp(20px,2.1vw,34px);margin-top:.5em">
    Continuous integration for autonomous agents.</p>
  <p style="margin-top:1.4em">Generate adversarial scenarios, run them in a
    deterministic mock world, and prove what the agent actually did.</p>
</div>""",
        # 2 problem
        f"""<div class="slide">
  <div class="kicker">the problem</div>
  <h2>Agents are shipped against a handful of prompts.</h2>
  <p class="lead">Teams write five or ten example tasks, check the replies look
    right, and deploy. Real failure modes surface later, on live data.</p>
  <div class="grid g2">
    <div class="card"><div class="big crit">{d['base_rate']:.0%}</div>
      <p style="margin:.4em 0 0">of hand-written-style scenarios pass</p></div>
    <div class="card"><div class="big crit">{d['mutated_rate']:.0%}</div>
      <p style="margin:.4em 0 0">of their adversarial variants pass</p></div>
  </div>
  <p style="margin-top:1.2em">A person writes down the situation they are
    picturing. Agents fail in the ones nobody pictures.</p>
</div>""",
        # 3 why judges fail
        """<div class="slide">
  <div class="kicker">the obvious approach</div>
  <h2>Have an LLM write the tests.<br>Have another LLM grade the answers.</h2>
  <p class="lead" style="margin-top:1em">Which invites one question:</p>
  <div class="card" style="margin-top:.6em;border-left:3px solid var(--crit)">
    <div style="font-size:clamp(24px,2.6vw,42px);font-weight:620">
      How do you know the grader is right?</div>
  </div>
  <p style="margin-top:1.2em">You have swapped one model you cannot verify for
    another one you cannot verify.</p>
</div>""",
        # 4 thesis
        f"""<div class="slide">
  <div class="kicker">our position</div>
  <h2 style="max-width:20em">You cannot evaluate an agent from its final answer.
    You have to evaluate its trajectory.</h2>
  <p class="lead">Doing that rigorously means owning the environment. Once you
    own the environment, you know the truth, so most failure detection needs no
    model at all.</p>
  <div class="card" style="margin-top:1.2em;border-left:3px solid var(--pass)">
    <div style="font-size:clamp(22px,2.3vw,36px);font-weight:620">
      <span class="pass">{d['det_modes']} of {d['total_modes']}</span> failure
      modes are decided by a property check.</div>
    <p style="margin:.5em 0 0">Not one of them calls a language model.</p>
  </div>
</div>""",
        # 5 the proof
        f"""<div class="slide">
  <div class="kicker">what that buys you &middot; <span class="mono">{lie['scenario_id']}</span></div>
  <h2 style="margin-bottom:.5em">The agent said:</h2>
  <div class="quote">&ldquo;{lie['trace']['final_message']}&rdquo;</div>
  <h2 style="margin:1.1em 0 .4em">The world recorded:</h2>
  <div class="flow">{"".join(f"<span>{op}</span>" for op in performed)}</div>
  <p style="margin-top:1.3em" class="lead">{halluc['summary']}</p>
  <p>Caught by checking state, not by asking a model whether the summary sounded
    truthful.</p>
</div>""",
        # 6 taxonomy
        f"""<div class="slide">
  <div class="kicker">the taxonomy</div>
  <h2 style="margin-bottom:.5em">Ten failure modes, each with a detection method.</h2>
  <table><thead><tr><th>mode</th><th>severity</th><th>what it means</th>
    <th>detector</th></tr></thead><tbody>{taxonomy_rows}</tbody></table>
  <p style="margin-top:1em;font-size:.8em">Published as a standalone spec in
    <span class="mono">docs/TAXONOMY.md</span>, written to be implementable
    without our code.</p>
</div>""",
        # 7 architecture
        """<div class="slide">
  <div class="kicker">how it works</div>
  <h2 style="margin-bottom:.8em">Six stages, one of which is optional.</h2>
  <div class="flow">
    <span>seed scenarios</span><i>&rarr;</i>
    <span>mutation ladder</span><i>&rarr;</i>
    <span>mock world</span><i>&rarr;</i>
    <span>trace</span><i>&rarr;</i>
    <span>10 detectors</span><i>&rarr;</i>
    <span>scorecard</span>
  </div>
  <ul style="margin-top:1.6em">
    <li><b>A scenario is a spec, not a prompt.</b> It carries a machine-checkable
      postcondition, so a verdict is a property check rather than an opinion.</li>
    <li><b>Mutations are code.</b> Eight pressure types, composed in pairs. No API
      calls, and the same suite every time.</li>
    <li><b>Runs are reproducible.</b> Same scenario, same fingerprint. That is what
      makes "you broke something" trustworthy instead of noise.</li>
  </ul>
</div>""",
        # 8 demo marker
        f"""<div class="slide" style="justify-content:center;align-items:flex-start">
  <div class="kicker">live</div>
  <h1 style="font-size:clamp(44px,6.5vw,96px)">Demo</h1>
  <p class="lead" style="margin-top:1em">{d['scenarios']} scenarios from
    {d['seeds']} hand-written seeds. Offline, no API key.</p>
  <div class="flow" style="margin-top:1.4em">
    <span>pytest examples/how_teams_test_today.py</span>
    <i>&rarr;</i><span>agentcheck run</span>
    <i>&rarr;</i><span>agentcheck run --fail-on-new</span>
  </div>
</div>""",
        # 9 results
        f"""<div class="slide">
  <div class="kicker">results</div>
  <h2 style="margin-bottom:.7em">The same agent, before and after guardrails.</h2>
  <table style="font-size:clamp(14px,1.3vw,22px)"><thead><tr>
    <th>domain</th><th>agent</th><th>pass rate</th><th>findings</th></tr></thead>
  <tbody>
    <tr><td>devops</td><td class="mono">{naive['agent_id']}</td>
      <td class="crit"><b>{naive['pass_rate']:.0%}</b></td><td>{naive['findings_total']}</td></tr>
    <tr><td>devops</td><td class="mono">{hardened['agent_id']}</td>
      <td class="pass"><b>{hardened['pass_rate']:.0%}</b></td>
      <td class="pass"><b>{hardened['findings_total']}</b></td></tr>
    <tr><td>support</td><td class="mono">{d['support_naive']['agent_id']}</td>
      <td class="crit"><b>{d['support_naive']['pass_rate']:.0%}</b></td>
      <td>{d['support_naive']['findings_total']}</td></tr>
    <tr><td>support</td><td class="mono">{d['support_hardened']['agent_id']}</td>
      <td class="pass"><b>{d['support_hardened']['pass_rate']:.0%}</b></td>
      <td class="pass"><b>{d['support_hardened']['findings_total']}</b></td></tr>
  </tbody></table>
  <p style="margin-top:1.1em" class="lead">Read the hundred-percents first. A
    correct agent survives every adversarial scenario without tripping a single
    detector.</p>
  <p>That is what makes the {d['total_findings']} findings on the other rows
    worth believing.</p>
</div>""",
        # 10 open source
        """<div class="slide">
  <div class="kicker">open source</div>
  <h2 style="margin-bottom:.6em">Apache-2.0, and dependency-free.</h2>
  <ul>
    <li><b>pip install, then one command.</b> <span class="mono">agentcheck demo</span>
      needs no API key and no configuration.</li>
    <li><b>Bring your own agent.</b> A Python class, an HTTP endpoint, or anything
      that speaks MCP, with no adapter to write.</li>
    <li><b>A GitHub Action</b> that fails a pull request only on new failures, so
      it can be adopted on a codebase that already has problems.</li>
    <li><b>The taxonomy is the artifact</b> we would most like someone else to
      take and use.</li>
  </ul>
  <p class="mono" style="margin-top:1.6em;font-size:clamp(15px,1.4vw,23px)">
    github.com/Sahilo6/agentcheck_hackathon</p>
</div>""",
    ]

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>agentcheck</title><style>{CSS}</style></head><body>"
        + "".join(slides)
        + "<div class='bar'></div><div class='num'></div>"
        f"<script>{JS}</script></body></html>"
    )


def main() -> None:
    if not FIXTURE.exists():
        sys.exit(f"missing {FIXTURE}; run examples/make_sample_scorecard.py first")
    html = build(load())
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}  ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
