"""Checker-scored text-to-CAD benchmark (SP1).

Design: docs/exec-plans/active/2026-09-25-sp1-cad-benchmark-design.md.
OCC-free modules (concepts, runlog, report) must stay importable in plain
Python so ``python -m simready.bench report`` works without pythonocc.
"""

# Bump on any checker change. Drop "-dev" when tagging the official run;
# ``run --official`` refuses a "-dev" version.
CHECKER_VERSION = "1.0.0-dev"
