#!/usr/bin/env python3
"""Generate synthetic parametric STEP files for SimReady Phase 2A training.

Five categories cover the rule-check landscape:
- normal_box: clean chunky solids (no findings expected)
- thin_plate: low min-dim ratio (triggers ThinWalls)
- l_bracket: fused box pair
- bracket_with_hole: cylindrical subtraction
- box_with_small_feature: small hole or bump (triggers SmallFeatures)

Default count is 100 per category. STEP files land in --output (default data/parametric/).
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

try:
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCC.Core.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
except ImportError as exc:  # pragma: no cover
    print(f"pythonocc-core import failed: {exc}", file=sys.stderr)
    raise SystemExit(2)


def _write_step(shape, out_path: Path) -> None:
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    writer.Write(str(out_path))


def _make_box(dx: float, dy: float, dz: float):
    return BRepPrimAPI_MakeBox(dx, dy, dz).Shape()


def _make_cylinder(radius: float, height: float, origin: tuple[float, float, float] = (0.0, 0.0, 0.0), axis: tuple[float, float, float] = (0.0, 0.0, 1.0)):
    ax2 = gp_Ax2(gp_Pnt(*origin), gp_Dir(*axis))
    return BRepPrimAPI_MakeCylinder(ax2, radius, height).Shape()


def gen_normal_box(rng: random.Random):
    dx = rng.uniform(20.0, 100.0)
    dy = rng.uniform(20.0, 100.0)
    dz = rng.uniform(20.0, 100.0)
    return _make_box(dx, dy, dz)


def gen_thin_plate(rng: random.Random):
    plate_dx = rng.uniform(40.0, 120.0)
    plate_dy = rng.uniform(40.0, 120.0)
    # Min/max ratio < 0.03 so ThinWalls fires
    plate_dz = rng.uniform(0.05, 0.8)
    return _make_box(plate_dx, plate_dy, plate_dz)


def gen_l_bracket(rng: random.Random):
    horizontal_dx = rng.uniform(40.0, 90.0)
    horizontal_dy = rng.uniform(40.0, 90.0)
    horizontal_dz = rng.uniform(5.0, 12.0)
    vertical_dz = rng.uniform(30.0, 80.0)

    base = _make_box(horizontal_dx, horizontal_dy, horizontal_dz)
    upright = BRepPrimAPI_MakeBox(
        gp_Pnt(0.0, 0.0, 0.0),
        horizontal_dx,
        horizontal_dz,
        vertical_dz,
    ).Shape()
    return BRepAlgoAPI_Fuse(base, upright).Shape()


def gen_bracket_with_hole(rng: random.Random):
    dx = rng.uniform(50.0, 100.0)
    dy = rng.uniform(40.0, 80.0)
    dz = rng.uniform(8.0, 20.0)
    radius = rng.uniform(3.0, min(dx, dy) * 0.2)
    origin_x = rng.uniform(radius * 1.5, dx - radius * 1.5)
    origin_y = rng.uniform(radius * 1.5, dy - radius * 1.5)

    body = _make_box(dx, dy, dz)
    hole = _make_cylinder(radius, dz, origin=(origin_x, origin_y, 0.0))
    return BRepAlgoAPI_Cut(body, hole).Shape()


def gen_box_with_small_feature(rng: random.Random):
    dx = rng.uniform(50.0, 100.0)
    dy = rng.uniform(50.0, 100.0)
    dz = rng.uniform(20.0, 50.0)
    # Small radius relative to max dim so SmallFilletsOrHoles / SmallFeatures fire.
    radius = rng.uniform(0.3, max(dx, dy) * 0.02)
    origin_x = rng.uniform(radius * 1.5, dx - radius * 1.5)
    origin_y = rng.uniform(radius * 1.5, dy - radius * 1.5)

    body = _make_box(dx, dy, dz)
    pin = _make_cylinder(radius, dz, origin=(origin_x, origin_y, 0.0))
    return BRepAlgoAPI_Cut(body, pin).Shape()


def apply_random_features(
    shape,
    rng: random.Random,
    fillet_prob: float = 0.0,
    chamfer_prob: float = 0.0,
    radius_range: tuple[float, float] = (1.0, 4.0),
):
    """Randomly fillet/chamfer edges so 'clean' training geometry carries
    manufactured features (real-CAD FP fix — see docs/validation/real_eval.md §1).

    Per-edge Bernoulli draws; any OCC failure (tangency, radius exceeding
    local size) falls back to the previous good shape so generation never
    aborts. Feature probability must stay independent of the defect label
    downstream — degraded variants are generated FROM featured cleans.
    """
    for prob, maker_cls in (
        (fillet_prob, BRepFilletAPI_MakeFillet),
        (chamfer_prob, BRepFilletAPI_MakeChamfer),
    ):
        if prob <= 0.0:
            continue
        try:
            maker = maker_cls(shape)
            n_added = 0
            explorer = TopExp_Explorer(shape, TopAbs_EDGE)
            while explorer.More():
                if rng.random() < prob:
                    radius = rng.uniform(*radius_range)
                    try:
                        maker.Add(radius, topods.Edge(explorer.Current()))
                        n_added += 1
                    except Exception:
                        pass
                explorer.Next()
            if n_added:
                maker.Build()
                if maker.IsDone():
                    candidate = maker.Shape()
                    if candidate is not None and not candidate.IsNull():
                        shape = candidate
        except Exception:
            pass  # keep the previous good shape
    return shape


CATEGORIES = {
    "normal_box": gen_normal_box,
    "thin_plate": gen_thin_plate,
    "l_bracket": gen_l_bracket,
    "bracket_with_hole": gen_bracket_with_hole,
    "small_feature_box": gen_box_with_small_feature,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("data/parametric"))
    parser.add_argument("--per-category", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260513)
    parser.add_argument("--categories", nargs="*", choices=sorted(CATEGORIES.keys()), default=None)
    parser.add_argument("--fillet-prob", type=float, default=0.0,
                        help="Per-edge probability of a random fillet (default 0 = off)")
    parser.add_argument("--chamfer-prob", type=float, default=0.0,
                        help="Per-edge probability of a random chamfer (default 0 = off)")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    categories = args.categories or sorted(CATEGORIES.keys())

    written = 0
    skipped = 0
    for category in categories:
        gen = CATEGORIES[category]
        for index in range(args.per_category):
            try:
                shape = gen(rng)
                if args.fillet_prob > 0.0 or args.chamfer_prob > 0.0:
                    shape = apply_random_features(
                        shape, rng,
                        fillet_prob=args.fillet_prob,
                        chamfer_prob=args.chamfer_prob,
                    )
            except Exception as exc:
                print(f"[skip] {category}#{index}: gen raised {exc}", file=sys.stderr)
                skipped += 1
                continue
            out_path = args.output / f"{category}_{index:04d}.step"
            try:
                _write_step(shape, out_path)
            except Exception as exc:
                print(f"[skip] {category}#{index}: STEP write raised {exc}", file=sys.stderr)
                skipped += 1
                continue
            written += 1

    print(f"wrote {written} STEP files to {args.output} (skipped {skipped})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
