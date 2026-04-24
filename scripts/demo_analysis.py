"""Run SimReady analysis on all test fixtures and print summary."""
from pathlib import Path

from simready.pipeline import analyze_file


fixtures = sorted(Path("tests/data").glob("*.step"))
for fixture in fixtures:
    report = analyze_file(str(fixture))
    score = report.get("score", {}).get("overall", "n/a")
    status = report.get("status", "Unknown")
    findings = len(report.get("findings", []))
    bodies = len(report.get("bodies", []))
    print(f"{fixture.name:30s}  score={score:>6}  status={status:20s}  findings={findings}  bodies={bodies}")
