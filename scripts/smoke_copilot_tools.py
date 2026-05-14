"""Day-1 smoke for SimReady Copilot tool resolvers.

Runs analyze_geometry + suggest_fixes directly (no LLM call) against the GrabCAD
fixtures. Verifies the tools wrap the SimReady pipeline cleanly and return the
data the agent will hand back to the model.

Run in the simready conda env:
    $env:PYTHONPATH = "<repo-root>"
    & C:\mm\sr\python.exe scripts/smoke_copilot_tools.py
"""

from __future__ import annotations

import json
from pathlib import Path

from simready.copilot.tools import analyze_geometry, suggest_fixes


FIXTURES = [
    "tests/data/grabcad/bracket_simple.STEP",
    "tests/data/grabcad/housing_moderate.stp",
    "tests/data/grabcad/manifold_complex.STEP",
]


def main() -> int:
    for fixture in FIXTURES:
        path = Path(fixture)
        print(f"=== {fixture} ===")
        if not path.exists():
            print(f"  SKIP — fixture missing")
            continue
        report = analyze_geometry(str(path), timeout_seconds=300)
        print(f"  status         : {report.get('status')}")
        geom = report.get("geometry", {}) or {}
        print(f"  face_count     : {geom.get('face_count')}")
        print(f"  complexity_tier: {geom.get('complexity_tier')}")
        findings = report.get("findings", []) or []
        print(f"  findings       : {len(findings)}")
        for finding in findings[:5]:
            print(f"    - [{finding.get('severity')}] {finding.get('check')}")
        fixes = suggest_fixes(findings, max_results=3)
        for suggestion in fixes.get("suggestions", []):
            line = (
                f"    fix [{suggestion['severity']}] "
                f"{suggestion['check']}: {suggestion['fix'][:80]}"
            )
            print(line)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
