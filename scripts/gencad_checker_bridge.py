"""Checker bridge: score GenCAD parts with SimReady's own checker (analyze_file_safe).

GenCAD parts are normalized to about 1.5 units across, while the checker's thresholds are in
millimetres, so each part is first scaled so its largest bounding-box side is 100 mm.
Resumable: re-running skips parts already in the output file.

Run in the sr env (pythonocc), ~50 s per part:
    C:/mm/sr/python.exe scripts/gencad_checker_bridge.py generated
    C:/mm/sr/python.exe scripts/gencad_checker_bridge.py reference   # after gencad_export_reference_steps.py
Writes docs/validation/gencad/checker_<which>.jsonl.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from gencad_common import CACHE, GENERATED_STEPS, MODEL_TAG, REPO, RESULTS

sys.path.insert(0, str(REPO))

TARGET_MM = 100.0
SOURCES = {
    "generated": (GENERATED_STEPS, f"{MODEL_TAG}_*.step"),
    "reference": (CACHE / "reference_steps", "gt_*.step"),
}


def scale_step(src: Path, dst: Path) -> tuple[float, list[float]]:
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.gp import gp_Pnt, gp_Trsf
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer

    reader = STEPControl_Reader()
    assert reader.ReadFile(str(src)) == IFSelect_RetDone, f"read failed: {src}"
    reader.TransferRoots()
    shape = reader.OneShape()
    box = Bnd_Box()
    brepbndlib.Add(shape, box)
    x0, y0, z0, x1, y1, z1 = box.Get()
    dims = [x1 - x0, y1 - y0, z1 - z0]
    factor = TARGET_MM / max(dims)
    trsf = gp_Trsf()
    trsf.SetScale(gp_Pnt(0, 0, 0), factor)
    writer = STEPControl_Writer()
    writer.Transfer(BRepBuilderAPI_Transform(shape, trsf, True).Shape(), STEPControl_AsIs)
    assert writer.Write(str(dst)) == IFSelect_RetDone, f"write failed: {dst}"
    return factor, [round(d * factor, 3) for d in dims]


def main() -> None:
    from simready.pipeline import analyze_file_safe

    which = sys.argv[1] if len(sys.argv) > 1 else "generated"
    src_dir, pattern = SOURCES[which]
    scaled_dir = CACHE / f"scaled_{which}_steps"
    scaled_dir.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"checker_{which}.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(l)["idx"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}
    files = sorted(src_dir.glob(pattern), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    for n, src in enumerate(files, 1):
        idx = int(src.stem.rsplit("_", 1)[1])
        if idx in done:
            continue
        rec: dict = {"idx": idx}
        try:
            dst = scaled_dir / src.name
            rec["scale_factor"], rec["dims_mm"] = scale_step(src, dst)
            r = analyze_file_safe(str(dst), timeout=180)
            score = r.get("score") or {}
            rec.update(status=r.get("status"), overall=score.get("overall"), label=score.get("label"),
                       rule_face_mean=score.get("rule_face_mean"),
                       complexity=(r.get("complexity") or {}).get("tier"),
                       face_count=(r.get("graph") or {}).get("face_count"),
                       findings=[(f.get("check"), f.get("severity")) for f in (r.get("findings") or [])],
                       validation=r.get("validation"))
        except Exception as exc:  # record and keep going
            rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        print(f"[{n}/{len(files)}] idx {idx} {rec.get('status')} {rec.get('overall')} {rec.get('error', '')}",
              flush=True)


if __name__ == "__main__":
    main()
