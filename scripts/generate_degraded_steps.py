"""Generate degraded STEP variants from clean parametric STEPs.

For each input STEP, produce up to 3 degraded copies — one per defect class:

    open_shell         : removes one face, leaving an open shell
    sliver_face        : adds a thin sliver block as a sibling solid in a Compound
    self_intersection  : packages two overlapping copies of the part as a Compound

Each output is written to <output_dir>/<stem>__<defect>.step alongside
<stem>__<defect>.tags.json, which records the ground-truth defect tag(s).
A combined manifest.json summarizes successes / failures.

The legacy ``zero_length_edge`` defect class is still implemented for
backwards compatibility but is OFF by default — STEPControl_Writer strips
the sub-tolerance free edge during round-trip, so the resulting file is
indistinguishable from a clean baseline and produces a false-clean score.
Opt back in via ``--defects`` if you have a different writer in mind.

Usage:
    python scripts/generate_degraded_steps.py \
        --input data/parametric --output data/parametric_degraded \
        --max-inputs 50

Requires pythonocc-core. Operations that fail per-defect are logged into the
manifest and do not abort the run.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

try:
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_Transform,
    )
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import (
        STEPControl_AsIs,
        STEPControl_Reader,
        STEPControl_Writer,
    )
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import (
        TopoDS_Compound,
        TopoDS_Shape,
        TopoDS_Shell,
        topods,
    )
    from OCC.Core.gp import gp_Pnt, gp_Trsf, gp_Vec
    OCC_AVAILABLE = True
except ImportError:  # pragma: no cover — OCC not installed; functions raise on call
    OCC_AVAILABLE = False


DEFAULT_INPUT = Path("data/parametric")
DEFAULT_OUTPUT = Path("data/parametric_degraded")
# zero_length_edge is gated behind explicit opt-in (see module docstring).
DEFECT_NAMES = ("open_shell", "sliver_face", "self_intersection")
ALL_DEFECT_NAMES = ("zero_length_edge", *DEFECT_NAMES)


def _require_occ() -> None:
    if not OCC_AVAILABLE:
        raise RuntimeError(
            "pythonocc-core is required for generate_degraded_steps.py. "
            "Install via the conda env: micromamba activate simready"
        )


def read_step(path: Path) -> "TopoDS_Shape":
    _require_occ()
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed for {path}")
    reader.TransferRoots()
    return reader.OneShape()


def write_step(shape: "TopoDS_Shape", path: Path) -> None:
    _require_occ()
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    status = writer.Write(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP write failed for {path}")


def _bounding_diagonal(shape: "TopoDS_Shape") -> float:
    """Approximate diagonal of the AABB. Used to size translations."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    box = Bnd_Box()
    brepbndlib.Add(shape, box, True)
    if box.IsVoid():
        return 1.0
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    diag = (dx * dx + dy * dy + dz * dz) ** 0.5
    return max(diag, 1.0)


def make_zero_length_edge(shape: "TopoDS_Shape") -> "TopoDS_Shape":
    """Add a near-zero-length edge to the original shape via a Compound."""
    _require_occ()
    p1 = gp_Pnt(0.0, 0.0, 0.0)
    p2 = gp_Pnt(1e-9, 0.0, 0.0)
    edge = BRepBuilderAPI_MakeEdge(p1, p2).Edge()
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    builder.Add(compound, shape)
    builder.Add(compound, edge)
    return compound


def make_open_shell(shape: "TopoDS_Shape") -> "TopoDS_Shape":
    """Build a shell containing all faces of `shape` EXCEPT the first one."""
    _require_occ()
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    faces = []
    while explorer.More():
        faces.append(topods.Face(explorer.Current()))
        explorer.Next()
    if len(faces) < 2:
        raise RuntimeError("open_shell needs >=2 faces")
    builder = BRep_Builder()
    shell = TopoDS_Shell()
    builder.MakeShell(shell)
    for face in faces[1:]:
        builder.Add(shell, face)
    return shell


def make_sliver_face(shape: "TopoDS_Shape") -> "TopoDS_Shape":
    """Add a thin sliver block as a sibling solid in a Compound.

    The sliver shares no shared topology with the input; it is intentionally
    out-of-tolerance thin (0.001 unit) to look like a degenerate strip face.
    """
    _require_occ()
    diag = _bounding_diagonal(shape)
    # Sliver dimensions: one tiny dimension, two ~10% of diag.
    sliver_thickness = 1e-3
    sliver = BRepPrimAPI_MakeBox(0.1 * diag, 0.1 * diag, sliver_thickness).Shape()
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    builder.Add(compound, shape)
    builder.Add(compound, sliver)
    return compound


