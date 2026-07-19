"""Regression: the 4 real-CAD parts that killed the 2026-05-28 eval.

Diagnosis (docs/validation/occ_hang_diagnosis.md): the two 58-face NURBS
flanges hung in check_self_intersection (BOPAlgo, GIL-held); the other
two were eval-budget artifacts, not hangs. With the freeform-face guard
plus analyze_file_safe, all four must complete a full analysis within a
90 s subprocess budget.

Local-only: tests/data/real_eval/ is gitignored (CI skips the module).
"""

from __future__ import annotations

from pathlib import Path

import pytest

occ = pytest.importorskip(
    "OCC.Core.BRepPrimAPI",
    reason="pythonocc-core not available (run under the sr env)",
)

REAL_EVAL = Path(__file__).resolve().parents[1] / "tests" / "data" / "real_eval"

pytestmark = pytest.mark.skipif(
    not REAL_EVAL.exists(), reason="gitignored real_eval data absent"
)

# (stem, why it previously died)
FORMER_KILLS = [
    ("43505K359", "BOPAlgo hang on B-spline flange"),
    ("44685K321", "BOPAlgo hang on B-spline flange"),
    ("1483N211", "eval budget artifact (14 s load + cold import)"),
    ("4519N12", "eval budget artifact (578 faces, cold import)"),
]


@pytest.mark.parametrize("stem,why", FORMER_KILLS, ids=[s for s, _ in FORMER_KILLS])
def test_former_kill_part_completes(stem, why):
    from simready.pipeline import analyze_file_safe

    matches = list(REAL_EVAL.glob(f"{stem}*.STEP"))
    if not matches:
        pytest.skip(f"{stem} not present locally")
    report = analyze_file_safe(str(matches[0]), timeout=90)
    # Full completion, not a clean timeout: the guard removed the hang.
    assert report["status"] != "InvalidInput", f"{stem} ({why}): {report['validation']['errors']}"
    assert report["geometry"]["face_count"] > 0


def test_flange_reports_self_intersection_skip():
    from simready.pipeline import analyze_file_safe

    matches = list(REAL_EVAL.glob("43505K359*.STEP"))
    if not matches:
        pytest.skip("43505K359 not present locally")
    report = analyze_file_safe(str(matches[0]), timeout=90)
    checks_fired = {f["check"] for f in report["findings"]}
    assert "SelfIntersectionSkipped" in checks_fired