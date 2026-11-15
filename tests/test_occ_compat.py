"""Exercise the pythonocc-style API against whichever binding is installed."""

import pytest
import importlib

from simready import occ_compat as occ
from simready.occ_utils import edge_length, iter_faces, shape_bounding_box

pytestmark = pytest.mark.skipif(not occ.OCC_AVAILABLE, reason="OCC unavailable")


def test_backend():
    assert occ.BACKEND in {"pythonocc", "ocp"}


def test_missing_pythonocc_attribute_falls_back_to_ocp(monkeypatch):
    pytest.importorskip("OCP")  # the fallback target; absent in the pythonocc-only sr env
    real_import = importlib.import_module

    def import_with_missing_attribute(name, *args, **kwargs):
        if name == "OCC.Core.Bnd":
            # An installed module lacking Bnd_Box makes getattr raise AttributeError.
            return object()
        return real_import(name, *args, **kwargs)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(importlib, "import_module", import_with_missing_attribute)
            importlib.reload(occ)
            assert occ.BACKEND == "ocp"
    finally:
        importlib.reload(occ)


def test_bounding_adapters_preserve_gap_and_optimal_extents():
    shape = occ.BRepPrimAPI_MakeBox(2.0, 3.0, 4.0).Shape()
    box = occ.Bnd_Box()
    occ.brepbndlib.Add(shape, box)
    assert box.CornerMax().X() - box.CornerMin().X() > 2.0
    optimal = occ.Bnd_Box()
    occ.brepbndlib.AddOptimal(shape, optimal, False, False)
    assert optimal.CornerMax().X() - optimal.CornerMin().X() == 2.0
    bb = shape_bounding_box(shape)
    assert bb["xmax"] - bb["xmin"] > 2.0


def test_mass_properties_adapters():
    shape = occ.BRepPrimAPI_MakeBox(2.0, 3.0, 4.0).Shape()
    props = occ.GProp_GProps()
    occ.brepgprop.VolumeProperties(shape, props)
    assert props.Mass() == pytest.approx(24.0)
    occ.brepgprop.SurfaceProperties(shape, props)
    assert props.Mass() == pytest.approx(52.0)


def test_topology_uv_and_curve_adapters():
    shape = occ.BRepPrimAPI_MakeBox(2.0, 3.0, 4.0).Shape()
    solid = occ.topods.Solid(shape)
    _, face = iter_faces(solid)[0]
    face = occ.topods.Face(face)
    u0, u1, v0, v1 = occ.breptools.UVBounds(face)
    assert u1 > u0 and v1 > v0
    mapping = occ.TopTools_IndexedDataMapOfShapeListOfShape()
    occ.topexp.MapShapesAndAncestors(shape, occ.TopAbs_EDGE, occ.TopAbs_FACE, mapping)
    assert mapping.Extent() == 12
    edge = occ.topods.Edge(occ.TopExp_Explorer(shape, occ.TopAbs_EDGE).Current())
    assert edge_length(edge) > 0
