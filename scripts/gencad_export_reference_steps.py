"""Export the reference (ground-truth) solids as STEP, for the rows the tuned model got valid.

Same cadquery + trimesh Python as gencad_iou_filled.py:
    .venv-gencad/Scripts/python scripts/gencad_export_reference_steps.py
Writes data/gencad/reference_steps/gt_<idx>.step (gitignored; regenerate any time).
"""
from __future__ import annotations

import cadquery as cq

from gencad_common import CACHE, load_reference, load_scores
from gencad_iou_filled import load_mecagent_metric


def main() -> None:
    M = load_mecagent_metric()
    out = CACHE / "reference_steps"
    out.mkdir(parents=True, exist_ok=True)
    ref = load_reference()
    valid = [i for i, s in load_scores().items() if s["valid"]]
    for i in sorted(valid):
        cq.exporters.export(M._load_solid_from_code(ref[i]["code"]), str(out / f"gt_{i}.step"))
    print("exported", len(list(out.glob("gt_*.step"))), "->", out)


if __name__ == "__main__":
    main()
