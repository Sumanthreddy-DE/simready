"""Geometric measurements for the text-to-CAD benchmark checker.

Everything here works on an in-memory ``TopoDS_Shape`` and returns plain
Python values, so the checker never needs a STEP round-trip. Needs OCC bindings (pythonocc or OCP, via simready.occ_compat): import it only inside the build/check subprocess or in tests that skip without OCC.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from simready.occ_compat import (
    Bnd_Box, brepbndlib, BRepAdaptor_Surface, BRepCheck_Analyzer,
    BRepClass3d_SolidClassifier, BRepGProp_Face, brepgprop, breptools,
    GeomAbs_Cylinder, GProp_GProps, ShapeAnalysis_FreeBounds,
    TopAbs_EDGE, TopAbs_OUT, gp_Pnt, gp_Vec,
)
from simready.occ_utils import count_shapes, count_topology, iter_faces

Vec3 = tuple[float, float, float]

# Geometric tolerances (mm / unitless). Far below any benchmark tolerance (±0.1 mm).
_LEN_TOL = 1e-4
_ANG_TOL = 1e-6
_PROBE_MM = 0.5  # how far past a hole's end the through-probe looks


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _perp_basis(d: Vec3) -> tuple[Vec3, Vec3]:
    """Two unit vectors perpendicular to unit vector ``d`` and to each other."""
    helper: Vec3 = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
    e1 = _sub(helper, _scale(d, _dot(helper, d)))
    e1 = _scale(e1, 1.0 / _norm(e1))
    e2 = (d[1] * e1[2] - d[2] * e1[1], d[2] * e1[0] - d[0] * e1[2], d[0] * e1[1] - d[1] * e1[0])
    return e1, e2


# ----------------------------------------------------------------------------
# Scalar properties
# ----------------------------------------------------------------------------


def volume(shape: Any) -> float:
    props = GProp_GProps()
    brepgprop.VolumeProperties(shape, props)
    return props.Mass()


def surface_area(shape: Any) -> float:
    props = GProp_GProps()
    brepgprop.SurfaceProperties(shape, props)
    return props.Mass()


def sorted_extents(shape: Any) -> list[float]:
    """Bounding-box side lengths, ascending, without tolerance inflation.

    AddOptimal excludes the per-side OCC gap so nominal upper bounds pass.
    Existing shape_bounding_box callers intentionally retain that gap.
    """
    box = Bnd_Box()
    brepbndlib.AddOptimal(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return sorted([hi.X() - lo.X(), hi.Y() - lo.Y(), hi.Z() - lo.Z()])


def free_edge_count(shape: Any) -> int:
    """Edges bounding only one face. 0 for a closed (watertight) shell."""
    bounds = ShapeAnalysis_FreeBounds(shape)
    return count_shapes(bounds.GetClosedWires(), TopAbs_EDGE) + count_shapes(
        bounds.GetOpenWires(), TopAbs_EDGE
    )


# ----------------------------------------------------------------------------
# Validity gate
# ----------------------------------------------------------------------------


@dataclass
class GateResult:
    passed: bool
    reason: str  # "" when passed, else a short machine-readable cause
    brep_valid: bool
    free_edges: int
    volume: float
    solids: int


def run_gate(shape: Any, expected_solids: int = 1) -> GateResult:
    """BRep valid, closed, positive volume, expected solid count — in that order."""
    try:
        brep_valid = bool(BRepCheck_Analyzer(shape).IsValid())
    except Exception:  # noqa: BLE001 — OCC raises on degenerate shapes
        brep_valid = False
    free = free_edge_count(shape)
    vol = volume(shape)
    solids = count_topology(shape)["solid_count"]
    if not brep_valid:
        reason = "brep_invalid"
    elif free > 0:
        reason = "open_shell"
    elif vol <= 0:
        reason = "non_positive_volume"
    elif solids != expected_solids:
        reason = f"solid_count {solids} != {expected_solids}"
    else:
        reason = ""
    return GateResult(reason == "", reason, brep_valid, free, vol, solids)


# ----------------------------------------------------------------------------
# Cylindrical features (holes and bosses)
# ----------------------------------------------------------------------------


@dataclass
class CylFeature:
    """One cylindrical feature, merged from all coaxial same-radius faces.

    ``concave`` = material outside the cylinder (hole/bore); convex = boss,
    shaft or outer tube wall. ``t0``/``t1`` are absolute positions along
    ``direction`` measured from ``axis_point``.
    """

    diameter: float
    axis_point: Vec3  # point on the axis closest to the origin
    direction: Vec3  # unit, canonical sign (first non-zero of z, y, x is > 0)
    t0: float
    t1: float
    sweep: float  # total angular coverage, radians (2*pi = full cylinder)
    concave: bool
    through: bool | None = None  # holes only; None for convex features

    @property
    def depth(self) -> float:
        return self.t1 - self.t0

    @property
    def full(self) -> bool:
        return self.sweep >= 2 * math.pi - 1e-3


def _canonical(d: Vec3) -> bool:
    """True if ``d`` already has the canonical sign."""
    for c in (d[2], d[1], d[0]):
        if abs(c) > _ANG_TOL:
            return c > 0
    return True


def _cyl_patch(face: Any) -> CylFeature | None:
    surf = BRepAdaptor_Surface(face, True)
    if surf.GetType() != GeomAbs_Cylinder:
        return None
    cyl = surf.Cylinder()
    ax = cyl.Axis()
    loc: Vec3 = (ax.Location().X(), ax.Location().Y(), ax.Location().Z())
    d: Vec3 = (ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z())
    u0, u1, v0, v1 = breptools.UVBounds(face)
    pnt, nrm = gp_Pnt(), gp_Vec()
    # BRepGProp_Face respects face orientation: the normal points out of material.
    BRepGProp_Face(face).Normal((u0 + u1) / 2, (v0 + v1) / 2, pnt, nrm)
    rel = _sub((pnt.X(), pnt.Y(), pnt.Z()), loc)
    radial = _sub(rel, _scale(d, _dot(rel, d)))
    concave = _dot((nrm.X(), nrm.Y(), nrm.Z()), radial) < 0
    if not _canonical(d):
        d, v0, v1 = _scale(d, -1.0), -v1, -v0
    axis_point = _sub(loc, _scale(d, _dot(loc, d)))
    base = _dot(loc, d)
    return CylFeature(2 * cyl.Radius(), axis_point, d, base + v0, base + v1, u1 - u0, concave)


def _same_axis(a: CylFeature, b: CylFeature) -> bool:
    return (
        a.concave == b.concave
        and abs(a.diameter - b.diameter) < _LEN_TOL
        and abs(_dot(a.direction, b.direction) - 1.0) < _ANG_TOL
        and _norm(_sub(a.axis_point, b.axis_point)) < _LEN_TOL
    )


def _probe_open(shape: Any, feat: CylFeature, t: float) -> bool:
    """True if four points at 0.9 r around the axis at position ``t`` are all outside material."""
    r = 0.45 * feat.diameter
    e1, e2 = _perp_basis(feat.direction)
    centre = _add(feat.axis_point, _scale(feat.direction, t))
    for e in (e1, _scale(e1, -1.0), e2, _scale(e2, -1.0)):
        q = _add(centre, _scale(e, r))
        if BRepClass3d_SolidClassifier(shape, gp_Pnt(*q), _LEN_TOL).State() != TopAbs_OUT:
            return False
    return True


def cylindrical_features(shape: Any) -> list[CylFeature]:
    """All cylindrical features, merged per (axis, diameter, concavity).

    Coaxial same-diameter faces merge when their axial spans touch or overlap
    (OCC may split one hole into several faces). A hole is ``through`` when
    probes ``_PROBE_MM`` past both ends, at 0.9 r, are all outside material —
    so the small hole of a counterbore is through and the counterbore is not.
    """
    merged: list[CylFeature] = []
    for _, face in iter_faces(shape):
        patch = _cyl_patch(face)
        if patch is None:
            continue
        for feat in merged:
            touching = patch.t0 <= feat.t1 + _LEN_TOL and patch.t1 >= feat.t0 - _LEN_TOL
            if _same_axis(feat, patch) and touching:
                same_span = abs(patch.t0 - feat.t0) < _LEN_TOL and abs(patch.t1 - feat.t1) < _LEN_TOL
                feat.sweep = feat.sweep + patch.sweep if same_span else max(feat.sweep, patch.sweep)
                feat.t0, feat.t1 = min(feat.t0, patch.t0), max(feat.t1, patch.t1)
                break
        else:
            merged.append(patch)
    for feat in merged:
        if feat.concave:
            feat.through = _probe_open(shape, feat, feat.t0 - _PROBE_MM) and _probe_open(
                shape, feat, feat.t1 + _PROBE_MM
            )
    return merged


def axis_distance(a: CylFeature, b: CylFeature) -> float:
    """Distance between two parallel axes (hole-pattern checks)."""
    diff = _sub(b.axis_point, a.axis_point)
    return _norm(_sub(diff, _scale(a.direction, _dot(diff, a.direction))))


# ----------------------------------------------------------------------------
# Replay fingerprint
# ----------------------------------------------------------------------------


def fingerprint(shape: Any) -> dict[str, Any]:
    """Rounded geometric summary, equal across rebuilds of the same spec on the
    same OCC version. ``replay`` compares this instead of a STEP byte hash,
    because STEP headers carry a timestamp."""
    topo = count_topology(shape)
    return {
        "volume": round(volume(shape), 2),
        "area": round(surface_area(shape), 2),
        "extents": [round(x, 3) for x in sorted_extents(shape)],
        "faces": topo["face_count"],
        "edges": topo["edge_count"],
        "solids": topo["solid_count"],
    }
