"""Build ``simready/bench/prompts/concepts_v2.jsonl`` and prove every check with controls.

concepts_v2 is the SP2 held-out set: 15 concepts (c051-c065) written before any
DSL v2 op exists, graded by the unchanged checker (``CHECKER_VERSION`` 1.0.0).
This script is the source of the file. For each concept it:

* builds a nominal model directly in OCCT (independent of the DSL) and asserts it
  passes every check of every phrasing (positive control);
* builds named fakes that must fail at least one explicit-phrasing check
  (negative controls);
* derives every ``volume`` range by rebuilding the model at the tolerance
  extremes (each dimension pushed to whichever bound adds or removes material);
* for in-vocab concepts, builds the DSL ``reference_spec`` and asserts it passes
  the explicit and engineer checks.

Run from the repo root with an OCC backend (pythonocc or the OCP venv):

    python scripts/bench_concepts_v2.py            # check only, print a summary
    python scripts/bench_concepts_v2.py --write    # also (re)write the JSONL file
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simready.bench.checker import grade_shape  # noqa: E402
from simready.bench.concepts import CHECK_LIST, Concept  # noqa: E402
from simready.gen.build import build_shape  # noqa: E402
from simready.gen.spec import PartSpec  # noqa: E402
from simready.occ_compat import (  # noqa: E402
    BACKEND,
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Fuse,
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCylinder,
    gp_Ax2,
    gp_Dir,
    gp_Pnt,
    gp_Vec,
)

if BACKEND == "ocp":
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeSphere
else:
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeSphere

OUT = ROOT / "simready" / "bench" / "prompts" / "concepts_v2.jsonl"
AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


# ---------------------------------------------------------------- OCCT helpers

def box(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def cyl(r, h, at=(0.0, 0.0, 0.0), axis="z"):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*at), gp_Dir(*AXES[axis])), r, h).Shape()


def cone(r1, r2, h, at=(0.0, 0.0, 0.0), axis="z"):
    return BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(*at), gp_Dir(*AXES[axis])), r1, r2, h).Shape()


def sphere(r, at=(0.0, 0.0, 0.0)):
    return BRepPrimAPI_MakeSphere(gp_Pnt(*at), r).Shape()


def prism(points, vec):
    """Extrude a closed planar polygon (list of 3D points) along ``vec``."""
    poly = BRepBuilderAPI_MakePolygon()
    for p in points:
        poly.Add(gp_Pnt(*p))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(*vec)).Shape()


def hex_prism(af, h, cx=0.0, cy=0.0, z0=0.0):
    """Regular hexagon, ``af`` across flats, flats parallel to X, extruded +Z."""
    rc = af / math.sqrt(3.0)
    pts = [(cx + rc * math.cos(math.radians(a)), cy + rc * math.sin(math.radians(a)), z0) for a in range(0, 360, 60)]
    return prism(pts, (0.0, 0.0, h))


def fuse(*shapes):
    out = shapes[0]
    for s in shapes[1:]:
        op = BRepAlgoAPI_Fuse(out, s)
        op.Build()
        out = op.Shape()
    return out


def cut(base, *tools):
    out = base
    for t in tools:
        op = BRepAlgoAPI_Cut(out, t)
        op.Build()
        out = op.Shape()
    return out


def chamfered_shaft(d, length, c, z0=0.0):
    """Shaft along +Z with a c x 45 deg chamfer at both ends (cones fused to a cylinder)."""
    r = d / 2
    return fuse(
        cone(r - c, r, c, (0, 0, z0)),
        cyl(r, length - 2 * c, (0, 0, z0 + c)),
        cone(r, r - c, c, (0, 0, z0 + length - c)),
    )


# ---------------------------------------------------------------- check helpers

def rng(nom, tol=0.1):
    return [round(nom - tol, 3), round(nom + tol, 3)]


def bbox(*ranges):
    return {"type": "bbox_sorted", "ranges": [list(r) for r in ranges]}


def bore(d, through=None, depth_min=None):
    c = {"type": "bore", "diameter": list(d)}
    if depth_min is not None:
        c["depth_min"] = depth_min
    if through is not None:
        c["through"] = through
    return c


def boss(d, height_min=None, count=None):
    c = {"type": "boss", "diameter": list(d)}
    if height_min is not None:
        c["height_min"] = height_min
    if count is not None:
        c["count"] = list(count)
    return c


def holes(d, count, through=None, depth_min=None, pattern=None):
    c = {"type": "hole_set", "diameter": list(d), "count": list(count)}
    if through is not None:
        c["through"] = through
    if depth_min is not None:
        c["depth_min"] = depth_min
    if pattern is not None:
        c["pattern"] = [list(p) for p in sorted(pattern)]
    return c


def volume(lo, hi):
    return {"type": "volume", "range": [lo, hi]}


def nc(what):
    return {"type": "not_checked", "what": what}


def pattern_of(points, tol=0.1):
    """Sorted pairwise distances of 2D/3D hole positions, each as a +-tol range."""
    ds = sorted(math.dist(a, b) for i, a in enumerate(points) for b in points[i + 1:])
    return [rng(round(d, 3), tol) for d in ds]


Params = dict[str, tuple[float, float, float, int]]  # name -> (lo, nominal, hi, sign)


def tol(nom, sign, t=0.1):
    return (nom - t, nom, nom + t, sign)


def fixed(nom):
    return (nom, nom, nom, 0)


def nominal(params: Params) -> dict[str, float]:
    return {k: v[1] for k, v in params.items()}


def volume_range(build: Callable[[dict], Any], params: Params) -> tuple[float, float]:
    """Volume at the material-min and material-max corners of the tolerance box."""
    from simready.bench import geometry as geo

    lo = {k: (v[0] if v[3] > 0 else v[2] if v[3] < 0 else v[1]) for k, v in params.items()}
    hi = {k: (v[2] if v[3] > 0 else v[0] if v[3] < 0 else v[1]) for k, v in params.items()}
    vmin, vmax = geo.volume(build(lo)), geo.volume(build(hi))
    assert vmin < vmax, (vmin, vmax)
    return math.floor(vmin), math.ceil(vmax)


# ---------------------------------------------------------------- concepts
# Each entry: concept fields + "build" (nominal OCCT model per phrasing family)
# + "fakes" (name -> shape that must fail explicit). Volume ranges are filled
# in by volume_range() so they always match the stated tolerances.

CONCEPTS: list[dict[str, Any]] = []


def concept(**kw):
    CONCEPTS.append(kw)


# c051 -------------------------------------------------------------------------
def _c051(p):
    head = cyl(p["dk"] / 2, p["k"], (0, 0, p["L"]))
    shank = cyl(p["d"] / 2, p["L"] + 0.5)
    socket = hex_prism(p["s"], p["t"] + 1, 0, 0, p["L"] + p["k"] - p["t"])
    return cut(fuse(shank, head), socket)


_c051_x = {"dk": tol(10, 1), "k": tol(6, 1), "d": tol(6, 1), "L": tol(20, 1), "s": tol(5, -1), "t": tol(3, -1)}
# ISO 4762 M6: dk max 10.00 (plain head), k 5.70-6.00, ds 5.82-6.00, s 5.020-5.140, t min 3.0, l 20 js16 19.58-20.42.
_c051_e = {"dk": (9.78, 10.0, 10.0, 1), "k": (5.7, 6.0, 6.0, 1), "d": (5.82, 6.0, 6.0, 1),
           "L": (19.58, 20.0, 20.42, 1), "s": (5.02, 5.02, 5.14, -1), "t": (3.0, 3.0, 3.0, -1)}
concept(
    concept_id="c051", name="M6 socket head cap screw blank (thread not modelled)", in_vocab=False,
    prompts={
        "explicit": "A socket head cap screw blank without thread: a 10 mm diameter, 6 mm tall cylindrical head on a 6 mm diameter shank 20 mm long (26 mm overall), with a hexagonal socket 5 mm across flats and 3 mm deep in the top of the head.",
        "engineer": "ISO 4762 M6 x 20 socket head cap screw with the thread left off (plain 6 mm shank), including its hexagon socket.",
        "intent": "A plain blank of an M6 cap screw with an Allen-key socket in the head.",
    },
    checks={
        "explicit": [bbox(rng(10), rng(10), rng(26)), boss(rng(10), 5.9), boss(rng(6), 19.9), ("volume", _c051, _c051_x),
                     nc("socket shape (hexagon vs round)")],
        "engineer": [bbox([9.78, 10.0], [9.78, 10.0], [25.28, 26.42]), boss([9.78, 10.0], 5.7), boss([5.82, 6.0], 19.58),
                     ("volume_max", _c051, _c051_e), nc("socket shape (hexagon vs round)")],
        "intent": [boss([5.5, 6.5]), boss([7.0, 14.0]), nc("length and socket")],
    },
    sources=["ISO 4762 M6: dk max 10.00 (plain head), k 5.70-6.00, ds 5.82-6.00, s 5 (5.020-5.140), t min 3.0; l = 20 js16 (19.58-20.42)",
             "Engineer volume has only an upper bound (socket depth t has no maximum); a socket-less blank at nominal size exceeds it",
             "Out of vocab (DSL v1): hexagonal socket"],
    build=lambda: _c051(nominal(_c051_x)),
    fakes={"no socket": lambda: fuse(cyl(3, 20.5), cyl(5, 6, (0, 0, 20)))},
)


# c052 -------------------------------------------------------------------------
def _c052(p):
    return cut(fuse(cyl(p["D3"] / 2, p["b"]), cyl(p["D"] / 2, p["L"])), cyl(p["d"] / 2, p["L"] + 2, (0, 0, -1)))


_c052_x = {"D3": tol(24, 1), "b": tol(3, 1), "D": tol(18, 1), "L": tol(20, 1), "d": tol(12, -1)}
concept(
    concept_id="c052", name="Flanged plain bearing bush, 12 x 18 x 20", in_vocab=True,
    prompts={
        "explicit": "A flanged bush: 18 mm outside diameter, a 12 mm bore straight through, 20 mm long overall, with a 24 mm diameter, 3 mm thick flange at one end (the flange is part of the 20 mm).",
        "engineer": "Flanged sleeve bush for a 12 mm shaft: 18 mm OD body, 24 x 3 mm collar, 20 mm overall length, bore 12 mm with running clearance on the shaft.",
        "intent": "A flanged bush for a 12 mm shaft.",
    },
    checks={
        "explicit": [bbox(rng(20), rng(24), rng(24)), bore(rng(12), through=True), boss(rng(18), 16.9), boss(rng(24), 2.9),
                     ("volume", _c052, _c052_x)],
        "engineer": [bbox(rng(20), rng(24), rng(24)), bore([12.0, 12.1], through=True), boss(rng(18), 16.9), boss(rng(24), 2.9)],
        "intent": [bore([12.0, 13.0], through=True), boss([13.0, 60.0], count=(2, None)), nc("body and flange sizes")],
    },
    sources=["No single standard: stated dimensions +-0.1; engineer bore 12.0-12.1 = clearance on a 12 mm shaft, never below nominal"],
    reference_spec={"steps": [
        {"op": "cyl", "r": 12, "h": 3, "at": [0, 0, 0]}, {"op": "cyl", "r": 9, "h": 20, "at": [0, 0, 0]},
        {"op": "fuse", "a": 0, "b": 1}, {"op": "cyl", "r": 6.025, "h": 20, "at": [0, 0, 0]}, {"op": "cut", "a": 2, "b": 3}]},
    build=lambda: _c052({**nominal(_c052_x), "d": 12.05}),
    fakes={"no flange": lambda: cut(cyl(9, 20), cyl(6, 22, (0, 0, -1)))},
)


# c053 -------------------------------------------------------------------------
concept(
    concept_id="c053", name="DIN 562 M5 thin square nut (thread not modelled)", in_vocab=True,
    prompts={
        "explicit": "A square nut 8 x 8 mm and 2.7 mm thick with a 4.2 mm hole through the middle (thread not modelled).",
        "engineer": "DIN 562 M5 thin square nut, with the thread modelled as the plain tap-drill hole.",
        "intent": "A square nut for an M5 screw.",
    },
    checks={
        "explicit": [bbox(rng(2.7), rng(8), rng(8)), bore(rng(4.2), through=True)],
        "engineer": [bbox([2.45, 2.7], [7.78, 8.0], [7.78, 8.0]), bore([4.134, 4.334], through=True)],
        "intent": [bore([4.0, 5.5], through=True), nc("outer size and thickness")],
    },
    sources=["DIN 562 M5: s = 8, m = 2.7; tolerance zones assumed s h13 (7.78-8.00) and m h14 (2.45-2.70) - proofread against the standard",
             "ISO 965-1 M5x0.8 6H minor diameter D1: 5 - 1.0825 x 0.8 = 4.134, TD1 grade 6 for P 0.8 = 0.200 -> 4.134-4.334"],
    reference_spec={"steps": [
        {"op": "box", "dx": 7.95, "dy": 7.95, "dz": 2.65, "at": [0, 0, 0]},
        {"op": "cyl", "r": 2.1, "h": 2.65, "at": [3.975, 3.975, 0]}, {"op": "cut", "a": 0, "b": 1}]},
    build=lambda: cut(box(0, 0, 0, 7.95, 7.95, 2.65), cyl(2.1, 4, (3.975, 3.975, -1))),
    fakes={"hex nut": lambda: cut(hex_prism(8, 2.7), cyl(2.1, 4, (0, 0, -1)))},
)


# c054 -------------------------------------------------------------------------
def _c054(p):
    pin = cyl(p["d"] / 2, p["L"] + 0.5)
    head = cyl(p["dk"] / 2, p["k"], (0, 0, p["L"]))
    hole = cyl(p["d1"] / 2, 20, (-10, 0, 3.5), "x")
    return cut(fuse(pin, head), hole)


_c054_x = {"d": tol(8, 1), "L": tol(30, 1), "dk": tol(14, 1), "k": tol(3, 1), "d1": tol(2, -1)}
concept(
    concept_id="c054", name="Headed clevis pin with split-pin hole", in_vocab=False,
    prompts={
        "explicit": "A headed pin: an 8 mm diameter pin 30 mm long under a 14 mm diameter, 3 mm thick head (33 mm overall), with a 2 mm hole drilled straight through the pin at right angles to its axis, 3.5 mm from the free end.",
        "engineer": "Clevis pin with head, ISO 2341 form B, 8 x 30, with the split-pin hole near the free end.",
        "intent": "A headed pin with a cross hole for a split pin.",
    },
    checks={
        "explicit": [bbox(rng(14), rng(14), rng(33)), boss(rng(14), 2.9), boss(rng(8), 29.9), holes(rng(2), (1, 1), through=True),
                     ("volume", _c054, _c054_x)],
        "engineer": [bbox([13.57, 14.0], [13.57, 14.0], [32.375, 33.625]), boss([13.57, 14.0], 2.875), boss([7.91, 8.0], 29.5),
                     holes([2.0, 2.14], (1, 1), through=True), nc("split-pin hole position")],
        "intent": [boss([3.0, 40.0], count=(2, None)), holes([0.8, 5.0], (1, 1), through=True), nc("sizes")],
    },
    sources=["ISO 2341 form B, d = 8: dk 14 h14 (13.57-14.00), k 3 js14 (2.875-3.125), d h11 (7.91-8.00), split-pin hole d1 2 H13 (2.00-2.14), l 30 js15 (29.5-30.5) - proofread against the standard",
             "Explicit volume over +-0.1 on every dimension; a pin without the cross hole fails it only through hole_set",
             "Out of vocab (DSL v1): cross hole at right angles to the Z axis"],
    build=lambda: _c054(nominal(_c054_x)),
    fakes={"no cross hole": lambda: fuse(cyl(4, 30.5), cyl(7, 3, (0, 0, 30)))},
)


# c055 -------------------------------------------------------------------------
def _c055(p):
    t, w, H, Lb, g, gt, dh = p["t"], p["w"], p["H"], p["Lb"], p["g"], p["gt"], p["dh"]
    base = box(0, 0, 0, Lb, w, t)
    upright = box(0, 0, 0, t, w, H)
    y0 = w / 2 - gt / 2
    gusset = prism([(t, y0, t), (t + g, y0, t), (t, y0, t + g)], (0, gt, 0))
    body = fuse(base, upright, gusset)
    c1 = cyl(dh / 2, t + 2, (35, w / 2 - 12.5, -1))
    c2 = cyl(dh / 2, t + 2, (35, w / 2 + 12.5, -1))
    return cut(body, c1, c2)


_c055_x = {"t": tol(5, 1), "w": tol(40, 1), "H": tol(60, 1), "Lb": tol(60, 1), "g": tol(30, 1), "gt": tol(5, 1), "dh": tol(6.6, -1)}
_c055_e = {**_c055_x, "dh": (6.4, 6.6, 7.0, -1)}
concept(
    concept_id="c055", name="Gusseted angle bracket", in_vocab=False,
    prompts={
        "explicit": "An angle bracket 40 mm wide: a base leg 60 x 40 x 5 mm and an upright leg 5 mm thick along one 40 mm edge, 60 mm overall height measured from the bottom face. A triangular gusset 5 mm thick, centred across the width, fills the inside corner, running 30 mm along the top of the base and 30 mm up the inner face of the upright. Two 6.6 mm through holes in the base leg, 25 mm apart across the width and centred on it, 35 mm from the upright's outer face.",
        "engineer": "Angle bracket from 5 mm plate, 40 mm wide, both legs 60 mm overall, with a 30 x 30 mm triangular stiffening gusset (5 mm thick) at mid-width in the inside corner and two M6 clearance holes in the base leg on 25 mm centres.",
        "intent": "A sturdy L-shaped bracket with a stiffening rib in the corner and two bolt holes in the base.",
    },
    checks={
        "explicit": [bbox(rng(40), rng(60), rng(60)), holes(rng(6.6), (2, 2), through=True, pattern=[rng(25)]),
                     ("volume", _c055, _c055_x)],
        "engineer": [bbox(rng(40), rng(60), rng(60)), holes([6.4, 7.0], (2, 2), through=True, pattern=[rng(25)]),
                     ("volume", _c055, _c055_e)],
        "intent": [holes([3.0, 15.0], (2, 2), through=True), nc("rib, leg sizes and thickness")],
    },
    sources=["ISO 273 M6 clearance: fine 6.4, medium 6.6, coarse 7.0",
             "Volume over +-0.1 on every dimension separates the gusset from no gusset and from a 30 x 30 square block",
             "Out of vocab (DSL v1): triangular gusset (no wedge or polygon prism)"],
    build=lambda: _c055(nominal(_c055_x)),
    fakes={
        "no gusset": lambda: cut(fuse(box(0, 0, 0, 60, 40, 5), box(0, 0, 0, 5, 40, 60)),
                                 cyl(3.3, 7, (35, 7.5, -1)), cyl(3.3, 7, (35, 32.5, -1))),
        "square block gusset": lambda: cut(fuse(box(0, 0, 0, 60, 40, 5), box(0, 0, 0, 5, 40, 60), box(5, 17.5, 5, 30, 5, 30)),
                                           cyl(3.3, 7, (35, 7.5, -1)), cyl(3.3, 7, (35, 32.5, -1))),
    },
)


# c056 -------------------------------------------------------------------------
_c056_ring = [(50 + 30 * math.cos(math.radians(a)), 50 + 30 * math.sin(math.radians(a))) for a in range(0, 360, 60)]
_c056_corner = [(10, 10), (90, 10), (10, 90), (90, 90)]


def _c056(ring_d=6.6, corner_d=9.0, ring=True):
    plate = box(0, 0, 0, 100, 100, 8)
    tools = [cyl(20, 10, (50, 50, -1))]
    tools += [cyl(corner_d / 2, 10, (x, y, -1)) for x, y in _c056_corner]
    if ring:
        tools += [cyl(ring_d / 2, 10, (x, y, -1)) for x, y in _c056_ring]
    return cut(plate, *tools)


concept(
    concept_id="c056", name="Square flange plate, 6-hole PCD and 4 corner holes", in_vocab=False,
    prompts={
        "explicit": "A 100 x 100 x 8 mm square plate with a 40 mm through hole in the centre, six 6.6 mm through holes equally spaced on a 60 mm diameter circle around it, and four 9 mm through holes on an 80 mm square pattern centred on the plate.",
        "engineer": "Square adapter flange, 100 x 100 x 8 mm, 40 mm centre bore, six M6 clearance holes equally spaced on a 60 mm PCD and four M8 clearance holes on an 80 mm square.",
        "intent": "A square plate with a big hole in the middle, a ring of six small bolt holes around it and a bolt hole in each corner.",
    },
    checks={
        "explicit": [bbox(rng(8), rng(100), rng(100)), bore(rng(40), through=True),
                     holes(rng(6.6), (6, 6), through=True, pattern=pattern_of(_c056_ring)),
                     holes(rng(9), (4, 4), through=True, pattern=pattern_of(_c056_corner))],
        "engineer": [bbox(rng(8), rng(100), rng(100)), bore(rng(40), through=True),
                     holes([6.4, 7.0], (6, 6), through=True, pattern=pattern_of(_c056_ring)),
                     holes([8.4, 10.0], (4, 4), through=True, pattern=pattern_of(_c056_corner))],
        "intent": [bore([20.5, 95.0], through=True), holes([1.0, 20.0], (10, 10), through=True), nc("plate size and hole positions")],
    },
    sources=["ISO 273 clearance: M6 6.4/6.6/7.0, M8 8.4/9.0/10.0 (fine/medium/coarse)",
             "Out of vocab (DSL v1): plate + 11 holes needs 23 steps (22 with the cutters fused first), over the 16-step limit"],
    build=lambda: _c056(),
    fakes={"ring missing": lambda: _c056(ring=False)},
)


# c057 -------------------------------------------------------------------------
def _c057(p):
    t, w, f, H = p["t"], p["w"], p["f"], p["H"]
    body = fuse(box(0, 0, 0, f, w, t), box(f - t, 0, 0, t, w, H), box(f - t, 0, H - t, f, w, t))
    return cut(body, cyl(p["dh"] / 2, t + 2, (13, w / 2, -1)), cyl(p["dh"] / 2, t + 2, (f - t + f - 13, w / 2, H - t - 1)))


_c057_x = {"t": tol(4, 1), "w": tol(40, 1), "f": fixed(30), "H": tol(40, 1), "dh": tol(5.5, -1)}
concept(
    concept_id="c057", name="Z-bracket with one hole per flange", in_vocab=True,
    prompts={
        "explicit": "A Z-shaped bracket from 4 mm plate, 40 mm wide throughout: a bottom flange 30 mm long, a vertical web rising to 40 mm overall height (measured from the bottom face), and a top flange 30 mm long pointing the opposite way, so the part is 56 mm long overall. One 5.5 mm through hole in each flange, 13 mm from the flange's free end and centred across the width.",
        "engineer": "Z-bracket in 4 mm plate, 40 mm wide, 30 mm flanges, 40 mm overall height and 56 mm overall length, with one M5 medium clearance hole (ISO 273) in each flange, 13 mm from its free end.",
        "intent": "A Z-shaped bracket with a bolt hole in each flange.",
    },
    checks={
        "explicit": [bbox(rng(40), rng(40), rng(56)), holes(rng(5.5), (2, 2), through=True, pattern=[rng(30)]),
                     ("volume", _c057, _c057_x)],
        "engineer": [bbox(rng(40), rng(40), rng(56)), holes(rng(5.5), (2, 2), through=True, pattern=[rng(30)])],
        "intent": [holes([2.0, 15.0], (2, 2), through=True), nc("flange and web sizes")],
    },
    sources=["ISO 273 M5 medium clearance 5.5",
             "Flange length held at 30 in the volume corners (overall length 56 = 2 x 30 - 4 is checked by bbox)"],
    reference_spec={"steps": [
        {"op": "box", "dx": 30, "dy": 40, "dz": 4, "at": [0, 0, 0]}, {"op": "box", "dx": 4, "dy": 40, "dz": 40, "at": [26, 0, 0]},
        {"op": "fuse", "a": 0, "b": 1}, {"op": "box", "dx": 30, "dy": 40, "dz": 4, "at": [26, 0, 36]},
        {"op": "fuse", "a": 2, "b": 3}, {"op": "cyl", "r": 2.75, "h": 4, "at": [13, 20, 0]}, {"op": "cut", "a": 4, "b": 5},
        {"op": "cyl", "r": 2.75, "h": 4, "at": [43, 20, 36]}, {"op": "cut", "a": 6, "b": 7}]},
    build=lambda: _c057(nominal(_c057_x)),
    fakes={"stacked web (45 mm tall)": lambda: cut(
        fuse(box(0, 0, 0, 30, 40, 4), box(26, 0, 4, 4, 40, 40), box(26, 0, 40, 30, 40, 4)),
        cyl(2.75, 6, (13, 20, -1)), cyl(2.75, 6, (43, 20, 39)))},
)


# c058 -------------------------------------------------------------------------
_c058_holes = [(12.5, 14.5), (87.5, 14.5), (12.5, 45.5), (87.5, 45.5)]


def _c058(p):
    L, W, t, wl, ww = p["L"], p["W"], p["t"], p["wl"], p["ww"]
    plate = box(0, 0, 0, L, W, t)
    window = box(50 - wl / 2, 30 - ww / 2, -1, wl, ww, t + 2)
    return cut(plate, window, *[cyl(p["dh"] / 2, t + 2, (x, y, -1)) for x, y in _c058_holes])


_c058_x = {"L": tol(100, 1), "W": tol(60, 1), "t": tol(3, 1), "wl": tol(72, -1), "ww": tol(25, -1), "dh": tol(3.4, -1)}
_c058_e = {**_c058_x, "dh": (3.2, 3.4, 3.6, -1)}
concept(
    concept_id="c058", name="Front panel for a 16x2 LCD module", in_vocab=True,
    prompts={
        "explicit": "A 100 x 60 x 3 mm front panel with a 72 x 25 mm rectangular window cut through it, centred on the panel, and four 3.4 mm through holes on a 75 x 31 mm rectangle centred on the panel.",
        "engineer": "Front panel, 100 x 60 x 3 mm, for a 16x2 character LCD module (80 x 36 mm board, M3 mounting holes on 75 x 31 mm centres): a 72 x 25 mm viewing window and M3 clearance holes, everything centred.",
        "intent": "A front panel for a 16x2 LCD: a window for the display and four screw holes to mount it.",
    },
    checks={
        "explicit": [bbox(rng(3), rng(60), rng(100)), holes(rng(3.4), (4, 4), through=True, pattern=pattern_of(_c058_holes)),
                     ("volume", _c058, _c058_x)],
        "engineer": [bbox(rng(3), rng(60), rng(100)), holes([3.2, 3.6], (4, 4), through=True, pattern=pattern_of(_c058_holes)),
                     ("volume", _c058, _c058_e)],
        "intent": [holes([2.5, 4.0], (4, 4), through=True, pattern=pattern_of(_c058_holes, 0.3)), nc("window and panel size")],
    },
    sources=["Common 1602 LCD module: 80 x 36 mm board, mounting holes on 75 x 31 mm centres (vendor drawings) - proofread",
             "ISO 273 M3 clearance: fine 3.2, medium 3.4, coarse 3.6",
             "Window graded only through volume (a missing window fails; a slightly different window size can pass)"],
    reference_spec={"steps": [
        {"op": "box", "dx": 100, "dy": 60, "dz": 3, "at": [0, 0, 0]}, {"op": "box", "dx": 72, "dy": 25, "dz": 3, "at": [14, 17.5, 0]},
        {"op": "cut", "a": 0, "b": 1},
        {"op": "cyl", "r": 1.7, "h": 3, "at": [12.5, 14.5, 0]}, {"op": "cut", "a": 2, "b": 3},
        {"op": "cyl", "r": 1.7, "h": 3, "at": [87.5, 14.5, 0]}, {"op": "cut", "a": 4, "b": 5},
        {"op": "cyl", "r": 1.7, "h": 3, "at": [12.5, 45.5, 0]}, {"op": "cut", "a": 6, "b": 7},
        {"op": "cyl", "r": 1.7, "h": 3, "at": [87.5, 45.5, 0]}, {"op": "cut", "a": 8, "b": 9}]},
    build=lambda: _c058(nominal(_c058_x)),
    fakes={"no window": lambda: cut(box(0, 0, 0, 100, 60, 3), *[cyl(1.7, 5, (x, y, -1)) for x, y in _c058_holes])},
)


# c059 -------------------------------------------------------------------------
def _c059(d=10.0, d2=9.6, m=1.1, groove=True):
    shaft = chamfered_shaft(d, 40, 0.5)
    if not groove:
        return shaft
    ring = cut(cyl(d, m, (0, 0, 5)), cyl(d2 / 2, m + 2, (0, 0, 4)))
    return cut(shaft, ring)


concept(
    concept_id="c059", name="Shaft with retaining-ring groove and chamfered ends", in_vocab=False,
    prompts={
        "explicit": "A 10 mm diameter shaft, 40 mm long, with a 0.5 mm x 45 degree chamfer on both ends and a retaining-ring groove 9.6 mm in diameter and 1.1 mm wide whose near edge is 5 mm from one end.",
        "engineer": "A 10 h9 shaft, 40 mm long, 0.5 x 45 degree chamfers on both ends, with a DIN 471 retaining-ring groove for a 10 mm shaft whose near flank is 5 mm from one end.",
        "intent": "A 10 mm shaft with a groove for an external circlip.",
    },
    checks={
        "explicit": [bbox(rng(10), rng(10), rng(40)), boss(rng(10), 33.3), boss(rng(9.6), 1.0), nc("end chamfers (too small for a volume check)")],
        "engineer": [bbox([9.964, 10.0], [9.964, 10.0], rng(40)), boss([9.964, 10.0], 33.3), boss([9.542, 9.6], 1.09),
                     nc("end chamfers (too small for a volume check)")],
        "intent": [boss([9.8, 10.2]), boss([8.5, 9.79], 0.5), nc("groove position and shaft length")],
    },
    sources=["DIN 471 for d1 = 10: groove d2 9.6 h10 (9.542-9.600), m 1.1 H13 (1.10-1.24)",
             "ISO 286-2 h9 for 6-10 mm: -0.036/0",
             "Long journal face: 40 - 6.1 - 0.5 chamfer = 33.4 mm",
             "Out of vocab (DSL v1): end chamfers"],
    build=lambda: _c059(),
    fakes={"no groove": lambda: _c059(groove=False)},
)


# c060 -------------------------------------------------------------------------
def _c060(p):
    D, L, d, dc = p["D"], p["L"], p["d"], p["dc"]
    h = (dc - d) / 2
    tube = cut(cyl(D / 2, L), cyl(d / 2, L + 2, (0, 0, -1)))
    sink = cone(d / 2, dc / 2 + 1, h + 1, (0, 0, L - h))  # 90 deg: radius grows 1 per 1 of height
    return cut(tube, sink)


_c060_x = {"D": tol(20, 1), "L": tol(15, 1), "d": tol(8.5, -1), "dc": tol(16, -1)}
_c060_e = {**_c060_x, "d": tol(9.0, -1)}
concept(
    concept_id="c060", name="Spacer with countersunk bore", in_vocab=False,
    prompts={
        "explicit": "A round spacer 20 mm outside diameter and 15 mm long with an 8.5 mm hole straight through its axis, countersunk at one end at 90 degrees to 16 mm diameter.",
        "engineer": "Spacer for an M8 countersunk screw: 20 mm OD x 15 mm long, M8 medium clearance hole (ISO 273) through, with a 90 degree countersink to 16 mm diameter at one end.",
        "intent": "A round spacer for an M8 countersunk screw, so the screw head sits flush.",
    },
    checks={
        "explicit": [bbox(rng(15), rng(20), rng(20)), boss(rng(20), 14.9), bore(rng(8.5), through=True, depth_min=11.0),
                     ("volume", _c060, _c060_x)],
        "engineer": [bbox(rng(15), rng(20), rng(20)), boss(rng(20), 14.9), bore(rng(9.0), through=True, depth_min=11.3),
                     ("volume", _c060, _c060_e)],
        "intent": [bore([8.2, 10.0], through=True), boss([10.5, 60.0]), nc("countersink and spacer size")],
    },
    sources=["ISO 273 M8 medium clearance 9.0",
             "Straight bore length = 15 - (16 - d) / 2: 11.25 for d = 8.5, 11.5 for d = 9.0",
             "Volume over +-0.1 on every dimension separates a countersunk bore from a plain one",
             "Out of vocab (DSL v1): conical countersink"],
    build=lambda: _c060(nominal(_c060_x)),
    build_engineer=lambda: _c060(nominal(_c060_e)),
    fakes={"no countersink": lambda: cut(cyl(10, 15), cyl(4.25, 17, (0, 0, -1)))},
)


# c061 -------------------------------------------------------------------------
def _c061(p):
    D, Hc, d, depth = p["D"], p["Hc"], p["d"], p["depth"]
    body = fuse(cyl(D / 2, Hc), sphere(D / 2, (0, 0, Hc)))
    body = cut(body, box(-D, -D, -2 * D, 2 * D, 2 * D, 2 * D))  # trim the lower half of the sphere
    return cut(body, cyl(d / 2, depth + 1, (0, 0, -1)))


_c061_x = {"D": tol(20, 1), "Hc": tol(12, 1), "d": tol(8.5, -1), "depth": tol(10, -1)}
_c061_e = {**_c061_x, "d": (8.376, 8.5, 8.676, -1)}
concept(
    concept_id="c061", name="Dome-top cap with blind tapped hole", in_vocab=False,
    prompts={
        "explicit": "A 20 mm diameter cylinder 12 mm tall with a 10 mm radius hemisphere on top (22 mm overall height), and an 8.5 mm blind hole 10 mm deep drilled up into it from the flat bottom, on the axis.",
        "engineer": "Dome-top cap blank for an M10 stud: 20 mm diameter, full-radius dome, 22 mm overall height, with a blind M10 tap-drill hole 10 mm deep from the flat end (thread not modelled).",
        "intent": "A round cap with a domed top and a threaded hole in the bottom for an M10 bolt.",
    },
    checks={
        "explicit": [bbox(rng(20), rng(20), rng(22)), boss(rng(20), 11.9), bore(rng(8.5), through=False, depth_min=9.9),
                     ("volume", _c061, _c061_x)],
        "engineer": [bbox(rng(20), rng(20), rng(22)), boss(rng(20), 11.9), bore([8.376, 8.676], through=False, depth_min=9.9),
                     ("volume", _c061, _c061_e)],
        "intent": [bore([8.3, 10.5], through=False), boss([12.0, 60.0]), nc("dome shape and cap size")],
    },
    sources=["ISO 965-1 M10x1.5 6H minor diameter D1: 10 - 1.0825 x 1.5 = 8.376, TD1 grade 6 for P 1.5 = 0.300 -> 8.376-8.676",
             "Volume over +-0.1 separates the dome from a flat-topped 22 mm cylinder",
             "Out of vocab (DSL v1): hemisphere"],
    build=lambda: _c061(nominal(_c061_x)),
    fakes={"flat top": lambda: cut(cyl(10, 22), cyl(4.25, 11, (0, 0, -1)))},
)


# c062 -------------------------------------------------------------------------
def _c062(two=True):
    tube = cut(cyl(12.5, 80), cyl(7.5, 82, (0, 0, -1)))
    tools = [cyl(2.5, 30, (-15, 0, 40), "x")]
    if two:
        tools.append(cyl(2.5, 30, (0, -15, 40), "y"))
    return cut(tube, *tools)


concept(
    concept_id="c062", name="Hollow shaft with two cross holes", in_vocab=False,
    prompts={
        "explicit": "A tube 25 mm outside diameter, 15 mm inside diameter and 80 mm long, with two 5 mm cross holes at mid-length, at right angles to each other and to the tube axis, each passing through both walls.",
        "engineer": "Hollow shaft 25 x 15 mm, 80 mm long, cross-drilled at mid-length with two 5 mm lubrication holes at 90 degrees to each other, each through both walls.",
        "intent": "A hollow tube with holes drilled across it in two directions at the middle.",
    },
    checks={
        "explicit": [bbox(rng(25), rng(25), rng(80)), boss(rng(25), 79.9), bore(rng(15), through=True),
                     holes(rng(5), (4, 4), through=True), nc("cross-hole axial position and the 90 degree angle")],
        "engineer": [bbox(rng(25), rng(25), rng(80)), boss(rng(25), 79.9), bore(rng(15), through=True),
                     holes(rng(5), (4, 4), through=True), nc("cross-hole axial position and the 90 degree angle")],
        "intent": [bore([1.0, 100.0], through=True), holes([0.5, 100.0], (5, 5), through=True), nc("sizes and hole directions")],
    },
    sources=["No standard: stated dimensions +-0.1",
             "The checker counts each wall crossing as its own through hole: two cross holes through both walls = 4 (positive control); intent counts every through hole of any size, bore included = 5",
             "Out of vocab (DSL v1): holes at right angles to the Z axis"],
    build=lambda: _c062(),
    fakes={"one cross hole": lambda: _c062(two=False)},
)


# c063 -------------------------------------------------------------------------
def _c063(p):
    L, W, tb, wp, hc, Db, d, dh = p["L"], p["W"], p["tb"], p["wp"], p["hc"], p["Db"], p["d"], p["dh"]
    base = box(0, 0, 0, L, W, tb)
    pedestal = box(L / 2 - wp / 2, 0, tb, wp, W, hc - tb)
    boss_ = cyl(Db / 2, W, (L / 2, 0, hc), "y")
    body = fuse(base, pedestal, boss_)
    return cut(body, cyl(d / 2, W + 2, (L / 2, -1, hc), "y"),
               cyl(dh / 2, tb + 2, (L / 2 - 31, W / 2, -1)), cyl(dh / 2, tb + 2, (L / 2 + 31, W / 2, -1)))


_c063_x = {"L": tol(80, 1), "W": tol(30, 1), "tb": tol(10, 1), "wp": tol(44, 1), "hc": fixed(27), "Db": tol(44, 1),
           "d": tol(22, -1), "dh": tol(9, -1)}
_c063_e = {**_c063_x, "d": (21.985, 22.0, 22.006, -1), "dh": (8.4, 9.0, 10.0, -1)}
concept(
    concept_id="c063", name="Pillow block for a 608 bearing", in_vocab=False,
    prompts={
        "explicit": "A bearing pillow block: an 80 x 30 x 10 mm base plate; on top of it, centred, a 44 mm wide pedestal the full 30 mm depth rising to a 44 mm diameter round boss whose axis is horizontal, runs along the 30 mm depth and sits 27 mm above the bottom face (49 mm overall height); a 22 mm bore straight through the boss on that axis; and two 9 mm vertical through holes in the base, 62 mm apart along the length and centred across the depth.",
        "engineer": "Pillow block housing for a 608 ball bearing: 80 x 30 x 10 mm base with two M8 clearance holes on 62 mm centres, 27 mm shaft-centre height, 44 mm diameter boss 30 mm wide, bearing seat bored straight through at K7.",
        "intent": "A pillow block that holds a 608 skateboard bearing with its shaft horizontal, bolted down with two bolts.",
    },
    checks={
        "explicit": [bbox(rng(30), rng(49), rng(80)), bore(rng(22), through=True),
                     holes(rng(9), (2, 2), through=True, pattern=[rng(62)]), ("volume", _c063, _c063_x)],
        "engineer": [bbox(rng(30), rng(49), rng(80)), bore([21.985, 22.006], through=True),
                     holes([8.4, 10.0], (2, 2), through=True, pattern=[rng(62)]), ("volume", _c063, _c063_e)],
        "intent": [bore([21.85, 22.1]), holes([3.0, 15.0], (2, 2), through=True), nc("base size and shaft height")],
    },
    sources=["608 bearing: 8 x 22 x 7 mm", "ISO 286-2 K7 for 18-30 mm: -0.015/+0.006 -> 21.985-22.006",
             "ISO 273 M8 clearance: fine 8.4, medium 9.0, coarse 10.0",
             "Out of vocab (DSL v1): horizontal (Y-axis) boss and bore"],
    build=lambda: _c063(nominal(_c063_x)),
    fakes={"vertical bore": lambda: cut(fuse(box(0, 0, 0, 80, 30, 10), box(18, 0, 10, 44, 30, 39)),
                                        cyl(11, 50, (40, 15, -1)), cyl(4.5, 12, (9, 15, -1)), cyl(4.5, 12, (71, 15, -1)))},
)


# c064 -------------------------------------------------------------------------
_c064_posts = [(6, 6), (74, 6), (6, 54), (74, 54)]


def _c064(p, posts=True):
    L, W, H, t, dp, dh, depth = p["L"], p["W"], p["H"], p["t"], p["dp"], p["dh"], p["depth"]
    shell = cut(box(0, 0, 0, L, W, H), box(t, t, t, L - 2 * t, W - 2 * t, H))
    if not posts:
        return shell
    body = fuse(shell, *[cyl(dp / 2, H - t, (x, y, t)) for x, y in _c064_posts])
    return cut(body, *[cyl(dh / 2, depth + 1, (x, y, H - depth)) for x, y in _c064_posts])


_c064_x = {"L": tol(80, 1), "W": tol(60, 1), "H": tol(30, 1), "t": tol(2, 1), "dp": tol(7, 1), "dh": tol(2.5, -1), "depth": tol(10, -1)}
concept(
    concept_id="c064", name="Open enclosure with four corner screw posts", in_vocab=False,
    prompts={
        "explicit": "An open-top box 80 x 60 x 30 mm outside with 2 mm walls and a 2 mm floor. Inside, four round screw posts 7 mm in diameter rise from the floor to the rim, each centred 6 mm in from the two nearest outside walls; each post has a 2.5 mm hole 10 mm deep drilled down from its top.",
        "engineer": "Open-top electronics enclosure, 80 x 60 x 30 mm outside, 2 mm wall and floor, with four full-height 7 mm screw bosses in the corners (centres 6 mm from the outside faces), each with a 10 mm deep 2.5 mm pilot hole for M3 self-tapping lid screws.",
        "intent": "A small open box for electronics with screw posts in the four corners for a lid.",
    },
    checks={
        "explicit": [bbox(rng(30), rng(60), rng(80)), boss(rng(7), 27.9, (4, 4)),
                     holes(rng(2.5), (4, 4), through=False, depth_min=9.9, pattern=pattern_of(_c064_posts)),
                     ("volume", _c064, _c064_x)],
        "engineer": [bbox(rng(30), rng(60), rng(80)), boss(rng(7), 27.9, (4, 4)),
                     holes(rng(2.5), (4, 4), through=False, depth_min=9.9, pattern=pattern_of(_c064_posts)),
                     ("volume", _c064, _c064_x)],
        "intent": [boss([3.0, 15.0], count=(4, 4)), holes([1.5, 4.5], (4, 4), through=False), nc("box size and wall thickness")],
    },
    sources=["No standard: stated dimensions +-0.1; 2.5 mm pilot for M3 self-tapping screws in plastic (common practice)",
             "Out of vocab (DSL v1): shell + 4 posts + 4 holes needs 19 steps, over the 16-step limit"],
    build=lambda: _c064(nominal(_c064_x)),
    fakes={"no posts": lambda: _c064(nominal(_c064_x), posts=False)},
)


# c065 -------------------------------------------------------------------------
def _c065(p, all_vertical=False):
    L, W, H = p["L"], p["W"], p["H"]
    block = box(0, 0, 0, L, W, H)
    if all_vertical:
        return cut(block, cyl(p["dx"] / 2, H + 2, (10, 10, -1)), cyl(p["dy"] / 2, H + 2, (30, 30, -1)),
                   cyl(p["dz"] / 2, H + 2, (12, 28, -1)))
    return cut(block, cyl(p["dx"] / 2, L + 2, (-1, 12, 10), "x"), cyl(p["dy"] / 2, W + 2, (28, -1, 20), "y"),
               cyl(p["dz"] / 2, H + 2, (12, 28, -1)))


_c065_x = {"L": tol(40, 1), "W": tol(40, 1), "H": tol(30, 1), "dx": tol(10, -1), "dy": tol(8, -1), "dz": tol(6, -1)}
concept(
    concept_id="c065", name="Manifold block with three non-meeting bores", in_vocab=False,
    prompts={
        "explicit": "A 40 x 40 x 30 mm block (30 mm is the height) with three straight through bores, one along each axis, placed so that no two bores meet: a 10 mm bore along the length, an 8 mm bore along the width and a 6 mm vertical bore.",
        "engineer": "Manifold block 40 x 40 x 30 mm high with three cross-drilled through passages that do not intersect, one per axis: 10 mm along X, 8 mm along Y, 6 mm along Z.",
        "intent": "A small block with three drilled passages running through it in three different directions, not meeting each other.",
    },
    checks={
        "explicit": [bbox(rng(30), rng(40), rng(40)), holes(rng(10), (1, 1), through=True), holes(rng(8), (1, 1), through=True),
                     holes(rng(6), (1, 1), through=True), ("volume", _c065, _c065_x),
                     nc("bore positions and which 40 mm direction carries the 10 mm vs the 8 mm bore")],
        "engineer": [bbox(rng(30), rng(40), rng(40)), holes(rng(10), (1, 1), through=True), holes(rng(8), (1, 1), through=True),
                     holes(rng(6), (1, 1), through=True), ("volume", _c065, _c065_x),
                     nc("bore positions and which 40 mm direction carries the 10 mm vs the 8 mm bore")],
        "intent": [holes([1.0, 20.0], (3, 3), through=True), nc("block size and bore directions")],
    },
    sources=["No standard: stated dimensions +-0.1",
             "Volume separates bores along X/Y (40 mm long) from all three vertical (30 mm long)",
             "Out of vocab (DSL v1): bores along X and Y"],
    build=lambda: _c065(nominal(_c065_x)),
    fakes={"all bores vertical": lambda: _c065(nominal(_c065_x), all_vertical=True)},
)


# ---------------------------------------------------------------- assemble + verify

def _resolve(check):
    if isinstance(check, tuple):
        kind, build, params = check
        lo, hi = volume_range(build, params)
        return volume(None if kind == "volume_max" else lo, hi)
    return check


def assemble(entry: dict) -> dict:
    checks = {ph: [_resolve(c) for c in entry["checks"][ph]] for ph in ("explicit", "engineer", "intent")}
    out = {k: entry[k] for k in ("concept_id", "name", "in_vocab", "prompts")}
    out["checks"] = checks
    out["sources"] = entry["sources"]
    out["reference_spec"] = entry.get("reference_spec")
    Concept.model_validate(out)
    return out


def _grade(shape, checks):
    return grade_shape(shape, CHECK_LIST.validate_python(checks))


def verify(entry: dict, row: dict) -> list[str]:
    cid, problems = row["concept_id"], []
    shapes = {"explicit": entry["build"](), "intent": entry["build"]()}
    shapes["engineer"] = entry["build_engineer"]() if "build_engineer" in entry else shapes["explicit"]
    for ph in ("explicit", "engineer", "intent"):
        rep = _grade(shapes[ph], row["checks"][ph])
        if not rep["passed"]:
            problems.append(f"{cid} positive control fails {ph}: {[c for c in rep['checks'] if c['status'] == 'fail'] or rep['gate']}")
    for name, fake in entry["fakes"].items():
        rep = _grade(fake(), row["checks"]["explicit"])
        if rep["passed"]:
            problems.append(f"{cid} negative control '{name}' passes explicit")
    if row["in_vocab"]:
        ref = build_shape(PartSpec.model_validate(row["reference_spec"]))
        for ph in ("explicit", "engineer"):
            rep = _grade(ref, row["checks"][ph])
            if not rep["passed"]:
                problems.append(f"{cid} reference_spec fails {ph}: {[c for c in rep['checks'] if c['status'] == 'fail']}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help=f"write {OUT.relative_to(ROOT)}")
    args = ap.parse_args()
    print(f"OCC backend: {BACKEND}")
    rows, problems = [], []
    for entry in CONCEPTS:
        row = assemble(entry)
        rows.append(row)
        found = verify(entry, row)
        problems += found
        print(f"{row['concept_id']} {'ok ' if not found else 'BAD'} in_vocab={row['in_vocab']!s:5} fakes={len(entry['fakes'])} {row['name']}")
    ids = [r["concept_id"] for r in rows]
    assert ids == [f"c{i:03d}" for i in range(51, 66)], ids
    for p in problems:
        print("  " + p)
    if problems:
        return 1
    if args.write:
        OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
        print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} concepts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
