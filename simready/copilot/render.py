"""Static colored-face PNG renderer for the Copilot UI (Day-11 option C).

Tessellates a STEP file via OCC + BRepMesh_IncrementalMesh, then renders each
triangle as a PIL polygon using painter's-algorithm depth sorting and a fixed
isometric projection. Each face is colored by its combined-per-face score
(green/amber/red).

PIL was chosen over matplotlib because the sr conda env's matplotlib build
crashes on import-then-save under the same DLL space as pythonocc 7.9 on
Windows. PIL is already in the env, has no clash, and the painter's-algorithm
draw is adequate for a static "face-score" thumbnail.

No interactive 3D — just a static PNG embedded in the chat tool result.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from simready.occ_utils import iter_faces

logger = logging.getLogger(__name__)

try:
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.TopLoc import TopLoc_Location
    _OCC_OK = True
except ImportError:  # pragma: no cover
    _OCC_OK = False


# Match ui/viz.py face_score_color thresholds so PNG matches future overlay UI.
_RED = (0.937, 0.267, 0.267, 1.0)     # #ef4444
_AMBER = (0.961, 0.620, 0.043, 1.0)   # #f59e0b
_GREEN = (0.133, 0.773, 0.369, 1.0)   # #22c55e


def color_for_score(score: float) -> tuple[float, float, float, float]:
    if score >= 0.75:
        return _RED
    if score >= 0.4:
        return _AMBER
    return _GREEN


def _read_step(path: str) -> Any | None:
    if not _OCC_OK:
        return None
    reader = STEPControl_Reader()
    if reader.ReadFile(path) != IFSelect_RetDone:
        return None
    reader.TransferRoots()
    shape = reader.OneShape()
    return None if shape.IsNull() else shape


def _bbox_diagonal(shape: Any) -> float:
    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return ((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2) ** 0.5


def _extract_triangles(
    shape: Any, per_face_scores: dict[Any, float]
) -> tuple[list[list[tuple[float, float, float]]], list[tuple[float, float, float, float]]]:
    """Return (tris, facecolors) lists in parallel order for Poly3DCollection."""
    diag = _bbox_diagonal(shape) or 1.0
    deflection = max(diag * 0.005, 0.05)
    BRepMesh_IncrementalMesh(shape, deflection, False, 0.5, True)

    tris: list[list[tuple[float, float, float]]] = []
    colors: list[tuple[float, float, float, float]] = []

    for face_index, face in iter_faces(shape):
        loc = TopLoc_Location()
        try:
            tri = BRep_Tool.Triangulation(face, loc)
        except Exception:
            continue
        if tri is None:
            continue
        trsf = loc.Transformation()
        n_nodes = tri.NbNodes()
        if n_nodes < 3:
            continue
        nodes: list[tuple[float, float, float]] = []
        for j in range(1, n_nodes + 1):
            pnt = tri.Node(j).Transformed(trsf)
            nodes.append((pnt.X(), pnt.Y(), pnt.Z()))

        score = float(
            per_face_scores.get(face_index, per_face_scores.get(str(face_index), 0.0))
        )
        color = color_for_score(score)

        for k in range(1, tri.NbTriangles() + 1):
            n1, n2, n3 = tri.Triangle(k).Get()
            tris.append([nodes[n1 - 1], nodes[n2 - 1], nodes[n3 - 1]])
            colors.append(color)

    return tris, colors


def _project_isometric(
    p: tuple[float, float, float],
    *,
    alpha: float = 0.5236,  # 30 deg, elevation
    beta: float = 0.5236,   # 30 deg, azimuth
) -> tuple[float, float, float]:
    """Project a 3D point to (screen_x, screen_y, depth) via fixed isometric view."""
    import math
    x, y, z = p
    cb, sb = math.cos(beta), math.sin(beta)
    ca, sa = math.cos(alpha), math.sin(alpha)
    # Yaw around Y, then pitch around X.
    x1 = x * cb - z * sb
    z1 = x * sb + z * cb
    y1 = y * ca + z1 * sa
    depth = -y * sa + z1 * ca
    return (x1, y1, depth)


def _save_png(
    tris: list[list[tuple[float, float, float]]],
    colors: list[tuple[float, float, float, float]],
    out_path: Path,
    *,
    width: int,
    height: int,
) -> Path | None:
    """PIL painter's-algorithm draw step. Unit-testable without OCC.

    Each triangle is projected via :func:`_project_isometric`, sorted by depth
    (far -> near), and filled with its RGB color. Output is a flat-shaded PNG
    on a white background.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    if not tris:
        return None

    projected: list[list[tuple[float, float]]] = []
    depths: list[float] = []
    for tri in tris:
        pp = [_project_isometric(p) for p in tri]
        projected.append([(p[0], p[1]) for p in pp])
        depths.append(sum(p[2] for p in pp) / 3.0)

    flat_xs = [x for poly in projected for (x, _) in poly]
    flat_ys = [y for poly in projected for (_, y) in poly]
    minx, maxx = min(flat_xs), max(flat_xs)
    miny, maxy = min(flat_ys), max(flat_ys)
    sx = (maxx - minx) or 1.0
    sy = (maxy - miny) or 1.0
    margin = 0.06
    inner_w = width * (1.0 - 2 * margin)
    inner_h = height * (1.0 - 2 * margin)
    scale = min(inner_w / sx, inner_h / sy)
    off_x = (width - sx * scale) / 2.0
    off_y = (height - sy * scale) / 2.0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Painter's algorithm: deepest first (background), nearest last (foreground).
    order = sorted(range(len(tris)), key=lambda i: depths[i])
    for i in order:
        poly_xy: list[tuple[float, float]] = []
        for (x, y) in projected[i]:
            px = (x - minx) * scale + off_x
            # Flip Y so model +Y goes up in the image.
            py = height - ((y - miny) * scale + off_y)
            poly_xy.append((px, py))
        rgb = tuple(int(max(0.0, min(1.0, c)) * 255) for c in colors[i][:3])
        # No per-triangle outline — outlines would expose the BRepMesh
        # fan-triangulation pattern across planar faces (noisy). A
        # boundary-aware silhouette would need topology-level edge extraction;
        # deferred.
        draw.polygon(poly_xy, fill=rgb)

    img.save(out_path, format="PNG")
    return out_path


def render_face_score_png(
    step_path: str,
    per_face_scores: dict[Any, float] | None,
    out_dir: Path,
    *,
    width: int = 800,
    height: int = 600,
) -> Path | None:
    """Render `step_path` as a 3D PNG colored per-face by combined score.

    Returns the PNG path on success, ``None`` if OCC / matplotlib missing or
    the geometry produces no tessellation. All failures are logged and
    swallowed so a render miss never fails an analyze_geometry tool call.
    """
    if not _OCC_OK:
        return None
    try:
        shape = _read_step(step_path)
        if shape is None:
            return None
        tris, colors = _extract_triangles(shape, per_face_scores or {})
        if not tris:
            return None
        stem = Path(step_path).stem
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        out_path = out_dir / f"{stem}_{ts}.png"
        return _save_png(tris, colors, out_path, width=width, height=height)
    except Exception as exc:  # pragma: no cover — keep render strictly best-effort
        logger.warning("render_face_score_png failed for %s: %s", step_path, exc)
        return None
