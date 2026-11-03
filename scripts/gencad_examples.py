"""Render the three runnable walkthrough pairs and print measured geometry as JSON.

Run from the repo root in simready-fix:
    python scripts/gencad_examples.py
Reference STEPs must first be exported with gencad_export_reference_steps.py.
No scoring, alignment, healing or checker pass is performed here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box

from gencad_common import CACHE, GENERATED_STEPS, MODEL_TAG, REPO, RESULTS

sys.path.insert(0, str(REPO))

from simready.copilot.png_render import _extract_triangles, _read_step, _save_png
from simready.occ_utils import iter_faces

INDICES = (400, 5699, 4836)
GREY = (0.6, 0.6, 0.6, 1.0)
WIDTH, HEIGHT = 800, 600
MAX_BYTES = 150_000


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
        triangles, [GREY] * len(triangles), target, width=WIDTH, height=HEIGHT
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
    measurements = []
    for idx in INDICES:
        for role, source in (
            ("reference", CACHE / "reference_steps" / f"gt_{idx}.step"),
            ("generated", GENERATED_STEPS / f"{MODEL_TAG}_{idx}.step"),
        ):
            measurements.append(render_step(idx, role, source))
    print(json.dumps(measurements, indent=2))


if __name__ == "__main__":
    main()
