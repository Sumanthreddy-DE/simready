"""Small pythonocc-first compatibility surface for build/benchmark geometry.

Names retain pythonocc spelling; OCP static methods are adapted here only.
Missing bindings leave every exported geometry name as None.
"""

from importlib import import_module
from types import SimpleNamespace

# Canonical pythonocc module -> public names (also the laptop verification map).
_MODULE_NAMES = {
    "Bnd": ("Bnd_Box",),
    "BRep": ("BRep_Builder",),
    "BRepAdaptor": ("BRepAdaptor_Curve", "BRepAdaptor_Surface"),
    "BRepAlgoAPI": ("BRepAlgoAPI_Cut", "BRepAlgoAPI_Fuse"),
    "BRepCheck": ("BRepCheck_Analyzer",),
    "BRepClass3d": ("BRepClass3d_SolidClassifier",),
    "BRepGProp": ("BRepGProp_Face",),
    "BRepPrimAPI": ("BRepPrimAPI_MakeBox", "BRepPrimAPI_MakeCylinder"),
    "GCPnts": ("GCPnts_AbscissaPoint",),
    "GeomAbs": ("GeomAbs_Cylinder",),
    "GProp": ("GProp_GProps",),
    "IFSelect": ("IFSelect_RetDone",),
    "ShapeAnalysis": ("ShapeAnalysis_FreeBounds",),
    "STEPControl": ("STEPControl_AsIs", "STEPControl_Reader", "STEPControl_Writer"),
    "TopAbs": ("TopAbs_EDGE", "TopAbs_FACE", "TopAbs_SOLID", "TopAbs_OUT"),
    "TopExp": ("TopExp_Explorer",),
    "TopoDS": ("TopoDS_Shell",),
    "TopTools": ("TopTools_IndexedDataMapOfShapeListOfShape",),
    "gp": ("gp_Ax2", "gp_Dir", "gp_Pnt", "gp_Vec"),
}
_ADAPTER_NAMES = ("brepbndlib", "brepgprop", "breptools", "topexp", "topods")
__all__ = [name for names in _MODULE_NAMES.values() for name in names] + list(_ADAPTER_NAMES) + ["breptools_UVBounds"]


def _load(prefix):
    return {
        name: (
            getattr(import_module("OCP.collections"),
                    "IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher")
            if prefix == "OCP" and module == "TopTools"
            else getattr(import_module(f"{prefix}.{module}"), name)
        )
        for module, names in _MODULE_NAMES.items()
        for name in names
    }


def _pythonocc():
    names = _load("OCC.Core")
    for module, name in zip(
        ("BRepBndLib", "BRepGProp", "BRepTools", "TopExp", "TopoDS"), _ADAPTER_NAMES
    ):
        names[name] = getattr(import_module(f"OCC.Core.{module}"), name)
    names["breptools_UVBounds"] = getattr(
        import_module("OCC.Core.BRepTools"), "breptools_UVBounds", None
    )
    return names


def _ocp():
    names = _load("OCP")
    for module, cls, public, methods in (
        ("BRepBndLib", "BRepBndLib", "brepbndlib", ("Add", "AddOptimal")),
        ("BRepGProp", "BRepGProp", "brepgprop", ("VolumeProperties", "SurfaceProperties")),
        ("BRepTools", "BRepTools", "breptools", ("UVBounds",)),
        ("TopExp", "TopExp", "topexp", ("MapShapesAndAncestors",)),
    ):
        source = getattr(import_module(f"OCP.{module}"), cls)
        names[public] = SimpleNamespace(**{m: getattr(source, m + "_s") for m in methods})
    source = import_module("OCP.TopoDS").TopoDS
    names["topods"] = SimpleNamespace(**{m: getattr(source, m) for m in ("Face", "Solid", "Edge")})
    # OCP exposes Length_s, whereas pythonocc callers use Length.
    source = names["GCPnts_AbscissaPoint"]
    names["GCPnts_AbscissaPoint"] = SimpleNamespace(Length=source.Length_s)
    names["breptools_UVBounds"] = names["breptools"].UVBounds
    return names


BACKEND = None
try:
    _names = _pythonocc()
    BACKEND = "pythonocc"
except ImportError:
    try:
        _names = _ocp()
        BACKEND = "ocp"
    except ImportError:
        _names = dict.fromkeys(__all__)
globals().update(_names)
OCC_AVAILABLE = BACKEND is not None
