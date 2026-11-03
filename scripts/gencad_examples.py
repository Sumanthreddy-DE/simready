"""Render the three runnable walkthrough pairs and print measured geometry as JSON.

Run from the repo root in simready-fix:
    python scripts/gencad_examples.py
Reference STEPs must first be exported with gencad_export_reference_steps.py.
No scoring, alignment, healing or checker pass is performed here.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box

from gencad_common import CACHE, GENERATED_STEPS, MODEL_TAG, REPO, RESULTS

sys.path.insert(0, str(REPO))

from simready.copilot.png_render import _extract_triangles, _read_step, _save_png
from simready.occ_utils import iter_faces

INDICES = (400, 5699, 4836)
BASE_GREY = 0.78
AMBIENT = 0.30
# World-space light direction; shading uses |n . L| so triangle winding does not matter.
LIGHT = (0.35, 0.85, 0.40)
WIDTH, HEIGHT = 800, 600
MAX_BYTES = 150_000


def shaded_colors(triangles: list) -> list[tuple[float, float, float, float]]:
    """One grey per triangle, darker as its normal turns away from the light.

    Flat single-colour fills render only silhouettes (a tube looked like a capsule, its
    bore invisible); per-triangle Lambert shading keeps faces and holes readable.
    """
    norm = math.sqrt(sum(c * c for c in LIGHT))
    light = tuple(c / norm for c in LIGHT)
    colors = []
    for a, b, c in triangles:
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        lambert = abs(sum(n[i] / length * light[i] for i in range(3)))
        g = BASE_GREY * (AMBIENT + (1 - AMBIENT) * lambert)
        colors.append((g, g, g, 1.0))
    return colors


def render_step(idx: int, role: str, source: Path) -> dict:
    shape = _read_step(str(source))
    if shape is None:
        raise RuntimeError(f"Cannot read STEP: {source}")
    # Exact geometry bounds before tessellation; do not use cached mesh bounds.
    bbox = Bnd_Box()
    brepbndlib.AddOptimal(shape, bbox, False, False)
    bounds = bbox.Get()
    dimensions = [bounds[i + 3] - bounds[i] for i in range(3)]
    faces = sum(1 for _ in iter_faces(shape))
    triangles, _ = _extract_triangles(shape, {})
    target = RESULTS / "examples" / f"{idx}_{role}.png"
    result = _save_png(
        triangles, shaded_colors(triangles), target, width=WIDTH, height=HEIGHT
    )
    if result is None:
        raise RuntimeError(f"Cannot render STEP: {source}")
    size = target.stat().st_size
    if size > MAX_BYTES:
        raise RuntimeError(f"PNG exceeds {MAX_BYTES} bytes: {target} ({size})")
    return {
        "idx": idx, "role": role, "source": str(source.relative_to(REPO)),
        "bbox_xyz": dimensions, "face_count": faces,
        "triangles": len(triangles), "image": str(target.relative_to(REPO)),
        "width": WIDTH, "height": HEIGHT, "bytes": size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roles", nargs="+", choices=("reference", "generated"),
                        default=["reference", "generated"],
                        help="render only these roles (references need the exported STEPs)")
    roles = parser.parse_args().roles
    measurements = []
    for idx in INDICES:
        for role, source in (
            ("reference", CACHE / "reference_steps" / f"gt_{idx}.step"),
            ("generated", GENERATED_STEPS / f"{MODEL_TAG}_{idx}.step"),
        ):
            if role in roles:
                measurements.append(render_step(idx, role, source))
    print(json.dumps(measurements, indent=2))


if __name__ == "__main__":
    main()
