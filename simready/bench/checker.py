"""Grade a built shape against a concept's checks. Needs OCC (via geometry).

Order: validity gate first (fail => F5, no checks run), then every check in
list order. The attempt passes iff the gate passes and no check fails;
``not_checked`` never fails. ``partial`` = passed / (passed + failed) is
logged for analysis and as SP3's dense reward.
"""

from __future__ import annotations

import itertools
from typing import Any

from simready.bench import CHECKER_VERSION
from simready.bench import geometry as geo
from simready.bench.concepts import (
    AnyOf,
    BBoxMinDim,
    BBoxSorted,
    Boss,
    Bore,
    Check,
    HoleSet,
    NotChecked,
    VolumeCheck,
    in_range,
)

PASS, FAIL, NOT_CHECKED = "pass", "fail", "not_checked"
F5 = "F5_invalid_solid"
F6 = "F6_dimension_miss"
F7 = "F7_feature_miss"
_EPS = 1e-6


def _holes(features: list[geo.CylFeature], check: HoleSet | Bore) -> list[geo.CylFeature]:
    return [
        f
        for f in features
        if f.concave
        and f.full
        and in_range(f.diameter, check.diameter)
        and (check.through is None or f.through == check.through)
        and (check.depth_min is None or f.depth >= check.depth_min - _EPS)
    ]


def _status(ok: bool) -> str:
    return PASS if ok else FAIL


def _eval(check: Check, shape: Any, features: list[geo.CylFeature]) -> tuple[str, str]:
    if isinstance(check, NotChecked):
        return NOT_CHECKED, check.what
    if isinstance(check, BBoxSorted):
        ext = geo.sorted_extents(shape)
        ok = all(in_range(e, r) for e, r in zip(ext, check.ranges))
        return _status(ok), f"extents {[round(e, 3) for e in ext]} vs {list(check.ranges)}"
    if isinstance(check, BBoxMinDim):
        smallest = geo.sorted_extents(shape)[0]
        return _status(smallest >= check.min - _EPS), f"min extent {smallest:.3f} vs >= {check.min}"
    if isinstance(check, VolumeCheck):
        vol = geo.volume(shape)
        return _status(in_range(vol, check.range)), f"volume {vol:.1f} vs {check.range}"
    if isinstance(check, HoleSet):
        holes = _holes(features, check)
        if not in_range(len(holes), check.count):
            return FAIL, f"{len(holes)} matching holes vs count {check.count}"
        if check.pattern is None:
            return PASS, f"{len(holes)} matching holes"
        dists = sorted(geo.axis_distance(a, b) for a, b in itertools.combinations(holes, 2))
        ranges = sorted(check.pattern, key=lambda r: float("-inf") if r[0] is None else r[0])
        ok = all(in_range(d, r) for d, r in zip(dists, ranges))
        return _status(ok), f"pairwise distances {[round(d, 3) for d in dists]} vs {ranges}"
    if isinstance(check, Bore):
        hits = _holes(features, check)
        found = sorted(round(f.diameter, 3) for f in features if f.concave and f.full)
        return _status(bool(hits)), f"{len(hits)} matching bores; hole diameters {found}"
    if isinstance(check, Boss):
        hits = [
            f
            for f in features
            if not f.concave
            and f.full
            and in_range(f.diameter, check.diameter)
            and (check.height_min is None or f.depth >= check.height_min - _EPS)
        ]
        found = sorted(round(f.diameter, 3) for f in features if not f.concave and f.full)
        return _status(in_range(len(hits), check.count)), f"{len(hits)} matching bosses; convex diameters {found}"
    if isinstance(check, AnyOf):
        subs = [_eval(c, shape, features) for c in check.checks]
        return _status(any(s == PASS for s, _ in subs)), " | ".join(d for _, d in subs)
    raise TypeError(f"unknown check type {type(check).__name__}")


def _class_of(check: Check) -> str:
    return F7 if isinstance(check, HoleSet) else F6


def grade_shape(shape: Any, checks: list[Check], expected_solids: int = 1) -> dict[str, Any]:
    gate = geo.run_gate(shape, expected_solids)
    gate_d = {
        "passed": gate.passed,
        "reason": gate.reason,
        "brep_valid": gate.brep_valid,
        "free_edges": gate.free_edges,
        "volume": round(gate.volume, 3),
        "solids": gate.solids,
    }
    report: dict[str, Any] = {"checker_version": CHECKER_VERSION, "gate": gate_d, "checks": []}
    if not gate.passed:
        report.update(n_pass=0, n_fail=0, n_not_checked=0, partial=0.0, passed=False, failure_class=F5)
        return report
    features = geo.cylindrical_features(shape)
    first_fail: str | None = None
    for check in checks:
        status, detail = _eval(check, shape, features)
        report["checks"].append({"type": check.type, "status": status, "detail": detail})
        if status == FAIL and first_fail is None:
            first_fail = _class_of(check)
    statuses = [c["status"] for c in report["checks"]]
    n_pass, n_fail = statuses.count(PASS), statuses.count(FAIL)
    report.update(
        n_pass=n_pass,
        n_fail=n_fail,
        n_not_checked=statuses.count(NOT_CHECKED),
        partial=n_pass / (n_pass + n_fail) if n_pass + n_fail else 1.0,
        passed=n_fail == 0,
        failure_class=first_fail,
    )
    return report
