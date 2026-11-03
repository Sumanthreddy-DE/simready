"""Export the reference (ground-truth) solids as STEP, for the rows the tuned model got valid.

Same cadquery + trimesh Python as gencad_iou_filled.py:
    .venv-gencad/Scripts/python scripts/gencad_export_reference_steps.py
Writes data/gencad/reference_steps/gt_<idx>.step (gitignored; regenerate any time).
"""
from __future__ import annotations

import argparse

import cadquery as cq

from gencad_common import CACHE, load_reference, load_scores
from gencad_iou_filled import load_mecagent_metric


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idx", type=int, nargs="+", help="export only these valid row indices")
    args = parser.parse_args()
    valid = {i for i, s in load_scores().items() if s["valid"]}
    selected = valid if args.idx is None else set(args.idx)
    if selected - valid:
        parser.error(f"rows are missing or invalid: {sorted(selected - valid)}")
    M = load_mecagent_metric()
    out = CACHE / "reference_steps"
    out.mkdir(parents=True, exist_ok=True)
    ref = load_reference()
    for i in sorted(selected):
        cq.exporters.export(M._load_solid_from_code(ref[i]["code"]), str(out / f"gt_{i}.step"))
    print("exported", len(selected), "->", out)


if __name__ == "__main__":
    main()
