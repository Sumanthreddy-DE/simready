"""Re-score generations with MecAgent's IoU twice: unchanged (surface voxels) and filled voxels.

MecAgent's best_iou.py voxelizes with `mesh.voxelized(pitch)`, which in trimesh is a surface
voxelization. The filled variant is identical except `.fill()` on both grids.

Needs a Python with cadquery + trimesh (not the sr env), e.g. a throwaway venv:
    python -m venv .venv-gencad && .venv-gencad/Scripts/python -m pip install cadquery trimesh scipy
    .venv-gencad/Scripts/python scripts/gencad_iou_filled.py [--limit N]
Writes docs/validation/gencad/iou_shell_vs_filled.json.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics as st
import urllib.request

import numpy as np
import trimesh

from gencad_common import (MECAGENT_METRIC, MECAGENT_METRIC_URL, RESULTS, load_generations,
                           load_reference, load_scores)


def load_mecagent_metric():
    if not MECAGENT_METRIC.exists():
        MECAGENT_METRIC.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MECAGENT_METRIC_URL, MECAGENT_METRIC)
    spec = importlib.util.spec_from_file_location("best_iou", MECAGENT_METRIC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def iou_best_filled(M, mesh_gt, mesh_pred, pitch: float = 0.05) -> float:
    """MecAgent's iou_best with filled voxel grids; everything else unchanged."""
    axes_gt, axes_pr = M._principal_axes(mesh_gt), M._principal_axes(mesh_pred)
    best = 0.0
    original = trimesh.Trimesh.voxelized
    trimesh.Trimesh.voxelized = lambda self, p, **k: original(self, p, **k).fill()
    try:
        for signs in [(1, 1, 1), (1, 1, -1), (1, -1, 1), (-1, 1, 1)]:
            rot = axes_gt @ (axes_pr @ np.diag(signs)).T
            a, b = M._voxel_bool_unified(mesh_gt, M._apply_rotation(mesh_pred, rot), pitch)
            union = np.logical_or(a, b).sum()
            if union:
                best = max(best, np.logical_and(a, b).sum() / union)
    finally:
        trimesh.Trimesh.voxelized = original
    return float(best)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="score only the first N rows (smoke test)")
    args = ap.parse_args()
    M = load_mecagent_metric()

    cube = trimesh.creation.box((1, 1, 1)).voxelized(0.05)
    print("1x1x1 cube at pitch 0.05: voxelized() =", int(cube.matrix.sum()),
          "| filled =", int(cube.copy().fill().matrix.sum()))

    ref, gen, colab = load_reference(), load_generations(), load_scores()
    out, max_diff = [], 0.0
    for i in sorted(colab)[: args.limit]:
        if not colab[i]["valid"]:
            out.append({"idx": i, "valid": False, "shell": 0.0, "filled": 0.0})
            continue
        g = M._normalized_mesh(M._load_solid_from_code(ref[i]["code"]))
        p = M._normalized_mesh(M._load_solid_from_code(gen[i]["code"]))
        shell = float(M.iou_best(g, p))
        max_diff = max(max_diff, abs(shell - colab[i]["iou"]))
        out.append({"idx": i, "valid": True, "shell": shell, "filled": iou_best_filled(M, g, p)})

    valid = [r for r in out if r["valid"]]
    print(f"max |local shell - Colab score| over {len(valid)} valid rows: {max_diff:.2e}")
    for k in ("shell", "filled"):
        xs = [r[k] for r in valid]
        print(f"{k:6}: mean {st.mean(xs):.3f} median {st.median(xs):.3f} "
              f"<0.1: {sum(x < 0.1 for x in xs)}  >=0.5: {sum(x >= 0.5 for x in xs)}  "
              f">=0.8: {sum(x >= 0.8 for x in xs)}  mean over all (invalid=0): {sum(xs) / len(out):.3f}")
    if args.limit is None:
        dst = RESULTS / "iou_shell_vs_filled.json"
        dst.write_text(json.dumps(out, indent=0), encoding="utf-8")
        print("wrote", dst)


if __name__ == "__main__":
    main()
