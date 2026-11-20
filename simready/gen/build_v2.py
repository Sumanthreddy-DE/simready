"""Trusted executor for DSL v2 (design E2). In-process; callers that need a
wall-clock bound run it in a spawn child (``simready.bench.attempt``).

``KernelBuildError`` marks failures the *spec* caused (fillet too large,
selector matched nothing, degenerate polygon): the bench scores them as
F4_build_error. Any other exception is an executor bug.
"""

from __future__ import annotations

import math
from typing import Any

from simready.gen.spec import BoxOp, CutOp, FuseOp
from simready.gen.spec_v2 import (
    ChamferOp,
    ConeOp,
    CylOpV2,
    FilletOp,
    GridOp,
    PartSpecV2,
    PolarOp,
    PrismOp,
    RegularPrismOp,
    SphereOp,
)
from simready.occ_compat import (
    BRepAdaptor_Curve,
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Fuse,
    BRepCheck_Analyzer,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_Transform,
    BRepFilletAPI_MakeChamfer,
    BRepFilletAPI_MakeFillet,
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCone,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakePrism,
    BRepPrimAPI_MakeSphere,
    GeomAbs_Line,
    TopAbs_EDGE,
    TopExp_Explorer,
    gp_Ax1,
    gp_Ax2,
    gp_Dir,
    gp_Pnt,
    gp_Trsf,
    gp_Vec,
    topods,
)

_AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
_PLANE = {"z": (0, 1), "x": (1, 2), "y": (0, 2)}  # (u, v) -> coordinate indices
_SEL_TOL = 1e-6


class KernelBuildError(RuntimeError):
    """The spec asked for geometry the kernel cannot make."""


def _ax2(at, axis):
    return gp_Ax2(gp_Pnt(*at), gp_Dir(*_AXES[axis]))


def _bool(op_cls, a, b):
    op = op_cls(a, b)
    op.Build()
    if not op.IsDone():
        raise KernelBuildError(f"{op_cls.__name__} failed")
    return op.Shape()


def _uv_to_xyz(at, axis, u, v):
    p = list(at)
    iu, iv = _PLANE[axis]
    p[iu] += u
    p[iv] += v
    return tuple(p)


def _prism(points_uv, h, at, axis):
    poly = BRepBuilderAPI_MakePolygon()
    for u, v in points_uv:
        poly.Add(gp_Pnt(*_uv_to_xyz(at, axis, u, v)))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire())
    if not face.IsDone():
        raise KernelBuildError("prism polygon is not a valid planar face")
    d = _AXES[axis]
    return BRepPrimAPI_MakePrism(face.Face(), gp_Vec(d[0] * h, d[1] * h, d[2] * h)).Shape()


def _regular_points(sides, across_flats):
    rc = across_flats / (2 * math.cos(math.pi / sides))
    offset = math.pi / 2 - math.pi / sides  # puts one flat perpendicular to v, i.e. parallel to u
    return [(rc * math.cos(offset + 2 * math.pi * k / sides), rc * math.sin(offset + 2 * math.pi * k / sides))
            for k in range(sides)]


