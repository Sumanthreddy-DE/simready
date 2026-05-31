"""Executor for the geometry-gen DSL.

Two entry points:

- ``build_shape(spec)``                — in-process, returns a ``TopoDS_Shape``.
                                         Cheap to unit-test. Caller owns the
                                         shape's lifetime.
- ``build_part(spec_dict, *, timeout_s, output_dir)`` — spawn-subprocess wrapper
                                         that bounds wall-clock via
                                         ``Process.terminate()``. This is what
                                         the ``build_part`` agent tool calls.

The subprocess matters because the OCC boolean primitives (``BRepAlgoAPI_Cut``,
``BRepAlgoAPI_Fuse``) can deadlock on degenerate inputs (zero-overlap cut,
coplanar fuse) and Python thread timeouts do not interrupt the underlying C++
call. See ``lessons_pythonocc-gotchas.md`` and ``scripts/eval_real_cad.py`` for
the same pattern.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from simready.gen.spec import BoxOp, CutOp, CylOp, FuseOp, PartSpec

try:  # pragma: no cover — exercised under sr env only
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
except ImportError:  # pragma: no cover — base env without pythonocc
    BRepAlgoAPI_Cut = None
    BRepAlgoAPI_Fuse = None
    BRepPrimAPI_MakeBox = None
    BRepPrimAPI_MakeCylinder = None
    gp_Ax2 = None
    gp_Dir = None
    gp_Pnt = None
    STEPControl_AsIs = None
    STEPControl_Writer = None


# Repo-relative default output dir for generated parts. Persistent so the
# agent's next tool call (analyze_geometry) can read the file.
DEFAULT_OUTPUT_DIR = Path("data/gen_parts")
DEFAULT_BUILD_TIMEOUT_S = 15.0


# ----------------------------------------------------------------------------
# In-process executor
# ----------------------------------------------------------------------------


def _occ_required() -> None:
    if BRepPrimAPI_MakeBox is None:
        raise RuntimeError(
            "pythonocc-core is not importable in this Python environment. "
            "Run geometry-gen under the sr env (C:\\mm\\sr\\python.exe)."
        )


def _build_box(op: BoxOp):
    origin = gp_Pnt(*op.at)
    return BRepPrimAPI_MakeBox(origin, op.dx, op.dy, op.dz).Shape()


def _build_cyl(op: CylOp):
    axis = gp_Ax2(gp_Pnt(*op.at), gp_Dir(0.0, 0.0, 1.0))
    return BRepPrimAPI_MakeCylinder(axis, op.r, op.h).Shape()


def _build_fuse(a, b):
    op = BRepAlgoAPI_Fuse(a, b)
    op.Build()
    return op.Shape()


def _build_cut(a, b):
    op = BRepAlgoAPI_Cut(a, b)
    op.Build()
    return op.Shape()


def build_shape(spec: PartSpec):
    """Materialize ``spec`` into a ``TopoDS_Shape``, in-process.

    The returned shape is the result of the *last* step in ``spec.steps``.
    """
    _occ_required()
    shapes: list[Any] = []
    for step in spec.steps:
        if isinstance(step, BoxOp):
            shapes.append(_build_box(step))
        elif isinstance(step, CylOp):
            shapes.append(_build_cyl(step))
        elif isinstance(step, FuseOp):
            shapes.append(_build_fuse(shapes[step.a], shapes[step.b]))
        elif isinstance(step, CutOp):
            shapes.append(_build_cut(shapes[step.a], shapes[step.b]))
        else:  # pragma: no cover — Pydantic guarantees the discriminator
            raise TypeError(f"Unknown op type: {type(step).__name__}")
    return shapes[-1]


def write_step(shape: Any, out_path: Path) -> None:
    _occ_required()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    writer.Write(str(out_path))


# ----------------------------------------------------------------------------
# Subprocess wrapper — hard wall-clock via spawn + Process.terminate()
# ----------------------------------------------------------------------------


def _build_worker_main(spec_dict: dict, out_path_str: str, queue) -> None:
    """Spawn-child entry point: validate spec, build shape, write STEP, return
    a JSON-serialisable summary. The parent ``terminate()``s on overrun."""
    try:
        # Imports kept inside the worker so the parent can run without OCC
        # (Pydantic-only validation still works in base env).
        from simready.gen.build import build_shape, write_step
        from simready.gen.spec import PartSpec
        from simready.occ_utils import count_topology, shape_bounding_box
        from simready.validator import validate_brep

        spec = PartSpec.model_validate(spec_dict)
        shape = build_shape(spec)

        occ_check = validate_brep(shape)
        out_path = Path(out_path_str)
        try:
            write_step(shape, out_path)
            wrote = True
        except Exception as exc:  # noqa: BLE001 — surfaced to caller
            queue.put(("err", f"step_write_failed: {type(exc).__name__}: {exc}"))
            return

        bbox = shape_bounding_box(shape)
        topo = count_topology(shape)
        payload = {
            "step_path": str(out_path),
            "schema_valid": True,
            "occ_valid": bool(getattr(occ_check, "is_valid", False)),
            "occ_errors": list(getattr(occ_check, "errors", []) or []),
            "faces": int(topo.get("face_count", 0)),
            "edges": int(topo.get("edge_count", 0)),
            "solids": int(topo.get("solid_count", 0)),
            "bbox_mm": bbox,
            "wrote": wrote,
        }
        queue.put(("ok", payload))
    except Exception as exc:  # noqa: BLE001 — any failure becomes a result
        queue.put(("err", f"{type(exc).__name__}: {exc}"))


def build_part(
    spec_dict: dict,
    *,
    output_dir: str | os.PathLike[str] | None = None,
    timeout_s: float = DEFAULT_BUILD_TIMEOUT_S,
    repo_root: str | os.PathLike[str] | None = None,
) -> dict:
    """Resolve, build, and persist a part defined by ``spec_dict``.

    Runs the executor in a spawn child process so an OCC deadlock can be killed
    with ``Process.terminate()`` after ``timeout_s`` seconds. The caller never
    sees a wall-clock longer than ``timeout_s + ~5 s`` (grace for graceful shutdown).

    Returns a JSON-serialisable dict suitable for use as a tool-call result.
    """
    # Pre-flight: validate the spec in the parent so schema errors surface
    # without paying a subprocess spawn. (Mirrors the precheck pattern in
    # ``scripts/eval_real_cad.py``.)
    try:
        PartSpec.model_validate(spec_dict)
    except Exception as exc:  # noqa: BLE001
        return {
            "schema_valid": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    out_dir = Path(output_dir) if output_dir is not None else root / DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"gen_{uuid.uuid4().hex[:12]}.step"

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=_build_worker_main, args=(spec_dict, str(out_path), queue))
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            try:
                proc.kill()
            except Exception:  # pragma: no cover
                pass
        return {
            "schema_valid": True,
            "occ_valid": False,
            "error": f"build_timeout (>{int(timeout_s)}s)",
        }

    try:
        status, payload = queue.get(timeout=2)
    except Exception:
        return {
            "schema_valid": True,
            "occ_valid": False,
            "error": f"no_result_from_worker (exit={proc.exitcode})",
        }
    if status == "err":
        return {
            "schema_valid": True,
            "occ_valid": False,
            "error": payload,
        }
    return payload


# Manual smoke (sr env only):
#   python -m simready.gen.build
if __name__ == "__main__":  # pragma: no cover
    demo_spec = {
        "steps": [
            {"op": "box", "dx": 80, "dy": 60, "dz": 10},
            {"op": "cyl", "r": 5, "h": 10, "at": [40, 30, 0]},
            {"op": "cut", "a": 0, "b": 1},
        ]
    }
    result = build_part(demo_spec, timeout_s=15)
    import json

    print(json.dumps(result, indent=2, default=str), file=sys.stderr)
