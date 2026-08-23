#!/usr/bin/env python3
"""Render docs/PROGRESS.md into a printable PDF.

    python3 docs/build_progress.py

Markdown is the source of truth (it reads fine on GitHub too); this produces the
PDF for sharing with anyone who would rather not open a repo. Uses headless
Chrome, which is already on this machine, so there is no extra dependency beyond
the `markdown` package.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("needs the markdown package:  pip install markdown")

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "PROGRESS.md"
OUTPUT = HERE / "PROGRESS.pdf"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]

CSS = """
@page { size: A4; margin: 16mm 15mm; }
* { box-sizing: border-box; }
body {
  font: 10.5pt/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, sans-serif;
  color: #16202e; margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 { font-size: 23pt; margin: 0 0 2mm; letter-spacing: -.4pt; }
h2 {
  font-size: 14pt; margin: 9mm 0 3mm; padding-bottom: 2mm;
  border-bottom: 1.5pt solid #d6dee9; letter-spacing: -.2pt;
  page-break-after: avoid;
}
h3 { font-size: 11.5pt; margin: 6mm 0 2mm; page-break-after: avoid; }
p { margin: 0 0 3mm; }
strong { color: #0b1522; }
hr { border: 0; border-top: 1pt solid #e3e9f1; margin: 7mm 0; }
ul, ol { margin: 0 0 3mm; padding-left: 5mm; }
li { margin-bottom: 1.5mm; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 9pt; background: #eef2f7; padding: .4mm 1.2mm; border-radius: 2pt;
  color: #16202e;
}
pre { background: #f5f8fb; border: 1pt solid #dfe6ee; border-radius: 3pt;
      padding: 3mm; overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
table {
  width: 100%; border-collapse: collapse; margin: 0 0 4mm;
  font-size: 9.5pt; page-break-inside: avoid;
}
th, td { text-align: left; padding: 1.8mm 2.5mm; border-bottom: .75pt solid #e3e9f1;
         vertical-align: top; }
th { background: #f2f6fa; font-weight: 600; font-size: 8.5pt;
     text-transform: uppercase; letter-spacing: .3pt; color: #4a5b70; }
tr:last-child td { border-bottom: 0; }
blockquote {
  margin: 0 0 4mm; padding: 3mm 4mm; background: #f5f8fb;
  border-left: 2.5pt solid #3b82f6; border-radius: 0 3pt 3pt 0;
  page-break-inside: avoid;
}
blockquote p:last-child { margin-bottom: 0; }
.meta { color: #6b7c93; font-size: 9pt; margin-bottom: 6mm; }
"""


def find_chrome() -> str:
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit("no Chrome or Chromium found; open the HTML and print to PDF manually")


def build_html() -> str:
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "attr_list"])
    body = md.convert(SOURCE.read_text(encoding="utf-8"))
    stamp = date.today().isoformat()
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>agentcheck progress</title><style>{CSS}</style></head>"
        f"<body>{body}"
        f"<p class='meta'>Generated {stamp} from docs/PROGRESS.md</p>"
        "</body></html>"
    )


def main() -> None:
    if not SOURCE.exists():
        sys.exit(f"missing {SOURCE}")

    html = build_html()
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "progress.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                find_chrome(),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={OUTPUT}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    size = OUTPUT.stat().st_size / 1024
    print(f"wrote {OUTPUT.relative_to(HERE.parent)}  ({size:.0f} KB)")


if __name__ == "__main__":
    main()