def _transformed(shape, trsf):
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def _fuse_all(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = _bool(BRepAlgoAPI_Fuse, out, s)
    return out


def _polar(shape, op: PolarOp):
    copies = [shape]
    for k in range(1, op.count):
        t = gp_Trsf()
        t.SetRotation(gp_Ax1(gp_Pnt(*op.center), gp_Dir(*_AXES[op.axis])), 2 * math.pi * k / op.count)
        copies.append(_transformed(shape, t))
    return _fuse_all(copies)


def _grid(shape, op: GridOp):
    copies = []
    for i in range(op.nx):
        for j in range(op.ny):
            t = gp_Trsf()
            t.SetTranslation(gp_Vec(i * op.dx, j * op.dy, 0.0))
            copies.append(_transformed(shape, t))
    return _fuse_all(copies)


def _unique_edges(shape) -> list[Any]:
    edges: list[Any] = []
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        e = topods.Edge(exp.Current())
        if not any(e.IsSame(seen) for seen in edges):
            edges.append(e)
        exp.Next()
    return edges


def select_edges(shape, selector: str) -> list[Any]:
    edges = _unique_edges(shape)
    if selector == "all":
        return edges
    kind, axis = selector[0], "xyz".index(selector[1])
    if kind == "|":
        out = []
        for e in edges:
            c = BRepAdaptor_Curve(e)
            if c.GetType() == GeomAbs_Line:
                d = c.Line().Direction()
                if abs(abs((d.X(), d.Y(), d.Z())[axis]) - 1.0) < _SEL_TOL:
                    out.append(e)
        return out
    mids = []
    for e in edges:
        c = BRepAdaptor_Curve(e)
        p = c.Value((c.FirstParameter() + c.LastParameter()) / 2)
        mids.append((p.X(), p.Y(), p.Z())[axis])
    target = max(mids) if kind == ">" else min(mids)
    return [e for e, m in zip(edges, mids) if abs(m - target) <= _SEL_TOL]


def _edge_op(shape, op):
    edges = select_edges(shape, op.edges)
    if not edges:
        raise KernelBuildError(f"edge selector {op.edges!r} matched no edges")
    maker = BRepFilletAPI_MakeFillet(shape) if isinstance(op, FilletOp) else BRepFilletAPI_MakeChamfer(shape)
    size = op.r if isinstance(op, FilletOp) else op.d
    for e in edges:
        maker.Add(size, e)
    try:
        maker.Build()
        ok = maker.IsDone()
    except Exception as exc:  # OCCT raises Standard_Failure subclasses for impossible blends
        raise KernelBuildError(f"{op.op} failed: {type(exc).__name__}: {exc}") from exc
    if not ok:
        raise KernelBuildError(f"{op.op} of size {size} on {len(edges)} edges could not be built")
    result = maker.Shape()
    # OCCT can report IsDone() for an oversized blend and return an invalid solid
    # (probed 2026-11-20: r = 3 on a 4 mm cube gave volume 490461 mm^3, IsValid False).
    if not BRepCheck_Analyzer(result).IsValid():
        raise KernelBuildError(f"{op.op} of size {size} produced an invalid solid")
    return result


def build_shape_v2(spec: PartSpecV2):
    """Materialize ``spec``; returns the last step's shape."""
    shapes: list[Any] = []
    for s in spec.steps:
        if isinstance(s, BoxOp):
            shapes.append(BRepPrimAPI_MakeBox(gp_Pnt(*s.at), s.dx, s.dy, s.dz).Shape())
        elif isinstance(s, CylOpV2):
            shapes.append(BRepPrimAPI_MakeCylinder(_ax2(s.at, s.axis), s.r, s.h).Shape())
        elif isinstance(s, ConeOp):
            shapes.append(BRepPrimAPI_MakeCone(_ax2(s.at, s.axis), s.r1, s.r2, s.h).Shape())
        elif isinstance(s, SphereOp):
            shapes.append(BRepPrimAPI_MakeSphere(gp_Pnt(*s.at), s.r).Shape())
        elif isinstance(s, PrismOp):
            shapes.append(_prism(s.points, s.h, s.at, s.axis))
        elif isinstance(s, RegularPrismOp):
            shapes.append(_prism(_regular_points(s.sides, s.across_flats), s.h, s.at, s.axis))
        elif isinstance(s, PolarOp):
            shapes.append(_polar(shapes[s.of], s))
        elif isinstance(s, GridOp):
            shapes.append(_grid(shapes[s.of], s))
        elif isinstance(s, (FilletOp, ChamferOp)):
            shapes.append(_edge_op(shapes[s.a], s))
        elif isinstance(s, FuseOp):
            shapes.append(_bool(BRepAlgoAPI_Fuse, shapes[s.a], shapes[s.b]))
        elif isinstance(s, CutOp):
            shapes.append(_bool(BRepAlgoAPI_Cut, shapes[s.a], shapes[s.b]))
        else:  # pragma: no cover — the discriminator guarantees the type
            raise TypeError(f"unknown op {type(s).__name__}")
    return shapes[-1]
