"""Geometry checks for SimReady Phase 1."""

from __future__ import annotations

from typing import Any

from simready.occ_utils import build_edge_face_map, edge_length

try:
    from OCC.Core.BRep import BRep_Tool
except ImportError:  # pragma: no cover
    BRep_Tool = None

try:
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
except ImportError:  # pragma: no cover
    BRepAdaptor_Surface = None

try:
    from OCC.Core.ShapeAnalysis import ShapeAnalysis_Shell
except ImportError:  # pragma: no cover
    ShapeAnalysis_Shell = None

try:
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
except ImportError:  # pragma: no cover
    TopAbs_EDGE = None
    TopAbs_FACE = None

try:
    from OCC.Core.TopExp import TopExp_Explorer
except ImportError:  # pragma: no cover
    TopExp_Explorer = None

try:
    from OCC.Core.TopoDS import topods
except ImportError:  # pragma: no cover
    topods = None

try:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
except ImportError:  # pragma: no cover
    brepgprop = None
    GProp_GProps = None


SHORT_EDGE_RATIO = 0.005
THIN_WALL_RATIO = 0.03
SMALL_FEATURE_RATIO = 0.02
SMALL_FEATURE_EDGE_RATIO = 0.2
SMALL_CYLINDER_RADIUS_RATIO = 0.03
DUPLICATE_BODY_BBOX_EPS = 1e-5
DUPLICATE_FACE_BBOX_EPS = 1e-5
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


def _cylindrical_radii(shape: Any) -> list[float]:
    if TopExp_Explorer is None or TopAbs_FACE is None or BRepAdaptor_Surface is None:
        return []

    radii: list[float] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = explorer.Current()
        try:
            surface = BRepAdaptor_Surface(face, True)
            cylinder = surface.Cylinder()
            radii.append(cylinder.Radius())
        except Exception:
            pass
        explorer.Next()
    return radii


def _body_bbox_signatures(shape: Any) -> list[tuple[float, float, float, float, float, float]]:
    if TopExp_Explorer is None:
        return []

    try:
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.TopAbs import TopAbs_SOLID
    except ImportError:  # pragma: no cover
        return []

    signatures: list[tuple[float, float, float, float, float, float]] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = explorer.Current()
        box = Bnd_Box()
        brepbndlib.Add(solid, box)
        bounds = box.Get()
        signatures.append(tuple(round(v, 5) for v in bounds))
        explorer.Next()
    return signatures


def _face_bbox_signatures(shape: Any) -> list[tuple[float, float, float, float, float, float]]:
    if TopExp_Explorer is None or TopAbs_FACE is None:
        return []

    try:
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
    except ImportError:  # pragma: no cover
        return []

    signatures: list[tuple[float, float, float, float, float, float]] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = explorer.Current()
        box = Bnd_Box()
        brepbndlib.Add(face, box)
        bounds = box.Get()
        signatures.append(tuple(round(v, 5) for v in bounds))
        explorer.Next()
    return signatures


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

    if TopExp_Explorer is None or TopAbs_EDGE is None:
        return findings

    zero_length_edges = 0
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edge = topods.Edge(explorer.Current()) if topods is not None else explorer.Current()
        if abs(edge_length(edge)) <= DEGENERATE_EDGE_TOLERANCE:
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
    edge_face_map = build_edge_face_map(shape)
    if edge_face_map is None:
        return []

    bad_edges = 0
    for index in range(1, edge_face_map.Size() + 1):
        if edge_face_map.FindFromIndex(index).Size() > 2:
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

    if BRep_Tool is None:
        return findings

    edge_face_map = build_edge_face_map(shape)
    if edge_face_map is None:
        return findings

    open_edges = 0
    degenerate_edges = 0
    for index in range(1, edge_face_map.Size() + 1):
        edge = edge_face_map.FindKey(index)
        attached_faces = edge_face_map.FindFromIndex(index).Size()
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
    try:
        explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    except Exception:
        return []
    while explorer.More():
        edge = topods.Edge(explorer.Current()) if topods is not None else explorer.Current()
        length = edge_length(edge)
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
            length = edge_length(edge)
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
    max_dim = _max_dim(geometry_summary.bounding_box)
    if max_dim <= 0:
        return []

    radius_threshold = max_dim * SMALL_CYLINDER_RADIUS_RATIO
    radii = [radius for radius in _cylindrical_radii(shape) if radius <= radius_threshold]
    if not radii:
        return []

    return [
        {
            "check": "SmallFilletsOrHoles",
            "severity": "Minor",
            "detail": f"Detected {len(radii)} cylindrical faces with radius below {radius_threshold:.6g}.",
            "suggestion": "Inspect small fillets or holes that may need defeaturing or local refinement.",
        }
    ]


def check_duplicate_body_heuristic(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    if geometry_summary.solid_count <= 1:
        return []

    signatures = _body_bbox_signatures(shape)
    if len(signatures) <= 1:
        return []

    duplicates = len(signatures) - len(set(signatures))
    if duplicates <= 0:
        return []

    return [
        {
            "check": "DuplicateBodyHeuristic",
            "severity": "Major",
            "detail": f"Detected {duplicates} body-level duplicate bounding-box signatures.",
            "suggestion": "Inspect for overlapping or duplicate solids before simulation.",
        }
    ]


def check_duplicate_face_heuristic(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    if geometry_summary.face_count <= 1:
        return []

    signatures = _face_bbox_signatures(shape)
    if len(signatures) <= 1:
        return []

    duplicates = len(signatures) - len(set(signatures))
    if duplicates <= 0:
        return []

    severity = "Major" if geometry_summary.solid_count <= 0 else "Minor"
    return [
        {
            "check": "DuplicateFaceHeuristic",
            "severity": severity,
            "detail": f"Detected {duplicates} duplicate face-level bounding-box signatures.",
            "suggestion": "Inspect for coincident or overlapping faces before meshing.",
        }
    ]


def check_orientation_nuance(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    if geometry_summary.solid_count > 0:
        return []
    if geometry_summary.face_count <= 0:
        return []

    return [
        {
            "check": "OrientationNuance",
            "severity": "Minor",
            "detail": "Face-based geometry without a closed solid may contain orientation inconsistencies.",
            "suggestion": "Inspect shell orientation and face normals before meshing.",
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
    findings.extend(check_duplicate_body_heuristic(shape, geometry_summary))
    findings.extend(check_duplicate_face_heuristic(shape, geometry_summary))
    findings.extend(check_orientation_nuance(shape, geometry_summary))

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
