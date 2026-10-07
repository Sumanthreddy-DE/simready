"""Failure and complexity analysis of the tuned model's 100 generations (stdlib only).

    python scripts/gencad_analyse.py
Needs data/gencad/gt_hundred.json (scripts/gencad_reference.py).
Writes docs/validation/gencad/per_row_analysis.json.
"""
from __future__ import annotations

import json
import re
import statistics as st

from gencad_common import RESULTS, load_generations, load_reference, load_scores


def n_sketches(code: str) -> int:
    return len(re.findall(r"^wp_sketch\d+\s*=", code, re.M))


def features(code: str) -> dict[str, bool]:
    return {"arc": "Arc" in code, "circle": ".circle(" in code, "cut": ".cut(" in code,
            "union": ".union(" in code}


def main() -> None:
    ref, scores, gen = load_reference(), load_scores(), load_generations()
    assert len(ref) == len(scores) == len(gen) == 100
    rows = []
    for i, g in ref.items():
        s, pred = scores[i], gen[i]["code"]
        rows.append(dict(idx=i, valid=s["valid"], iou=s["iou"], err=s["err"],
                         gt_sketches=n_sketches(g["code"]), pred_sketches=n_sketches(pred),
                         gt_chars=len(g["code"]), pred_chars=len(pred),
                         **{"gt_" + k: v for k, v in features(g["code"]).items()}))

    print("== failures")
    for r in rows:
        if not r["valid"]:
            print(f"idx {r['idx']:5} sketches ref {r['gt_sketches']} pred {r['pred_sketches']} | "
                  f"chars ref {r['gt_chars']} pred {r['pred_chars']} | {r['err'][:80]}")
    valid = [r for r in rows if r["valid"]]
    ious = [r["iou"] for r in valid]
    print(f"\n== IoU (MecAgent metric) over {len(valid)} valid: mean {st.mean(ious):.3f} "
          f"median {st.median(ious):.3f}")
    print("\n== by reference sketch count")
    for k in sorted({r["gt_sketches"] for r in rows}):
        grp = [r for r in rows if r["gt_sketches"] == k]
        ok = [r["iou"] for r in grp if r["valid"]] or [0.0]
        print(f"  {k}: n={len(grp):3}  VSR {sum(r['valid'] for r in grp) / len(grp):.2f}  "
              f"mean IoU(valid) {st.mean(ok):.3f}  "
              f"sketch count matches {sum(r['pred_sketches'] == r['gt_sketches'] for r in grp)}/{len(grp)}")
    out = RESULTS / "per_row_analysis.json"
    out.write_text(json.dumps(rows, indent=0), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
