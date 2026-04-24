"""Geometry checks for SimReady with Phase 2 per-face scoring groundwork."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simready.occ_utils import build_edge_face_map, edge_length, uv_bounds

try:
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
except ImportError:  # pragma: no cover
    BRepAlgoAPI_Common = None

try:
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Copy
except ImportError:  # pragma: no cover
    BRepBuilderAPI_Copy = None

try:
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
except ImportError:  # pragma: no cover
    BRepExtrema_DistShapeShape = None

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
DEGENERATE_EDGE_TOLERANCE = 1e-7


@dataclass
class CheckResult:
    per_face: dict[int, float] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FaceRecord:
    index: int
    face: Any


def _result(findings: list[dict[str, Any]] | None = None, per_face: dict[int, float] | None = None) -> CheckResult:
    return CheckResult(per_face=per_face or {}, findings=findings or [])


def _merge_check_results(results: list[CheckResult]) -> CheckResult:
    merged_findings: list[dict[str, Any]] = []
    merged_per_face: dict[int, float] = {}
    for result in results:
        merged_findings.extend(result.findings)
        for face_index, score in result.per_face.items():
            merged_per_face[face_index] = max(merged_per_face.get(face_index, 0.0), float(score))
    return CheckResult(per_face=merged_per_face, findings=merged_findings)


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


def _iter_faces(shape: Any) -> list[FaceRecord]:
    if TopExp_Explorer is None or TopAbs_FACE is None:
        return []
    try:
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
    except Exception:
        return []
    faces: list[FaceRecord] = []
    index = 1
    while explorer.More():
        face = topods.Face(explorer.Current()) if topods is not None else explorer.Current()
        faces.append(FaceRecord(index=index, face=face))
        index += 1
        explorer.Next()
    return faces


def _iter_edges(shape: Any) -> list[Any]:
    if TopExp_Explorer is None or TopAbs_EDGE is None:
        return []
    try:
        explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    except Exception:
        return []
    edges: list[Any] = []
    while explorer.More():
        edges.append(topods.Edge(explorer.Current()) if topods is not None else explorer.Current())
        explorer.Next()
    return edges


def _edge_to_face_indices(shape: Any) -> dict[int, list[int]]:
    edge_face_map = build_edge_face_map(shape)
    if edge_face_map is None:
        return {}

    faces = _iter_faces(shape)
    face_lookup: dict[int, Any] = {record.index: record.face for record in faces}
    reverse_lookup = {id(face): index for index, face in face_lookup.items()}
    mapping: dict[int, list[int]] = {}
    for edge_idx in range(1, edge_face_map.Size() + 1):
        attached: list[int] = []
        face_list = edge_face_map.FindFromIndex(edge_idx)
        for pos in range(1, face_list.Size() + 1):
            try:
                face = face_list.Value(pos)
                face_index = reverse_lookup.get(id(face))
                if face_index is not None:
                    attached.append(face_index)
            except Exception:
                continue
        mapping[edge_idx] = attached
    return mapping


def _cylindrical_face_radii(shape: Any) -> dict[int, float]:
    if BRepAdaptor_Surface is None:
        return {}
    result: dict[int, float] = {}
    for record in _iter_faces(shape):
        try:
            surface = BRepAdaptor_Surface(record.face, True)
            cylinder = surface.Cylinder()
            result[record.index] = cylinder.Radius()
        except Exception:
            continue
    return result


def check_degenerate_geometry(shape: Any, geometry_summary: Any) -> CheckResult:
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

    zero_length_edges = 0
    for edge in _iter_edges(shape):
        if abs(edge_length(edge)) <= DEGENERATE_EDGE_TOLERANCE:
            zero_length_edges += 1

    if zero_length_edges:
        findings.append(
            {
                "check": "DegenerateEdges",
                "severity": "Major",
                "detail": f"Detected {zero_length_edges} zero-length or collapsed edges.",
                "suggestion": "Remove or repair collapsed topology before meshing.",
            }
        )

    return _result(findings=findings)


def check_non_manifold_edges(shape: Any) -> CheckResult:
    edge_face_map = build_edge_face_map(shape)
    if edge_face_map is None:
        return _result()

    bad_edges = 0
    per_face: dict[int, float] = {}
    attached_faces = _edge_to_face_indices(shape)
    for index in range(1, edge_face_map.Size() + 1):
        face_count = edge_face_map.FindFromIndex(index).Size()
        if face_count > 2:
            bad_edges += 1
            for face_index in attached_faces.get(index, []):
                per_face[face_index] = max(per_face.get(face_index, 0.0), 1.0)

    if not bad_edges:
        return _result()

    return _result(
        findings=[
            {
                "check": "NonManifoldEdges",
                "severity": "Major",
                "detail": f"Detected {bad_edges} non-manifold edges shared by more than two faces.",
                "suggestion": "Repair or simplify the topology before simulation.",
            }
        ],
        per_face=per_face,
    )


def check_open_boundaries(shape: Any, geometry_summary: Any | None = None) -> CheckResult:
    findings: list[dict[str, Any]] = []
    per_face: dict[int, float] = {}

    if geometry_summary is not None and geometry_summary.solid_count <= 0 and geometry_summary.face_count > 0:
        findings.append(
            {
                "check": "OpenBoundaries",
                "severity": "Major",
                "detail": "Geometry contains faces but no closed solid volume.",
                "suggestion": "Close the shell or export a watertight solid before simulation.",
            }
        )
        for record in _iter_faces(shape):
            per_face[record.index] = max(per_face.get(record.index, 0.0), 0.8)

    if BRep_Tool is None:
        return _result(findings=findings, per_face=per_face)

    edge_face_map = build_edge_face_map(shape)
    if edge_face_map is None:
        return _result(findings=findings, per_face=per_face)

    attached_faces = _edge_to_face_indices(shape)
    open_edges = 0
    degenerate_edges = 0
    for index in range(1, edge_face_map.Size() + 1):
        edge = edge_face_map.FindKey(index)
        face_count = edge_face_map.FindFromIndex(index).Size()
        if face_count == 1:
            open_edges += 1
            for face_index in attached_faces.get(index, []):
                per_face[face_index] = max(per_face.get(face_index, 0.0), 1.0)
        try:
            if BRep_Tool.Degenerated(edge):
                degenerate_edges += 1
                for face_index in attached_faces.get(index, []):
                    per_face[face_index] = max(per_face.get(face_index, 0.0), 0.9)
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
                for record in _iter_faces(shape):
                    per_face[record.index] = max(per_face.get(record.index, 0.0), 0.7)
        except Exception:
            pass

    return _result(findings=findings, per_face=per_face)


def check_short_edges(shape: Any, geometry_summary: Any) -> CheckResult:
    threshold = _short_edge_threshold(geometry_summary.bounding_box)
    if threshold <= 0:
        return _result()

    short_edges = 0
    per_face: dict[int, float] = {}
    edge_face_map = build_edge_face_map(shape)
    attached_faces = _edge_to_face_indices(shape) if edge_face_map is not None else {}

    for edge_index, edge in enumerate(_iter_edges(shape), start=1):
        length = edge_length(edge)
        if DEGENERATE_EDGE_TOLERANCE < length < threshold:
            short_edges += 1
            severity_score = min(1.0, max(0.1, 1.0 - (length / threshold)))
            for face_index in attached_faces.get(edge_index, []):
                per_face[face_index] = max(per_face.get(face_index, 0.0), severity_score)

    if not short_edges:
        return _result()

    severity = "Major" if short_edges >= 8 else "Minor"
    return _result(
        findings=[
            {
                "check": "ShortEdges",
                "severity": severity,
                "detail": f"Detected {short_edges} edges shorter than {threshold:.6g} model units.",
                "suggestion": "Merge or simplify tiny edges that may degrade mesh quality.",
            }
        ],
        per_face=per_face,
    )


def check_thin_walls(geometry_summary: Any) -> CheckResult:
    max_dim = _max_dim(geometry_summary.bounding_box)
    min_dim = _min_nonzero_dim(geometry_summary.bounding_box)
    if max_dim <= 0 or min_dim <= 0:
        return _result()

    ratio = min_dim / max_dim
    if ratio >= THIN_WALL_RATIO:
        return _result()

    score = min(1.0, max(0.1, 1.0 - (ratio / THIN_WALL_RATIO)))
    return _result(
        findings=[
            {
                "check": "ThinWalls",
                "severity": "Major",
                "detail": f"Minimum model thickness ratio is approximately {ratio:.4f}.",
                "suggestion": "Inspect thin regions and confirm they are meshable for the intended solver.",
            }
        ],
        per_face={0: score},
    )


def check_small_features(shape: Any, geometry_summary: Any) -> CheckResult:
    if brepgprop is None or GProp_GProps is None:
        return _result()

    max_dim = _max_dim(geometry_summary.bounding_box)
    if max_dim <= 0:
        return _result()

    face_threshold = (max_dim ** 2) * SMALL_FEATURE_RATIO
    edge_threshold = max_dim * SMALL_FEATURE_EDGE_RATIO
    small_faces = 0
    small_edges = 0
    per_face: dict[int, float] = {}

    for record in _iter_faces(shape):
        props = GProp_GProps()
        try:
            brepgprop.SurfaceProperties(record.face, props)
            area = props.Mass()
        except Exception:
            area = 0.0
        if 0 < area < face_threshold:
            small_faces += 1
            per_face[record.index] = max(per_face.get(record.index, 0.0), min(1.0, max(0.1, 1.0 - (area / face_threshold))))

    edge_face_map = build_edge_face_map(shape)
    attached_faces = _edge_to_face_indices(shape) if edge_face_map is not None else {}
    for edge_index, edge in enumerate(_iter_edges(shape), start=1):
        length = edge_length(edge)
        if DEGENERATE_EDGE_TOLERANCE < length < edge_threshold:
            small_edges += 1
            edge_score = min(1.0, max(0.1, 1.0 - (length / edge_threshold)))
            for face_index in attached_faces.get(edge_index, []):
                per_face[face_index] = max(per_face.get(face_index, 0.0), edge_score)

    if not small_faces and not small_edges:
        return _result()

    return _result(
        findings=[
            {
                "check": "SmallFeatures",
                "severity": "Minor",
                "detail": f"Detected {small_faces} small faces and {small_edges} short local edges relative to part scale.",
                "suggestion": "Inspect tiny local features that may force unnecessary mesh refinement.",
            }
        ],
        per_face=per_face,
    )


def check_small_fillets(shape: Any, geometry_summary: Any) -> CheckResult:
    max_dim = _max_dim(geometry_summary.bounding_box)
    if max_dim <= 0:
        return _result()

    radius_threshold = max_dim * SMALL_CYLINDER_RADIUS_RATIO
    radii = _cylindrical_face_radii(shape)
    per_face: dict[int, float] = {}
    flagged = 0
    for face_index, radius in radii.items():
        if radius <= radius_threshold:
            flagged += 1
            per_face[face_index] = min(1.0, max(0.1, 1.0 - (radius / radius_threshold if radius_threshold else 0.0)))

    if not flagged:
        return _result()

    return _result(
        findings=[
            {
                "check": "SmallFilletsOrHoles",
                "severity": "Minor",
                "detail": f"Detected {flagged} cylindrical faces with radius below {radius_threshold:.6g}.",
                "suggestion": "Inspect small fillets or holes that may need defeaturing or local refinement.",
            }
        ],
        per_face=per_face,
    )


def check_duplicate_body_heuristic(shape: Any, geometry_summary: Any) -> CheckResult:
    if geometry_summary.solid_count <= 1:
        return _result()

    try:
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
        from OCC.Core.TopAbs import TopAbs_SOLID
    except ImportError:  # pragma: no cover
        return _result()

    if TopExp_Explorer is None:
        return _result()

    signatures: list[tuple[float, float, float, float, float, float]] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = explorer.Current()
        box = Bnd_Box()
        brepbndlib.Add(solid, box)
        signatures.append(tuple(round(v, 5) for v in box.Get()))
        explorer.Next()

    duplicates = len(signatures) - len(set(signatures))
    if duplicates <= 0:
        return _result()

    return _result(
        findings=[
            {
                "check": "DuplicateBodyHeuristic",
                "severity": "Major",
                "detail": f"Detected {duplicates} body-level duplicate bounding-box signatures.",
                "suggestion": "Inspect for overlapping or duplicate solids before simulation.",
            }
        ],
        per_face={0: min(1.0, 0.5 + duplicates * 0.25)},
    )


def check_duplicate_face_heuristic(shape: Any, geometry_summary: Any) -> CheckResult:
    if geometry_summary.face_count <= 1:
        return _result()

    signatures: dict[tuple[float, float, float, float, float, float], list[int]] = {}
    try:
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib
    except ImportError:  # pragma: no cover
        return _result()

    for record in _iter_faces(shape):
        box = Bnd_Box()
        brepbndlib.Add(record.face, box)
        signature = tuple(round(v, 5) for v in box.Get())
        signatures.setdefault(signature, []).append(record.index)

    duplicates = sum(len(indices) - 1 for indices in signatures.values() if len(indices) > 1)
    if duplicates <= 0:
        return _result()

    per_face: dict[int, float] = {}
    for indices in signatures.values():
        if len(indices) > 1:
            for face_index in indices:
                per_face[face_index] = max(per_face.get(face_index, 0.0), 0.8)

    severity = "Major" if geometry_summary.solid_count <= 0 else "Minor"
    return _result(
        findings=[
            {
                "check": "DuplicateFaceHeuristic",
                "severity": severity,
                "detail": f"Detected {duplicates} duplicate face-level bounding-box signatures.",
                "suggestion": "Inspect for coincident or overlapping faces before meshing.",
            }
        ],
        per_face=per_face,
    )


def check_orientation_nuance(shape: Any, geometry_summary: Any) -> CheckResult:
    if geometry_summary.solid_count > 0 or geometry_summary.face_count <= 0:
        return _result()

    per_face = {record.index: 0.4 for record in _iter_faces(shape)}
    return _result(
        findings=[
            {
                "check": "OrientationNuance",
                "severity": "Minor",
                "detail": "Face-based geometry without a closed solid may contain orientation inconsistencies.",
                "suggestion": "Inspect shell orientation and face normals before meshing.",
            }
        ],
        per_face=per_face,
    )


def check_sharp_edges(shape: Any, threshold_degrees: float = 15.0) -> CheckResult:
    if BRepAdaptor_Surface is None:
        return _result()

    findings: list[dict[str, Any]] = []
    per_face: dict[int, float] = {}
    faces = {record.index: record.face for record in _iter_faces(shape)}
    attached_faces = _edge_to_face_indices(shape)
    sharp_edges = 0

    for edge_index, face_indices in attached_faces.items():
        if len(face_indices) != 2:
            continue
        try:
            normal_a = _face_normal_for_check(faces[face_indices[0]])
            normal_b = _face_normal_for_check(faces[face_indices[1]])
            angle = _angle_between_normals(normal_a, normal_b)
        except Exception:
            continue
        if angle is None:
            continue
        if angle < threshold_degrees:
            sharp_edges += 1
            severity_score = min(1.0, max(0.3, 1.0 - (angle / threshold_degrees)))
            for face_index in face_indices:
                per_face[face_index] = max(per_face.get(face_index, 0.0), severity_score)

    if sharp_edges:
        findings.append(
            {
                "check": "SharpEdges",
                "severity": "Minor",
                "detail": f"Detected {sharp_edges} adjacent edge pairs with dihedral angle below {threshold_degrees:.1f} degrees.",
                "suggestion": "Inspect sharp transitions and confirm they are intentional for meshing and stress concentration.",
            }
        )

    return _result(findings=findings, per_face=per_face)


def _face_normal_for_check(face: Any) -> tuple[float, float, float] | None:
    try:
        from OCC.Core.GeomLProp import GeomLProp_SLProps
    except ImportError:  # pragma: no cover
        return None

    surface = BRepAdaptor_Surface(face, True)
    umin, umax, vmin, vmax = uv_bounds(face)
    props = GeomLProp_SLProps(surface.Surface().Surface(), (umin + umax) / 2.0, (vmin + vmax) / 2.0, 1, 1e-6)
    if not props.IsNormalDefined():
        return None
    normal = props.Normal()
    return (float(normal.X()), float(normal.Y()), float(normal.Z()))


def _angle_between_normals(a: tuple[float, float, float] | None, b: tuple[float, float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    import math

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return None
    cosine = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
    return math.degrees(math.acos(cosine))


def check_self_intersection(shape: Any) -> CheckResult:
    if BRepBuilderAPI_Copy is None or BRepAlgoAPI_Common is None:
        return _result()

    try:
        copier = BRepBuilderAPI_Copy(shape)
        copier.Perform(shape)
        copied = copier.Shape()
        common = BRepAlgoAPI_Common(shape, copied)
        common.Build()
        if common.IsDone() and not common.Shape().IsNull():
            return _result(
                findings=[
                    {
                        "check": "SelfIntersection",
                        "severity": "Major",
                        "detail": "Boolean self-overlap check returned intersecting geometry.",
                        "suggestion": "Inspect for self-intersecting or duplicated overlapping topology before meshing.",
                    }
                ],
                per_face={record.index: 0.9 for record in _iter_faces(shape)},
            )
    except Exception:
        return _result()

    return _result()


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


def run_essential_checks_detailed(shape: Any, geometry_summary: Any) -> CheckResult:
    check_calls = [
        (check_degenerate_geometry, (shape, geometry_summary)),
        (check_non_manifold_edges, (shape,)),
        (check_open_boundaries, (shape, geometry_summary)),
        (check_short_edges, (shape, geometry_summary)),
        (check_thin_walls, (geometry_summary,)),
        (check_small_features, (shape, geometry_summary)),
        (check_small_fillets, (shape, geometry_summary)),
        (check_duplicate_body_heuristic, (shape, geometry_summary)),
        (check_duplicate_face_heuristic, (shape, geometry_summary)),
        (check_orientation_nuance, (shape, geometry_summary)),
        (check_sharp_edges, (shape,)),
        (check_self_intersection, (shape,)),
    ]
    results: list[CheckResult] = []
    for check_fn, args in check_calls:
        try:
            results.append(check_fn(*args))
        except Exception:
            results.append(
                _result(
                    findings=[
                        {
                            "check": check_fn.__name__,
                            "severity": "Info",
                            "detail": "Check skipped due to internal error on this geometry.",
                            "suggestion": "This check could not be completed. Manual review recommended.",
                        }
                    ]
                )
            )
    merged = _merge_check_results(results)

    if geometry_summary.solid_count > 1:
        merged.findings.append(
            {
                "check": "MultiBodyDetected",
                "severity": "Info",
                "detail": f"Detected {geometry_summary.solid_count} solids.",
                "suggestion": "Split and analyze bodies individually in a later phase.",
            }
        )

    return merged


def run_essential_checks(shape: Any, geometry_summary: Any) -> list[dict[str, Any]]:
    return run_essential_checks_detailed(shape, geometry_summary).findings
