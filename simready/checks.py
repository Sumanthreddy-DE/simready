"""Essential Phase 1A geometry checks."""

from __future__ import annotations

from typing import Any

try:
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.ShapeAnalysis import ShapeAnalysis_Shell
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCC.Core.TopExp import TopExp, TopExp_Explorer
    from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
    from OCC.Core.TopoDS import topods
except ImportError:  # pragma: no cover
    BRep_Tool = None
    BRepAdaptor_Curve = None
    ShapeAnalysis_Shell = None
    TopAbs_EDGE = TopAbs_FACE = None
    TopExp = None
    TopExp_Explorer = None
    TopTools_IndexedDataMapOfShapeListOfShape = None
    topods = None


SHORT_EDGE_RATIO = 0.005
DEGENERATE_EDGE_TOLERANCE = 1e-7
OPEN_EDGE_TOLERANCE = 1e-7


def _bbox_dims(bounding_box: dict[str, float] | None) -> tuple[float, float, float]:
    if not bounding_box:
        return 0.0, 0.0, 0.0
    return (
        bounding_box["xmax"] - bounding_box["xmin"],
        bounding_box["ymax"] - bounding_box["ymin"],
        bounding_box["zmax"] - bounding_box["zmin"],
    )


def _short_edge_threshold(bounding_box: dict[str, float] | None) -> float:
    dims = _bbox_dims(bounding_box)
    max_dim = max(dims) if dims else 0.0
    return max_dim * SHORT_EDGE_RATIO if max_dim > 0 else 0.0


def check_degenerate_geometry(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    if geometry_summary.face_count <= 0 or geometry_summary.edge_count <= 0:
        findings.append(
            {
                "check": "DegenerateGeometry",
                "severity": "Major",
                "detail": "Shape has no faces or edges after parsing.",
                "suggestion": "Inspect the exported geometry for collapsed topology.",
            }
        )

    if BRepAdaptor_Curve is None or TopExp_Explorer is None or TopAbs_EDGE is None:
        return findings

    zero_length_edges = 0
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edge = topods.Edge(explorer.Current()) if topods is not None else explorer.Current()
        try:
            curve = BRepAdaptor_Curve(edge)
            if curve.Is3DCurve() and curve.FirstParameter() != curve.LastParameter():
                length = curve.LastParameter() - curve.FirstParameter()
            else:
                length = 0.0
        except Exception:
            length = 0.0

        if abs(length) <= DEGENERATE_EDGE_TOLERANCE:
            zero_length_edges += 1
        explorer.Next()

    if zero_length_edges:
        findings.append(
            {
                "check": "DegenerateEdges",
                "severity": "Major",
                "detail": f"Detected {zero_length_edges} zero-length or collapsed edges.",
                "suggestion": "Remove or repair collapsed topology before meshing.",
            }
        )

    return findings


def check_non_manifold_edges(shape: Any) -> list[dict[str, Any]]:
    if TopExp is None or TopTools_IndexedDataMapOfShapeListOfShape is None or TopAbs_EDGE is None or TopAbs_FACE is None:
        return []

    edge_face_map = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, edge_face_map)

    bad_edges = 0
    for index in range(1, edge_face_map.Extent() + 1):
        if edge_face_map.FindFromIndex(index).Extent() > 2:
            bad_edges += 1

    if not bad_edges:
        return []

    return [
        {
            "check": "NonManifoldEdges",
            "severity": "Major",
            "detail": f"Detected {bad_edges} non-manifold edges shared by more than two faces.",
            "suggestion": "Repair or simplify the topology before simulation.",
        }
    ]


def check_open_boundaries(shape: Any, geometry_summary: Any | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    if geometry_summary is not None and geometry_summary.solid_count <= 0 and geometry_summary.face_count > 0:
        findings.append(
            {
                "check": "OpenBoundaries",
                "severity": "Major",
                "detail": "Geometry contains faces but no closed solid volume.",
                "suggestion": "Close the shell or export a watertight solid before simulation.",
            }
        )

    if BRep_Tool is None or TopExp is None or TopTools_IndexedDataMapOfShapeListOfShape is None or TopAbs_EDGE is None or TopAbs_FACE is None:
        return findings

    edge_face_map = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, edge_face_map)

    open_edges = 0
    degenerate_edges = 0
    for index in range(1, edge_face_map.Extent() + 1):
        edge = edge_face_map.FindKey(index)
        attached_faces = edge_face_map.FindFromIndex(index).Extent()
        if attached_faces == 1:
            open_edges += 1
        try:
            if BRep_Tool.Degenerated(edge):
                degenerate_edges += 1
        except Exception:
            pass

    if open_edges > 0:
        findings.append(
            {
                "check": "OpenBoundaries",
                "severity": "Major",
                "detail": f"Detected {open_edges} open boundary edges.",
                "suggestion": "Close gaps or stitch surfaces into a watertight solid.",
            }
        )

    if degenerate_edges > 0:
        findings.append(
            {
                "check": "DegenerateTopology",
                "severity": "Major",
                "detail": f"Detected {degenerate_edges} degenerated edges flagged by OCC.",
                "suggestion": "Repair the topology before meshing.",
            }
        )

    if ShapeAnalysis_Shell is not None and TopExp_Explorer is not None and TopAbs_FACE is not None and open_edges == 0:
        try:
            shell_analysis = ShapeAnalysis_Shell()
            has_bad_edges = False
            explorer = TopExp_Explorer(shape, TopAbs_FACE)
            while explorer.More():
                face = topods.Face(explorer.Current()) if topods is not None else explorer.Current()
                if shell_analysis.CheckOrientedShells(face, True):
                    has_bad_edges = True
                    break
                explorer.Next()
            if has_bad_edges:
                findings.append(
                    {
                        "check": "PotentialGaps",
                        "severity": "Major",
                        "detail": "Shell orientation analysis suggests open or inconsistent boundaries.",
                        "suggestion": "Inspect face connectivity and shell closure.",
                    }
                )
        except Exception:
            pass

    return findings


def check_short_edges(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    if BRepAdaptor_Curve is None or TopExp_Explorer is None or TopAbs_EDGE is None:
        return []

    threshold = _short_edge_threshold(geometry_summary.bounding_box)
    if threshold <= 0:
        return []

    short_edges = 0
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edge = topods.Edge(explorer.Current()) if topods is not None else explorer.Current()
        try:
            curve = BRepAdaptor_Curve(edge)
            length = abs(curve.LastParameter() - curve.FirstParameter())
        except Exception:
            length = 0.0

        if length > DEGENERATE_EDGE_TOLERANCE and length < threshold:
            short_edges += 1
        explorer.Next()

    if not short_edges:
        return []

    return [
        {
            "check": "ShortEdges",
            "severity": "Minor",
            "detail": f"Detected {short_edges} edges shorter than {threshold:.6g} model units.",
            "suggestion": "Merge or simplify tiny edges that may degrade mesh quality.",
        }
    ]


def run_essential_checks(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    findings.extend(check_degenerate_geometry(shape, geometry_summary))
    findings.extend(check_non_manifold_edges(shape))
    findings.extend(check_open_boundaries(shape, geometry_summary))
    findings.extend(check_short_edges(shape, geometry_summary))

    if geometry_summary.solid_count > 1:
        findings.append(
            {
                "check": "MultiBodyDetected",
                "severity": "Info",
                "detail": f"Detected {geometry_summary.solid_count} solids.",
                "suggestion": "Split and analyze bodies individually in a later phase.",
            }
        )

    return findings
