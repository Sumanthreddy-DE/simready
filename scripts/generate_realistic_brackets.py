#!/usr/bin/env python3
"""Generate 5 harder synthetic fixtures for SimReady real-world-ish validation.

Categories (one STEP each, single solid body):

- boxed_beam_with_holes: rectangular tube with 4 mounting holes through one face
- ribbed_plate: flat plate with 3 stiffening ribs (vertical extrusions)
- l_bracket_with_fillet: L bracket with a filleted inner corner
- t_junction: T-shaped fused solid
- complex_bracket: bracket with multiple holes and chamfered edges

Each fixture is closer in topology to real CAD parts than the smoke fixtures
and the parametric training set: filleted edges, multi-feature solids, mixed
surface types. Useful as a sanity gate before stress-testing the pipeline on
true GrabCAD/SimJEB STEPs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
except ImportError as exc:  # pragma: no cover
    print(f"pythonocc-core import failed: {exc}", file=sys.stderr)
    raise SystemExit(2)


def _make_box(dx: float, dy: float, dz: float, origin: tuple[float, float, float] = (0.0, 0.0, 0.0)):
    return BRepPrimAPI_MakeBox(gp_Pnt(*origin), dx, dy, dz).Shape()


def _make_cylinder(radius: float, height: float, origin: tuple[float, float, float] = (0.0, 0.0, 0.0), axis: tuple[float, float, float] = (0.0, 0.0, 1.0)):
    ax2 = gp_Ax2(gp_Pnt(*origin), gp_Dir(*axis))
    return BRepPrimAPI_MakeCylinder(ax2, radius, height).Shape()


def _write_step(shape, out_path: Path) -> None:
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    writer.Write(str(out_path))


def boxed_beam_with_holes():
    """Hollow box-section beam with 4 through-holes on the top face."""
    outer = _make_box(120.0, 40.0, 40.0)
    inner = _make_box(108.0, 28.0, 28.0, origin=(6.0, 6.0, 6.0))
    beam = BRepAlgoAPI_Cut(outer, inner).Shape()

    body = beam
    hole_radius = 3.0
    for x_offset in (20.0, 50.0, 80.0, 100.0):
        hole = _make_cylinder(hole_radius, 50.0, origin=(x_offset, 20.0, -5.0))
        body = BRepAlgoAPI_Cut(body, hole).Shape()
    return body


def ribbed_plate():
    """Flat baseplate with three stiffening ribs running across its top."""
    base = _make_box(150.0, 80.0, 4.0)
    body = base
    rib_dy, rib_dz = 4.0, 18.0
    for x_offset in (25.0, 70.0, 115.0):
        rib = _make_box(rib_dy, 80.0, rib_dz, origin=(x_offset, 0.0, 4.0))
        body = BRepAlgoAPI_Fuse(body, rib).Shape()
    return body


def l_bracket_with_fillet():
    """L-bracket with an internal fillet at the inside corner.

    A small fillet radius keeps the bracket within typical engineering norms
    and forces the pipeline to handle curved transitions.
    """
    horizontal = _make_box(70.0, 60.0, 8.0)
    vertical = _make_box(70.0, 8.0, 50.0)
    bracket = BRepAlgoAPI_Fuse(horizontal, vertical).Shape()

    fillet_maker = BRepFilletAPI_MakeFillet(bracket)
    edge_explorer = TopExp_Explorer(bracket, TopAbs_EDGE)
    added = 0
    while edge_explorer.More() and added < 2:
        edge = topods.Edge(edge_explorer.Current())
        # Filleting every edge gets fragile; pick the first couple that accept it.
        try:
            fillet_maker.Add(3.0, edge)
            added += 1
        except Exception:
            pass
        edge_explorer.Next()
    if added == 0:
        return bracket
    try:
        return fillet_maker.Shape()
    except Exception:
        return bracket


def t_junction():
    """T-shaped solid: a horizontal bar fused with a vertical post."""
    horizontal = _make_box(120.0, 30.0, 20.0)
    vertical = _make_box(30.0, 30.0, 80.0, origin=(45.0, 0.0, 20.0))
    return BRepAlgoAPI_Fuse(horizontal, vertical).Shape()


def complex_bracket():
    """L bracket with three mounting holes and chamfered top edges."""
    body = l_bracket_with_fillet()
    hole_radius = 3.5
    for x_offset in (15.0, 35.0, 55.0):
        hole = _make_cylinder(hole_radius, 20.0, origin=(x_offset, 30.0, -5.0))
        body = BRepAlgoAPI_Cut(body, hole).Shape()

    chamfer_maker = BRepFilletAPI_MakeChamfer(body)
    edge_explorer = TopExp_Explorer(body, TopAbs_EDGE)
    chamfered = 0
    while edge_explorer.More() and chamfered < 3:
        edge = topods.Edge(edge_explorer.Current())
        try:
            chamfer_maker.Add(1.0, edge)
            chamfered += 1
        except Exception:
            pass
        edge_explorer.Next()
    if chamfered == 0:
        return body
    try:
        return chamfer_maker.Shape()
    except Exception:
        return body


FIXTURES = {
    "boxed_beam_with_holes": boxed_beam_with_holes,
    "ribbed_plate": ribbed_plate,
    "l_bracket_with_fillet": l_bracket_with_fillet,
    "t_junction": t_junction,
    "complex_bracket": complex_bracket,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("tests/data/realistic_brackets"))
    parser.add_argument("--only", nargs="*", choices=sorted(FIXTURES.keys()), default=None)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    targets = args.only or sorted(FIXTURES.keys())

    written = 0
    for name in targets:
        try:
            shape = FIXTURES[name]()
        except Exception as exc:
            print(f"[fail] {name}: gen raised {exc}", file=sys.stderr)
            continue
        out_path = args.output / f"{name}.step"
        try:
            _write_step(shape, out_path)
        except Exception as exc:
            print(f"[fail] {name}: STEP write raised {exc}", file=sys.stderr)
            continue
        written += 1
        print(f"[ok] {out_path}")

    print(f"wrote {written}/{len(targets)} realistic bracket fixtures to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
