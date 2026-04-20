"""Geometry checks for SimReady Phase 1."""

from __future__ import annotations

from typing import Any

try:
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Cylinder
    from OCC.Core.ShapeAnalysis import ShapeAnalysis_Shell
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCC.Core.TopExp import TopExp, TopExp_Explorer
    from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
    from OCC.Core.TopoDS import topods
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
except ImportError:  # pragma: no cover
    BRep_Tool = None
    BRepAdaptor_Curve = None
    BRepAdaptor_Surface = None
    GeomAbs_Cylinder = None
    ShapeAnalysis_Shell = None
    TopAbs_EDGE = TopAbs_FACE = None
    TopExp = None
    TopExp_Explorer = None
    TopTools_IndexedDataMapOfShapeListOfShape = None
    topods = None
    brepgprop = None
    GProp_GProps = None


SHORT_EDGE_RATIO = 0.005
THIN_WALL_RATIO = 0.03
SMALL_FEATURE_RATIO = 0.02
SMALL_FEATURE_EDGE_RATIO = 0.2
SMALL_FILLET_RADIUS_RATIO = 0.03
DEGENERATE_EDGE_TOLERANCE = 1e-7


def _bbox_dims(bounding_box: dict[str, float] | None) -> tuple[float, float, float]:
    if not bounding_box:
        return 0.0, 0.0, 0.0
    return (
        bounding_box["xmax"] - bounding_box["xmin"],
        bounding_box["ymax"] - bounding_box["ymin"],
        bounding_box["zmax"] - bounding_box["zmin"],
    )


def _max_dim(bounding_box: dict[str, float] | None) -> float:
    dims = _bbox_dims(bounding_box)
    return max(dims) if dims else 0.0


def _min_nonzero_dim(bounding_box: dict[str, float] | None) -> float:
    dims = [d for d in _bbox_dims(bounding_box) if d > 0]
    return min(dims) if dims else 0.0


def _short_edge_threshold(bounding_box: dict[str, float] | None) -> float:
    max_dim = _max_dim(bounding_box)
    return max_dim * SHORT_EDGE_RATIO if max_dim > 0 else 0.0


def _surface_area(shape: Any) -> float:
    if brepgprop is None or GProp_GProps is None:
        return 0.0
    props = GProp_GProps()
    brepgprop.SurfaceProperties(shape, props)
    return props.Mass()


def _edge_length(edge: Any) -> float:
    if BRepAdaptor_Curve is None:
        return 0.0
    try:
        curve = BRepAdaptor_Curve(edge)
        return abs(curve.LastParameter() - curve.FirstParameter())
    except Exception:
        return 0.0


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
        if abs(_edge_length(edge)) <= DEGENERATE_EDGE_TOLERANCE:
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
    if TopExp_Explorer is None or TopAbs_EDGE is None:
        return []

    threshold = _short_edge_threshold(geometry_summary.bounding_box)
    if threshold <= 0:
        return []

    short_edges = 0
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edge = topods.Edge(explorer.Current()) if topods is not None else explorer.Current()
        length = _edge_length(edge)
        if DEGENERATE_EDGE_TOLERANCE < length < threshold:
            short_edges += 1
        explorer.Next()

    if not short_edges:
        return []

    severity = "Major" if short_edges >= 8 else "Minor"
    return [
        {
            "check": "ShortEdges",
            "severity": severity,
            "detail": f"Detected {short_edges} edges shorter than {threshold:.6g} model units.",
            "suggestion": "Merge or simplify tiny edges that may degrade mesh quality.",
        }
    ]


def check_thin_walls(geometry_summary: Any) -> list[dict[str, Any]]:
    max_dim = _max_dim(geometry_summary.bounding_box)
    min_dim = _min_nonzero_dim(geometry_summary.bounding_box)
    if max_dim <= 0 or min_dim <= 0:
        return []

    if (min_dim / max_dim) >= THIN_WALL_RATIO:
        return []

    return [
        {
            "check": "ThinWalls",
            "severity": "Major",
            "detail": f"Minimum model thickness ratio is approximately {min_dim / max_dim:.4f}.",
            "suggestion": "Inspect thin regions and confirm they are meshable for the intended solver.",
        }
    ]


def check_small_features(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    if TopExp_Explorer is None or brepgprop is None or GProp_GProps is None:
        return []

    max_dim = _max_dim(geometry_summary.bounding_box)
    if max_dim <= 0:
        return []

    face_threshold = (max_dim ** 2) * SMALL_FEATURE_RATIO
    edge_threshold = max_dim * SMALL_FEATURE_EDGE_RATIO
    small_faces = 0
    small_edges = 0

    if TopAbs_FACE is not None:
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
        while explorer.More():
            face = topods.Face(explorer.Current()) if topods is not None else explorer.Current()
            props = GProp_GProps()
            try:
                brepgprop.SurfaceProperties(face, props)
                area = props.Mass()
            except Exception:
                area = 0.0
            if 0 < area < face_threshold:
                small_faces += 1
            explorer.Next()

    if TopAbs_EDGE is not None:
        edge_explorer = TopExp_Explorer(shape, TopAbs_EDGE)
        while edge_explorer.More():
            edge = topods.Edge(edge_explorer.Current()) if topods is not None else edge_explorer.Current()
            length = _edge_length(edge)
            if DEGENERATE_EDGE_TOLERANCE < length < edge_threshold:
                small_edges += 1
            edge_explorer.Next()

    if not small_faces and not small_edges:
        return []

    return [
        {
            "check": "SmallFeatures",
            "severity": "Minor",
            "detail": f"Detected {small_faces} small faces and {small_edges} short local edges relative to part scale.",
            "suggestion": "Inspect tiny local features that may force unnecessary mesh refinement.",
        }
    ]


def check_small_fillets(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    if TopExp_Explorer is None or TopAbs_FACE is None or BRepAdaptor_Surface is None:
        return []

    max_dim = _max_dim(geometry_summary.bounding_box)
    if max_dim <= 0:
        return []
    radius_threshold = max_dim * SMALL_FILLET_RADIUS_RATIO

    small_cylinders = 0
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = topods.Face(explorer.Current()) if topods is not None else explorer.Current()
        try:
            surface = BRepAdaptor_Surface(face, True)
            cylinder = surface.Cylinder()
            radius = cylinder.Radius()
            if radius <= radius_threshold:
                small_cylinders += 1
        except Exception:
            pass
        explorer.Next()

    if not small_cylinders:
        return []

    return [
        {
            "check": "SmallFilletsOrHoles",
            "severity": "Minor",
            "detail": f"Detected {small_cylinders} cylindrical faces with radius below {radius_threshold:.6g}.",
            "suggestion": "Inspect small fillets or holes that may need defeaturing or local refinement.",
        }
    ]


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    severity_counts = {"Critical": 0, "Major": 0, "Minor": 0, "Info": 0}
    for finding in findings:
        severity = finding.get("severity", "Info")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    return {
        "total": len(findings),
        "by_severity": severity_counts,
        "major_checks": [f["check"] for f in findings if f.get("severity") == "Major"],
    }


def run_essential_checks(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    findings.extend(check_degenerate_geometry(shape, geometry_summary))
    findings.extend(check_non_manifold_edges(shape))
    findings.extend(check_open_boundaries(shape, geometry_summary))
    findings.extend(check_short_edges(shape, geometry_summary))
    findings.extend(check_thin_walls(geometry_summary))
    findings.extend(check_small_features(shape, geometry_summary))
    findings.extend(check_small_fillets(shape, geometry_summary))

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