def make_self_intersection(shape: "TopoDS_Shape") -> "TopoDS_Shape":
    """Compound the original shape with a slightly-translated copy → overlap."""
    _require_occ()
    diag = _bounding_diagonal(shape)
    offset = 0.25 * diag  # translate < AABB so the copies overlap
    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(offset, 0.0, 0.0))
    moved = BRepBuilderAPI_Transform(shape, trsf, True).Shape()
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    builder.Add(compound, shape)
    builder.Add(compound, moved)
    return compound


DEFECT_GENERATORS: dict[str, Callable[["TopoDS_Shape"], "TopoDS_Shape"]] = {
    "zero_length_edge": make_zero_length_edge,
    "open_shell": make_open_shell,
    "sliver_face": make_sliver_face,
    "self_intersection": make_self_intersection,
}


def generate_for_input(
    input_step: Path,
    output_dir: Path,
    defects: list[str],
) -> list[dict[str, Any]]:
    """Run all requested defect generators on a single input STEP. Returns manifest rows."""
    rows: list[dict[str, Any]] = []
    try:
        shape = read_step(input_step)
    except Exception as exc:
        return [{
            "input": str(input_step),
            "defect": "<read>",
            "status": "error",
            "reason": f"read_step: {exc}",
        }]

    stem = input_step.stem
    for defect in defects:
        out_step = output_dir / f"{stem}__{defect}.step"
        out_tags = output_dir / f"{stem}__{defect}.tags.json"
        try:
            degraded = DEFECT_GENERATORS[defect](shape)
            write_step(degraded, out_step)
            tags_payload = {
                "stem": f"{stem}__{defect}",
                "source_step": str(input_step),
                "defect_tags": [defect],
                "synthesis": "scripts/generate_degraded_steps.py",
            }
            out_tags.write_text(json.dumps(tags_payload, indent=2), encoding="utf-8")
            rows.append({
                "input": str(input_step),
                "defect": defect,
                "status": "ok",
                "output_step": str(out_step),
                "output_tags": str(out_tags),
            })
        except Exception as exc:
            rows.append({
                "input": str(input_step),
                "defect": defect,
                "status": "error",
                "reason": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(limit=3),
            })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help=f"Input directory of clean parametric STEPs (default: {DEFAULT_INPUT})")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Output directory for degraded STEPs (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--max-inputs", type=int, default=50,
                        help="Cap the number of input STEPs to process. 0 = no cap. Default 50.")
    parser.add_argument("--defects", type=str, default=",".join(DEFECT_NAMES),
                        help=f"Comma-separated defect classes "
                             f"(default: {','.join(DEFECT_NAMES)}). "
                             f"Available: {','.join(ALL_DEFECT_NAMES)}")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"Input dir {args.input} missing.", file=sys.stderr)
        return 1
    args.output.mkdir(parents=True, exist_ok=True)

    requested = [d.strip() for d in args.defects.split(",") if d.strip()]
    invalid = [d for d in requested if d not in DEFECT_GENERATORS]
    if invalid:
        print(f"Unknown defect(s): {invalid}. Available: {list(DEFECT_GENERATORS)}",
              file=sys.stderr)
        return 1

    inputs = sorted(args.input.glob("*.step")) + sorted(args.input.glob("*.STEP"))
    if args.max_inputs > 0:
        inputs = inputs[: args.max_inputs]
    if not inputs:
        print(f"No STEP files in {args.input}.", file=sys.stderr)
        return 1

    print(f"Generating up to {len(inputs) * len(requested)} degraded STEPs "
          f"({len(inputs)} inputs × {len(requested)} defects)...", flush=True)

    manifest: list[dict[str, Any]] = []
    for i, step_file in enumerate(inputs, 1):
        rows = generate_for_input(step_file, args.output, requested)
        manifest.extend(rows)
        ok = sum(1 for r in rows if r["status"] == "ok")
        print(f"  [{i}/{len(inputs)}] {step_file.name}: {ok}/{len(rows)} ok",
              flush=True)

    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    total_ok = sum(1 for r in manifest if r["status"] == "ok")
    print(f"\nDone. {total_ok}/{len(manifest)} degraded STEPs written to {args.output}",
          flush=True)
    return 0 if total_ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
