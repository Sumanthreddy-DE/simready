"""Single-file HTML report generation for SimReady."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:  # pragma: no cover
    Environment = None
    FileSystemLoader = None
    select_autoescape = None


def render_html_report(report: dict[str, Any], output_path: str) -> str:
    template_dir = Path(__file__).resolve().parent / "templates"
    if Environment is None or FileSystemLoader is None or select_autoescape is None:
        html = _fallback_html(report)
    else:
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template("report.html")
        html = template.render(report=report, report_json=json.dumps(report, indent=2), score=report.get("score", {}), ml=report.get("ml", {}))

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return str(destination)


def _fallback_html(report: dict[str, Any]) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>SimReady Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; background: #111827; color: #f9fafb; }}
    pre {{ background: #1f2937; padding: 1rem; border-radius: 8px; overflow-x: auto; }}
    .badge {{ display: inline-block; padding: 0.4rem 0.8rem; border-radius: 999px; background: #2563eb; }}
  </style>
</head>
<body>
  <h1>SimReady Report</h1>
  <p><span class=\"badge\">{report.get('score', {}).get('overall', 'n/a')}/100</span> {report.get('status', '')}</p>
  <pre>{json.dumps(report, indent=2)}</pre>
</body>
</html>
"""
