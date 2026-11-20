# SP2 Generation Vocabulary v2 Implementation Plan

**Status:** active
**Last verified:** 2026-11-20

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a versioned DSL v2, a sandboxed free-form build123d arm and a leak-free repair pass to the SP1 benchmark, then run and publish the pre-registered SP2 comparisons (`bench_v2`).

**Architecture:** DSL v1 (`simready/gen/spec.py`, `build.py`) stays byte-identical; v2 is a separate schema + executor selected through a small registry (`simready/gen/dsl.py`). The bench gains an `arm` (`dsl-v1`, `dsl-v2`, `build123d`) pinned in every run header; the build123d arm runs model code in a dedicated venv child that writes one STEP, graded by the unchanged checker 1.0.0. Repair re-measures the failed part and sends back only measurements, never target ranges.

**Tech Stack:** Python 3.12, Pydantic v2, OCCT via `simready.occ_compat` (pythonocc or OCP `cadquery-ocp==8.0.1.1.0`), build123d 0.13.0 in its own venv, pytest, OpenAI-compatible chat API (D Labs, local `llama-server`).

**Design:** `docs/exec-plans/active/2026-11-20-sp2-vocab-v2-design.md` (decisions E1–E5, run matrix, pre-registered results). Read it first.

## Global Constraints

- `simready/gen/spec.py`, `simready/gen/build.py`, `simready/bench/prompts/concepts_v1.jsonl`, `concepts_v1.sha256` and `CHECKER_VERSION = "1.0.0"` are not edited.
- DSL v1 `system_prompt_sha256` stays `3dd19661924d5de944e4325eeed84d99ea14cab0483a3b595289d37185224d0c`; SP1 logs must regrade with 0 differences after every task that touches `simready/bench/`.
- A run header without `arm` means `dsl-v1` (SP1 logs).
- Step cap stays `STEPS_MAX = 16` in v2.
- Checks use v1 check types only; no new check type.
- Repair feedback never contains a target range, check list or check `detail` string.
- Approval gates (stop and ask the user): freezing `concepts_v2.sha256` (after proofread), creating `~/.venvs/simready-b123d`, installing `llama-server` and downloading model weights, every official run that spends D Labs credit or more than ~2 h of local compute.
- Python: run tests with the OCC venv, `~/.venvs/simready-ocp/bin/python -m pytest`; OCC-only test modules skip when `OCC_AVAILABLE` is false.
- Commit at the end of every task, staging only that task's files, in the same call as `git add`. No AI attribution. Never `git push` (the user pushes).

## File Structure

| File | Responsibility |
|---|---|
| `simready/occ_compat.py` (modify) | export the extra OCCT names v2 needs |
| `simready/gen/spec_v2.py` (create) | Pydantic schema for DSL v2 + `BUILD_PART_TOOL_SCHEMA_V2` |
| `simready/gen/build_v2.py` (create) | trusted executor for v2, `KernelBuildError` |
| `simready/gen/dsl.py` (create) | registry: version → schema, executor, tool schema, known ops |
| `simready/bench/concepts.py` (modify) | `CONCEPTS_V2`, per-file frozen hash, v2 reference specs loader |
| `simready/bench/prompts/concepts_v2.sha256` (create, gated) | frozen hash of `concepts_v2.jsonl` |
| `simready/bench/prompts/reference_specs_v2.json` (create) | hand-built v2 reference specs = v2 in-vocab definition |
| `simready/bench/prompting.py` (modify) | per-arm system prompt, tool, hash |
| `simready/bench/attempt.py` (modify) | `dsl` through classify/grade, STEP grading, `features` in results |
| `simready/bench/code_arm.py` (create) | code-arm prompt, code extraction, AST gate |
| `simready/bench/code_exec.py` (create) | run model code in the build123d venv child |
| `simready/bench/_b123d_child.py` (create) | child script executed by the build123d venv |
| `simready/bench/runner.py` (modify) | `arm` parameter, header pin, per-arm in-vocab |
| `simready/bench/replay.py` (modify) | arm-aware regrade/replay |
| `simready/bench/repair.py` (create) | measured feedback + repair run |
| `simready/bench/report.py` (modify) | arm comparison, repair section |
| `simready/bench/__main__.py` (modify) | `--arm`, `--concepts`, `repair`, `compare` |
| `simready/bench/providers.json` (modify) | local small-model entry |
| `docs/adr/0005-bench-free-form-code-arm.md` (create) | sandbox decision and limits |
| `docs/validation/bench_v2.md` (create) | published results |

---

### Task 0: Proofread and freeze `concepts_v2` (user gate)

**Files:**
- Modify: `simready/bench/concepts.py`
- Modify: `simready/bench/runner.py:94-96`
- Create: `simready/bench/prompts/concepts_v2.sha256`
- Test: `tests/test_bench_concepts_v2_file.py`, `tests/test_bench_runner.py`

**Interfaces:**
- Produces: `CONCEPTS_V2: Path`; `frozen_sha256(path: str | Path) -> str | None` now takes the `.sha256` path explicitly; `frozen_path(concepts_path: Path) -> Path` returns `concepts_path.with_suffix(".sha256")`.

- [ ] **Step 1: User proofread.** Ask the user to proofread `simready/bench/prompts/concepts_v2.jsonl` (flagged in sources: DIN 562 tolerance zones, ISO 2341 form B, the 1602 LCD 75 × 31 pattern; confirm ISO 4762 M6, K7 21.985–22.006, DIN 471 d = 10). Apply corrections in `scripts/bench_concepts_v2.py` only, then regenerate:

Run: `~/.venvs/simready-ocp/bin/python scripts/bench_concepts_v2.py --write`
Expected: 15 lines `cNNN ok`, last line `wrote simready/bench/prompts/concepts_v2.jsonl (15 concepts)`.

- [ ] **Step 2: Write the failing test** (append to `tests/test_bench_concepts_v2_file.py`):

```python
from simready.bench.concepts import CONCEPTS_V2, file_sha256, frozen_path, frozen_sha256


def test_concepts_v2_is_frozen():
    assert frozen_sha256(frozen_path(CONCEPTS_V2)) == file_sha256(CONCEPTS_V2)
```

and replace the local `CONCEPTS_V2 = BENCH_DIR / ...` line in that file with the import above.

- [ ] **Step 3: Run it to verify it fails**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_concepts_v2_file.py -q`
Expected: FAIL, `ImportError: cannot import name 'CONCEPTS_V2'`.

- [ ] **Step 4: Implement.** In `simready/bench/concepts.py` replace the two constants and `frozen_sha256`:

```python
CONCEPTS_V1 = BENCH_DIR / "prompts" / "concepts_v1.jsonl"
CONCEPTS_V2 = BENCH_DIR / "prompts" / "concepts_v2.jsonl"
CONCEPTS_V1_FROZEN = BENCH_DIR / "prompts" / "concepts_v1.sha256"


def frozen_path(concepts_path: str | Path) -> Path:
    return Path(concepts_path).with_suffix(".sha256")
```

```python
def frozen_sha256(path: str | Path = CONCEPTS_V1_FROZEN) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").strip() or None
```

(`frozen_sha256` body is unchanged; only `frozen_path` is new.) In `simready/bench/runner.py` change the official check:

```python
    if official:
        if frozen_sha256(frozen_path(concepts_path)) != prompt_sha:
            raise RuntimeError(f"official run needs the frozen prompt file ({frozen_path(concepts_path).name} must match)")
```

and import `frozen_path` from `simready.bench.concepts`.

- [ ] **Step 5: Freeze (user approval required).** After the user approves the proofread file:

Run: `sha256sum simready/bench/prompts/concepts_v2.jsonl | cut -d' ' -f1 > simready/bench/prompts/concepts_v2.sha256`

- [ ] **Step 6: Run tests**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_concepts_v2_file.py tests/test_bench_concepts_file.py tests/test_bench_runner.py -q`
Expected: all pass (the runner's existing official-run tests still raise for an unfrozen file).

- [ ] **Step 7: Commit**

```bash
git add scripts/bench_concepts_v2.py simready/bench/prompts/concepts_v2.jsonl simready/bench/prompts/concepts_v2.sha256 simready/bench/concepts.py simready/bench/runner.py tests/test_bench_concepts_v2_file.py && git commit -m "feat(bench): freeze concepts_v2 after proofread; per-file frozen hash"
```

---

### Task 1: DSL v2 schema

**Files:**
- Create: `simready/gen/spec_v2.py`
- Test: `tests/test_gen_spec_v2.py`

**Interfaces:**
- Consumes: v1 bounds and `BoxOp`, `FuseOp`, `CutOp` from `simready/gen/spec.py` (imported, not copied).
- Produces: `PartSpecV2` (`steps: list[OpV2]`, 1..16), op classes `CylOpV2`, `ConeOp`, `SphereOp`, `PrismOp`, `RegularPrismOp`, `PolarOp`, `GridOp`, `FilletOp`, `ChamferOp`; `Axis = Literal["x", "y", "z"]`; `EDGE_SELECTORS: frozenset[str]`; `KNOWN_OPS_V2: frozenset[str]`; `BUILD_PART_TOOL_SCHEMA_V2: dict`; `refs(step) -> tuple[int, ...]` (step indices a step consumes).

- [ ] **Step 1: Write the failing tests** — `tests/test_gen_spec_v2.py`:

```python
"""DSL v2 schema contracts. Pure Pydantic, no OCC."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from simready.bench.concepts import CONCEPTS_V1, load_concepts
from simready.gen.spec_v2 import (
    BUILD_PART_TOOL_SCHEMA_V2,
    EDGE_SELECTORS,
    KNOWN_OPS_V2,
    CylOpV2,
    PartSpecV2,
)


def v2(*steps):
    return PartSpecV2.model_validate({"steps": list(steps)})


def test_every_v1_reference_spec_is_a_valid_v2_spec():
    for c in load_concepts(CONCEPTS_V1):
        if c.in_vocab:
            v2(*c.reference_spec["steps"])


def test_cyl_axis_defaults_to_z():
    step = v2({"op": "cyl", "r": 5, "h": 10}).steps[0]
    assert isinstance(step, CylOpV2) and step.axis == "z"


def test_cone_rejects_equal_or_double_zero_radii():
    v2({"op": "cone", "r1": 4, "r2": 0, "h": 3})
    with pytest.raises(ValidationError):
        v2({"op": "cone", "r1": 0, "r2": 0, "h": 3})
    with pytest.raises(ValidationError):
        v2({"op": "cone", "r1": 4, "r2": 4, "h": 3})


def test_prism_needs_3_to_12_points():
    v2({"op": "prism", "points": [[0, 0], [30, 0], [0, 30]], "h": 5})
    with pytest.raises(ValidationError):
        v2({"op": "prism", "points": [[0, 0], [1, 0]], "h": 5})
    with pytest.raises(ValidationError):
        v2({"op": "prism", "points": [[i, i * i] for i in range(13)], "h": 5})


def test_regular_prism_sides_bounds():
    v2({"op": "regular_prism", "sides": 6, "across_flats": 8, "h": 3})
    with pytest.raises(ValidationError):
        v2({"op": "regular_prism", "sides": 2, "across_flats": 8, "h": 3})


def test_polar_and_grid_reference_rules():
    v2({"op": "cyl", "r": 1, "h": 5}, {"op": "polar", "of": 0, "count": 8, "center": [0, 0, 0]})
    with pytest.raises(ValidationError, match="prior step"):
        v2({"op": "cyl", "r": 1, "h": 5}, {"op": "polar", "of": 1, "count": 8, "center": [0, 0, 0]})
    with pytest.raises(ValidationError):
        v2({"op": "cyl", "r": 1, "h": 5}, {"op": "grid", "of": 0, "nx": 1, "ny": 1, "dx": 5, "dy": 5})


def test_pattern_counts_as_reference_for_orphan_rule():
    v2(
        {"op": "box", "dx": 80, "dy": 60, "dz": 5},
        {"op": "cyl", "r": 1, "h": 5, "at": [10, 10, 0]},
        {"op": "grid", "of": 1, "nx": 2, "ny": 2, "dx": 60, "dy": 40},
        {"op": "cut", "a": 0, "b": 2},
    )
    with pytest.raises(ValidationError, match="never referenced"):
        v2({"op": "box", "dx": 8, "dy": 6, "dz": 5}, {"op": "sphere", "r": 3})


def test_fillet_selector_vocabulary():
    assert EDGE_SELECTORS == frozenset({"all", ">x", "<x", "|x", ">y", "<y", "|y", ">z", "<z", "|z"})
    v2({"op": "box", "dx": 8, "dy": 6, "dz": 5}, {"op": "fillet", "a": 0, "r": 1, "edges": ">z"})
    with pytest.raises(ValidationError):
        v2({"op": "box", "dx": 8, "dy": 6, "dz": 5}, {"op": "fillet", "a": 0, "r": 1, "edges": "top"})


def test_step_cap_is_still_16():
    with pytest.raises(ValidationError, match="at most 16"):
        v2(*[{"op": "box", "dx": 1, "dy": 1, "dz": 1}] * 17)


def test_known_ops_and_tool_schema_mention_every_op():
    assert KNOWN_OPS_V2 == frozenset({"box", "cyl", "cone", "sphere", "prism", "regular_prism",
                                      "polar", "grid", "fillet", "chamfer", "fuse", "cut"})
    desc = BUILD_PART_TOOL_SCHEMA_V2["function"]["description"]
    for op in KNOWN_OPS_V2:
        assert op in desc, op
```

(17 boxes fail the list-length check, Pydantic's message "List should have at most 16 items", before any reference rule runs.)

- [ ] **Step 2: Run to verify failure**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_gen_spec_v2.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'simready.gen.spec_v2'`.

- [ ] **Step 3: Implement** `simready/gen/spec_v2.py`:

```python
"""Pydantic schema for DSL v2 (SP2, design E2).

v1 (``simready.gen.spec``) is frozen; every v1 spec validates here and builds
the same shape. New: an ``axis`` on ``cyl``; ``cone``, ``sphere``, ``prism``,
``regular_prism``; patterns ``polar`` / ``grid``; ``fillet`` / ``chamfer`` with
CadQuery-style edge selectors. Same 16-step cap and orphan rule as v1;
patterns count as references to the step they copy.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from simready.gen.spec import (
    DIM_MAX,
    PLACEMENT_MAX,
    PLACEMENT_MIN,
    RADIUS_MAX,
    STEPS_MAX,
    STEPS_MIN,
    BoxOp,
    CutOp,
    FuseOp,
    Placement,
    PositiveDim,
    PositiveRadius,
)

Axis = Literal["x", "y", "z"]
EDGE_SELECTORS = frozenset({"all"} | {f"{s}{a}" for s in "><|" for a in "xyz"})
EdgeSelector = Literal["all", ">x", "<x", "|x", ">y", "<y", "|y", ">z", "<z", "|z"]
NonNegRadius = Annotated[float, Field(ge=0, le=RADIUS_MAX)]
Point2 = tuple[
    Annotated[float, Field(ge=PLACEMENT_MIN, le=PLACEMENT_MAX)],
    Annotated[float, Field(ge=PLACEMENT_MIN, le=PLACEMENT_MAX)],
]
Offset = Annotated[float, Field(ge=-DIM_MAX, le=DIM_MAX)]


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CylOpV2(_Op):
    """Cylinder from ``at`` along +``axis``."""

    op: Literal["cyl"]
    r: PositiveRadius
    h: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)
    axis: Axis = "z"


class ConeOp(_Op):
    """Cone or frustum: radius ``r1`` at ``at``, ``r2`` at ``at + h * axis``."""

    op: Literal["cone"]
    r1: NonNegRadius
    r2: NonNegRadius
    h: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)
    axis: Axis = "z"

    @model_validator(mode="after")
    def _radii(self) -> "ConeOp":
        if self.r1 == 0 and self.r2 == 0:
            raise ValueError("cone needs r1 > 0 or r2 > 0")
        if self.r1 == self.r2:
            raise ValueError("cone with r1 == r2 is a cylinder; use cyl")
        return self


class SphereOp(_Op):
    op: Literal["sphere"]
    r: PositiveRadius
    at: Placement = (0.0, 0.0, 0.0)


class PrismOp(_Op):
    """Closed polygon of [u, v] points (plane: z->(x,y), x->(y,z), y->(x,z)) extruded h along +axis."""

    op: Literal["prism"]
    points: list[Point2] = Field(min_length=3, max_length=12)
    h: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)
    axis: Axis = "z"


class RegularPrismOp(_Op):
    """Regular polygon centred on ``at``, one flat parallel to u, extruded h along +axis."""

    op: Literal["regular_prism"]
    sides: int = Field(ge=3, le=12)
    across_flats: PositiveDim
    h: PositiveDim
    at: Placement = (0.0, 0.0, 0.0)
    axis: Axis = "z"


class PolarOp(_Op):
    """Union of ``count`` copies of step ``of`` rotated 360/count deg about the axis through ``center``."""

    op: Literal["polar"]
    of: NonNegativeInt
    count: int = Field(ge=2, le=64)
    center: Placement
    axis: Axis = "z"


class GridOp(_Op):
    """Union of nx * ny copies of step ``of`` translated i*dx along X and j*dy along Y."""

    op: Literal["grid"]
    of: NonNegativeInt
    nx: int = Field(ge=1, le=16)
    ny: int = Field(ge=1, le=16)
    dx: Offset
    dy: Offset

    @model_validator(mode="after")
    def _at_least_two(self) -> "GridOp":
        if self.nx * self.ny < 2:
            raise ValueError("grid needs nx * ny >= 2")
        return self


class FilletOp(_Op):
    op: Literal["fillet"]
    a: NonNegativeInt
    r: PositiveDim
    edges: EdgeSelector


class ChamferOp(_Op):
    op: Literal["chamfer"]
    a: NonNegativeInt
    d: PositiveDim
    edges: EdgeSelector


OpV2 = Annotated[
    Union[BoxOp, CylOpV2, ConeOp, SphereOp, PrismOp, RegularPrismOp, PolarOp, GridOp,
          FilletOp, ChamferOp, FuseOp, CutOp],
    Field(discriminator="op"),
]
KNOWN_OPS_V2 = frozenset({"box", "cyl", "cone", "sphere", "prism", "regular_prism",
                          "polar", "grid", "fillet", "chamfer", "fuse", "cut"})


def refs(step: BaseModel) -> tuple[int, ...]:
    """Step indices this step consumes."""
    if isinstance(step, (FuseOp, CutOp)):
        return (step.a, step.b)
    if isinstance(step, (PolarOp, GridOp)):
        return (step.of,)
    if isinstance(step, (FilletOp, ChamferOp)):
        return (step.a,)
    return ()


class PartSpecV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[OpV2] = Field(min_length=STEPS_MIN, max_length=STEPS_MAX)

    @model_validator(mode="after")
    def _check_refs(self) -> "PartSpecV2":
        for i, step in enumerate(self.steps):
            r = refs(step)
            for ref in r:
                if ref >= i:
                    raise ValueError(f"steps[{i}] refers to step {ref}; it must refer to a prior step (< {i})")
            if len(r) == 2 and r[0] == r[1]:
                raise ValueError(f"steps[{i}] cannot reference the same step on both sides ({r[0]})")
        return self

    @model_validator(mode="after")
    def _check_orphans(self) -> "PartSpecV2":
        referenced = {ref for step in self.steps for ref in refs(step)}
        for i, step in enumerate(self.steps[:-1]):
            if i not in referenced:
                raise ValueError(
                    f"steps[{i}] ({step.op}) is never referenced by a later step; only the final step "
                    f"is returned as the part, so this step would be discarded"
                )
        return self


BUILD_PART_TOOL_SCHEMA_V2: dict = {
    "type": "function",
    "function": {
        "name": "build_part",
        "description": (
            "Generate a new STEP file from a typed parametric spec. The spec is a list of ops: "
            "box(dx, dy, dz, at) [at = min corner]; "
            "cyl(r, h, at, axis) [base centre at 'at', extends h along +axis; axis 'x'|'y'|'z', default 'z']; "
            "cone(r1, r2, h, at, axis) [radius r1 at 'at', r2 at the far end; one radius may be 0, not both, r1 != r2]; "
            "sphere(r, at) [at = centre]; "
            "prism(points, h, at, axis) [3-12 [u, v] points of a closed polygon, offset by 'at', extruded h along +axis; "
            "(u, v) is (x, y) for axis 'z', (y, z) for 'x', (x, z) for 'y']; "
            "regular_prism(sides, across_flats, h, at, axis) [3-12 sides, centred on 'at', one flat parallel to u]; "
            "polar(of, count, center, axis) [union of count copies of step 'of' rotated evenly about the axis through center]; "
            "grid(of, nx, ny, dx, dy) [union of nx*ny copies of step 'of' moved i*dx along X and j*dy along Y]; "
            "fillet(a, r, edges) and chamfer(a, d, edges) [round or bevel edges of step 'a'; edges is 'all', "
            "'>z' (edges at the highest z), '<z' (lowest z), '|z' (straight edges parallel to z), same for x and y]; "
            "fuse(a, b); cut(a, b) [subtract b from a]. "
            "'a', 'b' and 'of' are 0-based indices of earlier steps. The last step is the part returned; "
            "every other step MUST be used by a later step. "
            f"A spec has at most {STEPS_MAX} steps. Limits in mm: lengths in (0, {DIM_MAX:g}], radii in (0, {RADIUS_MAX:g}] "
            f"(cone radii may be 0), coordinates in [{PLACEMENT_MIN:g}, {PLACEMENT_MAX:g}]."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": (
                        "Shape: {\"steps\": [{\"op\": ..., ...}, ...]}. Example, plate with 4 corner holes: "
                        "{\"steps\": [{\"op\":\"box\",\"dx\":80,\"dy\":60,\"dz\":5},"
                        "{\"op\":\"cyl\",\"r\":2,\"h\":5,\"at\":[10,10,0]},"
                        "{\"op\":\"grid\",\"of\":1,\"nx\":2,\"ny\":2,\"dx\":60,\"dy\":40},"
                        "{\"op\":\"cut\",\"a\":0,\"b\":2}]}."
                    ),
                },
            },
            "required": ["spec"],
        },
    },
}
```

- [ ] **Step 4: Run tests**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_gen_spec_v2.py tests/test_gen_spec.py -q`
Expected: all pass. If `test_fillet_selector_vocabulary`'s first assertion fails, the `EDGE_SELECTORS` comprehension and the `Literal` disagree — fix the comprehension, never the test.

- [ ] **Step 5: Commit**

```bash
git add simready/gen/spec_v2.py tests/test_gen_spec_v2.py && git commit -m "feat(gen): DSL v2 schema (axis, cone, sphere, prisms, patterns, fillet/chamfer)"
```

---

### Task 2: DSL v2 executor

**Files:**
- Modify: `simready/occ_compat.py` (`_MODULE_NAMES`)
- Create: `simready/gen/build_v2.py`
- Test: `tests/test_gen_build_v2.py`

**Interfaces:**
- Consumes: `PartSpecV2` and op classes (Task 1).
- Produces: `build_shape_v2(spec: PartSpecV2) -> TopoDS_Shape`; `class KernelBuildError(RuntimeError)` raised for kernel failures the model caused (fillet/chamfer not done, selector matched no edges, polygon face failed).

- [ ] **Step 1: Extend the shim.** In `simready/occ_compat.py` `_MODULE_NAMES`, add (names are identical in pythonocc and OCP):

```python
    "BRepBuilderAPI": ("BRepBuilderAPI_MakeFace", "BRepBuilderAPI_MakePolygon", "BRepBuilderAPI_Transform"),
    "BRepFilletAPI": ("BRepFilletAPI_MakeChamfer", "BRepFilletAPI_MakeFillet"),
```

and extend the existing entries to:

```python
    "BRepPrimAPI": ("BRepPrimAPI_MakeBox", "BRepPrimAPI_MakeCone", "BRepPrimAPI_MakeCylinder",
                    "BRepPrimAPI_MakePrism", "BRepPrimAPI_MakeSphere"),
    "GeomAbs": ("GeomAbs_Cylinder", "GeomAbs_Line"),
    "gp": ("gp_Ax1", "gp_Ax2", "gp_Dir", "gp_Pnt", "gp_Trsf", "gp_Vec"),
```

Run: `~/.venvs/simready-ocp/bin/python -c "import simready.occ_compat as o; print(o.BACKEND, o.BRepFilletAPI_MakeFillet is not None, o.gp_Trsf is not None)"`
Expected: `ocp True True`.

- [ ] **Step 2: Write the failing tests** — `tests/test_gen_build_v2.py`:

```python
"""DSL v2 executor: each op against an analytic volume or extent (OCC)."""

from __future__ import annotations

import math

import pytest

from simready.occ_compat import OCC_AVAILABLE

if not OCC_AVAILABLE:
    pytest.skip("OCC bindings not available", allow_module_level=True)

from simready.bench import geometry as geo  # noqa: E402
from simready.bench.concepts import CONCEPTS_V1, load_concepts  # noqa: E402
from simready.gen.build import build_shape  # noqa: E402
from simready.gen.build_v2 import KernelBuildError, build_shape_v2  # noqa: E402
from simready.gen.spec import PartSpec  # noqa: E402
from simready.gen.spec_v2 import PartSpecV2  # noqa: E402


def build(*steps):
    return build_shape_v2(PartSpecV2.model_validate({"steps": list(steps)}))


@pytest.mark.parametrize("c", [c for c in load_concepts(CONCEPTS_V1) if c.in_vocab][:10], ids=lambda c: c.concept_id)
def test_v1_specs_build_identically(c):
    a = geo.fingerprint(build_shape(PartSpec.model_validate(c.reference_spec)))
    b = geo.fingerprint(build_shape_v2(PartSpecV2.model_validate(c.reference_spec)))
    assert a == b


def test_cyl_axis_x_extent():
    assert geo.sorted_extents(build({"op": "cyl", "r": 5, "h": 40, "axis": "x"})) == pytest.approx([10, 10, 40], abs=1e-6)


def test_cone_and_sphere_volumes():
    assert geo.volume(build({"op": "cone", "r1": 3, "r2": 0, "h": 9})) == pytest.approx(math.pi * 9 * 9 / 3, rel=1e-6)
    assert geo.volume(build({"op": "sphere", "r": 10})) == pytest.approx(4 / 3 * math.pi * 1000, rel=1e-6)


def test_prism_triangle_volume_and_plane_mapping():
    tri = {"op": "prism", "points": [[0, 0], [30, 0], [0, 30]], "h": 5, "axis": "y"}
    shape = build(tri)
    assert geo.volume(shape) == pytest.approx(0.5 * 30 * 30 * 5, rel=1e-6)
    assert geo.sorted_extents(shape) == pytest.approx([5, 30, 30], abs=1e-6)


def test_regular_hexagon_flats_parallel_to_u():
    shape = build({"op": "regular_prism", "sides": 6, "across_flats": 10, "h": 4})
    assert geo.sorted_extents(shape) == pytest.approx([4, 10, 20 / math.sqrt(3)], abs=1e-6)


def test_polar_eight_holes_on_bolt_circle():
    shape = build(
        {"op": "cyl", "r": 50, "h": 10},
        {"op": "cyl", "r": 4.5, "h": 10, "at": [37.5, 0, 0]},
        {"op": "polar", "of": 1, "count": 8, "center": [0, 0, 0]},
        {"op": "cut", "a": 0, "b": 2},
    )
    holes = [f for f in geo.cylindrical_features(shape) if f.concave and abs(f.diameter - 9) < 1e-6]
    assert len(holes) == 8


def test_grid_two_by_two():
    shape = build(
        {"op": "box", "dx": 80, "dy": 60, "dz": 5},
        {"op": "cyl", "r": 2, "h": 5, "at": [10, 10, 0]},
        {"op": "grid", "of": 1, "nx": 2, "ny": 2, "dx": 60, "dy": 40},
        {"op": "cut", "a": 0, "b": 2},
    )
    assert geo.volume(shape) == pytest.approx(80 * 60 * 5 - 4 * math.pi * 4 * 5, rel=1e-6)


def test_fillet_top_edges_removes_material():
    plain = 80 * 50 * 10
    shape = build({"op": "box", "dx": 80, "dy": 50, "dz": 10}, {"op": "fillet", "a": 0, "r": 3, "edges": ">z"})
    removed = (1 - math.pi / 4) * 9 * (2 * 80 + 2 * 50)  # straight runs; corners add a little more
    assert plain - geo.volume(shape) == pytest.approx(removed, rel=0.05)


def test_chamfer_shaft_ends():
    shape = build({"op": "cyl", "r": 6, "h": 60}, {"op": "chamfer", "a": 0, "d": 1, "edges": "all"})
    assert geo.sorted_extents(shape) == pytest.approx([12, 12, 60], abs=1e-6)
    assert geo.volume(shape) < math.pi * 36 * 60


def test_impossible_fillet_is_a_kernel_build_error():
    with pytest.raises(KernelBuildError):
        build({"op": "box", "dx": 4, "dy": 4, "dz": 4}, {"op": "fillet", "a": 0, "r": 3, "edges": "all"})
```

- [ ] **Step 3: Run to verify failure**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_gen_build_v2.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'simready.gen.build_v2'`.

- [ ] **Step 4: Implement** `simready/gen/build_v2.py`:

```python
"""Trusted executor for DSL v2 (design E2). In-process; callers that need a
wall-clock bound run it in a spawn child (``simready.bench.attempt``).

``KernelBuildError`` marks failures the *spec* caused (fillet too large,
selector matched nothing, degenerate polygon): the bench scores them as
F4_build_error. Any other exception is an executor bug.
"""

from __future__ import annotations

import math
from typing import Any

from simready.gen.spec import BoxOp, CutOp, FuseOp
from simready.gen.spec_v2 import (
    ChamferOp,
    ConeOp,
    CylOpV2,
    FilletOp,
    GridOp,
    PartSpecV2,
    PolarOp,
    PrismOp,
    RegularPrismOp,
    SphereOp,
)
from simready.occ_compat import (
    BRepAdaptor_Curve,
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Fuse,
    BRepCheck_Analyzer,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_Transform,
    BRepFilletAPI_MakeChamfer,
    BRepFilletAPI_MakeFillet,
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCone,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakePrism,
    BRepPrimAPI_MakeSphere,
    GeomAbs_Line,
    TopAbs_EDGE,
    TopExp_Explorer,
    gp_Ax1,
    gp_Ax2,
    gp_Dir,
    gp_Pnt,
    gp_Trsf,
    gp_Vec,
    topods,
)

_AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
_PLANE = {"z": (0, 1), "x": (1, 2), "y": (0, 2)}  # (u, v) -> coordinate indices
_SEL_TOL = 1e-6


class KernelBuildError(RuntimeError):
    """The spec asked for geometry the kernel cannot make."""


def _ax2(at, axis):
    return gp_Ax2(gp_Pnt(*at), gp_Dir(*_AXES[axis]))


def _bool(op_cls, a, b):
    op = op_cls(a, b)
    op.Build()
    if not op.IsDone():
        raise KernelBuildError(f"{op_cls.__name__} failed")
    return op.Shape()


def _uv_to_xyz(at, axis, u, v):
    p = list(at)
    iu, iv = _PLANE[axis]
    p[iu] += u
    p[iv] += v
    return tuple(p)


def _prism(points_uv, h, at, axis):
    poly = BRepBuilderAPI_MakePolygon()
    for u, v in points_uv:
        poly.Add(gp_Pnt(*_uv_to_xyz(at, axis, u, v)))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire())
    if not face.IsDone():
        raise KernelBuildError("prism polygon is not a valid planar face")
    d = _AXES[axis]
    return BRepPrimAPI_MakePrism(face.Face(), gp_Vec(d[0] * h, d[1] * h, d[2] * h)).Shape()


def _regular_points(sides, across_flats):
    rc = across_flats / (2 * math.cos(math.pi / sides))
    offset = math.pi / 2 - math.pi / sides  # puts one flat perpendicular to v, i.e. parallel to u
    return [(rc * math.cos(offset + 2 * math.pi * k / sides), rc * math.sin(offset + 2 * math.pi * k / sides))
            for k in range(sides)]


def _transformed(shape, trsf):
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def _fuse_all(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = _bool(BRepAlgoAPI_Fuse, out, s)
    return out


def _polar(shape, op: PolarOp):
    copies = [shape]
    for k in range(1, op.count):
        t = gp_Trsf()
        t.SetRotation(gp_Ax1(gp_Pnt(*op.center), gp_Dir(*_AXES[op.axis])), 2 * math.pi * k / op.count)
        copies.append(_transformed(shape, t))
    return _fuse_all(copies)


def _grid(shape, op: GridOp):
    copies = []
    for i in range(op.nx):
        for j in range(op.ny):
            t = gp_Trsf()
            t.SetTranslation(gp_Vec(i * op.dx, j * op.dy, 0.0))
            copies.append(_transformed(shape, t))
    return _fuse_all(copies)


def _unique_edges(shape) -> list[Any]:
    edges: list[Any] = []
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        e = topods.Edge(exp.Current())
        if not any(e.IsSame(seen) for seen in edges):
            edges.append(e)
        exp.Next()
    return edges


def select_edges(shape, selector: str) -> list[Any]:
    edges = _unique_edges(shape)
    if selector == "all":
        return edges
    kind, axis = selector[0], "xyz".index(selector[1])
    if kind == "|":
        out = []
        for e in edges:
            c = BRepAdaptor_Curve(e)
            if c.GetType() == GeomAbs_Line:
                d = c.Line().Direction()
                if abs(abs((d.X(), d.Y(), d.Z())[axis]) - 1.0) < _SEL_TOL:
                    out.append(e)
        return out
    mids = []
    for e in edges:
        c = BRepAdaptor_Curve(e)
        p = c.Value((c.FirstParameter() + c.LastParameter()) / 2)
        mids.append((p.X(), p.Y(), p.Z())[axis])
    target = max(mids) if kind == ">" else min(mids)
    return [e for e, m in zip(edges, mids) if abs(m - target) <= _SEL_TOL]


def _edge_op(shape, op):
    edges = select_edges(shape, op.edges)
    if not edges:
        raise KernelBuildError(f"edge selector {op.edges!r} matched no edges")
    maker = BRepFilletAPI_MakeFillet(shape) if isinstance(op, FilletOp) else BRepFilletAPI_MakeChamfer(shape)
    size = op.r if isinstance(op, FilletOp) else op.d
    for e in edges:
        maker.Add(size, e)
    try:
        maker.Build()
        ok = maker.IsDone()
    except Exception as exc:  # OCCT raises Standard_Failure subclasses for impossible blends
        raise KernelBuildError(f"{op.op} failed: {type(exc).__name__}: {exc}") from exc
    if not ok:
        raise KernelBuildError(f"{op.op} of size {size} on {len(edges)} edges could not be built")
    result = maker.Shape()
    # OCCT can report IsDone() for an oversized blend and return an invalid solid
    # (probed 2026-11-20: r = 3 on a 4 mm cube gave volume 490461 mm^3, IsValid False).
    if not BRepCheck_Analyzer(result).IsValid():
        raise KernelBuildError(f"{op.op} of size {size} produced an invalid solid")
    return result


def build_shape_v2(spec: PartSpecV2):
    """Materialize ``spec``; returns the last step's shape."""
    shapes: list[Any] = []
    for s in spec.steps:
        if isinstance(s, BoxOp):
            shapes.append(BRepPrimAPI_MakeBox(gp_Pnt(*s.at), s.dx, s.dy, s.dz).Shape())
        elif isinstance(s, CylOpV2):
            shapes.append(BRepPrimAPI_MakeCylinder(_ax2(s.at, s.axis), s.r, s.h).Shape())
        elif isinstance(s, ConeOp):
            shapes.append(BRepPrimAPI_MakeCone(_ax2(s.at, s.axis), s.r1, s.r2, s.h).Shape())
        elif isinstance(s, SphereOp):
            shapes.append(BRepPrimAPI_MakeSphere(gp_Pnt(*s.at), s.r).Shape())
        elif isinstance(s, PrismOp):
            shapes.append(_prism(s.points, s.h, s.at, s.axis))
        elif isinstance(s, RegularPrismOp):
            shapes.append(_prism(_regular_points(s.sides, s.across_flats), s.h, s.at, s.axis))
        elif isinstance(s, PolarOp):
            shapes.append(_polar(shapes[s.of], s))
        elif isinstance(s, GridOp):
            shapes.append(_grid(shapes[s.of], s))
        elif isinstance(s, (FilletOp, ChamferOp)):
            shapes.append(_edge_op(shapes[s.a], s))
        elif isinstance(s, FuseOp):
            shapes.append(_bool(BRepAlgoAPI_Fuse, shapes[s.a], shapes[s.b]))
        elif isinstance(s, CutOp):
            shapes.append(_bool(BRepAlgoAPI_Cut, shapes[s.a], shapes[s.b]))
        else:  # pragma: no cover — the discriminator guarantees the type
            raise TypeError(f"unknown op {type(s).__name__}")
    return shapes[-1]
```

Note on `test_v1_specs_build_identically`: v1 `_build_fuse`/`_build_cut` do not check `IsDone`; v2 does. A v1 spec whose boolean fails therefore raises in v2 instead of returning a broken shape — that is intended and graded F4.

- [ ] **Step 5: Run tests**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_gen_build_v2.py tests/test_gen_build.py -q`
Expected: all pass. If `test_fillet_top_edges_removes_material` is outside 5%, print `plain - volume` and compare with the closed form before touching the tolerance (Working Rule 9: suspect the expectation and the probe before the executor).

- [ ] **Step 6: Commit**

```bash
git add simready/occ_compat.py simready/gen/build_v2.py tests/test_gen_build_v2.py && git commit -m "feat(gen): DSL v2 executor with KernelBuildError"
```

---

### Task 3: DSL registry and arm plumbing through the bench

**Files:**
- Create: `simready/gen/dsl.py`
- Modify: `simready/bench/prompting.py`, `simready/bench/attempt.py`, `simready/bench/runner.py`, `simready/bench/replay.py`, `simready/bench/__main__.py`
- Test: `tests/test_bench_arms.py`

**Interfaces:**
- Consumes: Task 1 and Task 2 names.
- Produces:
  - `simready.gen.dsl`: `DSL_VERSIONS = ("v1", "v2")`; `spec_model(v) -> type[BaseModel]`; `build(v, spec_dict) -> TopoDS_Shape` (validates then builds); `tool_schema(v) -> dict`; `known_ops(v) -> frozenset[str]`.
  - `simready.bench.prompting`: `ARMS = ("dsl-v1", "dsl-v2", "build123d")`; `dsl_of(arm) -> str | None`; `bench_tool(arm) -> dict | None`; `system_prompt(arm) -> str`; `system_prompt_sha256(arm="dsl-v1") -> str`; `build_messages(prompt, arm="dsl-v1")`. `BUILD_PART_TOOL` and `SYSTEM_PROMPT` stay as v1 aliases.
  - `simready.bench.attempt`: `classify_spec(spec, dsl="v1")`, `grade_spec(spec_dict, checks, expected_solids=1, timeout_s=GRADE_TIMEOUT_S, dsl="v1")`, `evaluate_reply(parsed, checks, expected_solids, grade=grade_spec, dsl="v1")`; `KNOWN_OPS` stays the v1 set.
  - `simready.bench.runner.run_benchmark(..., arm: str = "dsl-v1")`; header key `arm` (pinned; a header without it equals `dsl-v1`); attempt key `in_vocab` = in-vocab for that arm.
  - CLI: `run --arm {dsl-v1,dsl-v2,build123d} --concepts PATH`.

- [ ] **Step 1: Write the failing tests** — `tests/test_bench_arms.py`:

```python
"""Arm plumbing: v1 stays byte-identical, v2 is selectable and pinned."""

from __future__ import annotations

from simready.bench.attempt import F9, classify_spec
from simready.bench.prompting import (
    BUILD_PART_TOOL,
    bench_tool,
    build_messages,
    system_prompt_sha256,
)
from simready.gen.dsl import known_ops, spec_model

SP1_HASH = "3dd19661924d5de944e4325eeed84d99ea14cab0483a3b595289d37185224d0c"
FILLET = {"steps": [{"op": "box", "dx": 8, "dy": 6, "dz": 5}, {"op": "fillet", "a": 0, "r": 1, "edges": ">z"}]}


def test_v1_prompt_hash_unchanged():
    assert system_prompt_sha256() == SP1_HASH
    assert system_prompt_sha256("dsl-v1") == SP1_HASH
    assert bench_tool("dsl-v1") == BUILD_PART_TOOL


def test_v2_prompt_differs_and_has_no_agent_sentence():
    assert system_prompt_sha256("dsl-v2") != SP1_HASH
    desc = bench_tool("dsl-v2")["function"]["description"]
    assert "analyze_geometry" not in desc and "polar" in desc


def test_fillet_is_out_of_vocab_in_v1_and_valid_in_v2():
    assert classify_spec(FILLET)[0] == F9
    assert classify_spec(FILLET, dsl="v2") == (None, [])
    assert known_ops("v1") == frozenset({"box", "cyl", "fuse", "cut"})
    spec_model("v2").model_validate(FILLET)


def test_messages_per_arm():
    assert build_messages("x")[0]["content"] == build_messages("x", "dsl-v2")[0]["content"]
    assert bench_tool("build123d") is None
```

Append to `tests/test_bench_runner.py`. That file has a `FakeClient` class (line 33; `calls` holds `(prompt, seed)` tuples), a `concepts` fixture (a two-concept file in `tmp_path`) and a `_run(...)` helper; read the helper's signature first and pass `arm` through it if it forwards `**kwargs`, else call `run_benchmark` directly as below. `ok_grade` stands for the passing fake grade the file already uses (copy its name from the existing tests).

```python
def test_header_pins_arm(tmp_path, concepts):
    out = tmp_path / "r.jsonl"
    kw = dict(model_alias="m", model_id="m", base_url="u", k=1, out_path=out, concepts_path=concepts,
              workers=1, grade=ok_grade)
    run_benchmark(client=FakeClient(), arm="dsl-v2", **kw)
    assert runlog.read_header(out)["arm"] == "dsl-v2"
    with pytest.raises(RuntimeError, match="resume mismatch on arm"):
        run_benchmark(client=FakeClient(), arm="dsl-v1", **kw)


def test_header_without_arm_resumes_as_dsl_v1(tmp_path, concepts):
    out = tmp_path / "r.jsonl"
    kw = dict(model_alias="m", model_id="m", base_url="u", k=1, out_path=out, concepts_path=concepts,
              workers=1, grade=ok_grade)
    run_benchmark(client=FakeClient(), **kw)
    lines = out.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0]); header.pop("arm")
    out.write_text("\n".join([json.dumps(header)] + lines[1:]) + "\n", encoding="utf-8")
    run_benchmark(client=FakeClient(), arm="dsl-v1", **kw)  # an SP1-style header resumes as dsl-v1
```

- [ ] **Step 2: Run to verify failure**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_arms.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'simready.gen.dsl'`.

- [ ] **Step 3: Implement the registry** `simready/gen/dsl.py`:

```python
"""DSL version registry: one place that maps a version to schema, executor and tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

DSL_VERSIONS = ("v1", "v2")


def spec_model(version: str) -> type[BaseModel]:
    if version == "v1":
        from simready.gen.spec import PartSpec
        return PartSpec
    if version == "v2":
        from simready.gen.spec_v2 import PartSpecV2
        return PartSpecV2
    raise ValueError(f"unknown DSL version {version!r}")


def known_ops(version: str) -> frozenset[str]:
    if version == "v1":
        return frozenset({"box", "cyl", "fuse", "cut"})
    from simready.gen.spec_v2 import KNOWN_OPS_V2
    spec_model(version)  # raises for an unknown version
    return KNOWN_OPS_V2


def tool_schema(version: str) -> dict:
    if version == "v1":
        from simready.gen.spec import BUILD_PART_TOOL_SCHEMA
        return BUILD_PART_TOOL_SCHEMA
    from simready.gen.spec_v2 import BUILD_PART_TOOL_SCHEMA_V2
    spec_model(version)
    return BUILD_PART_TOOL_SCHEMA_V2


def build(version: str, spec_dict: dict) -> Any:
    spec = spec_model(version).model_validate(spec_dict)
    if version == "v1":
        from simready.gen.build import build_shape
        return build_shape(spec)
    from simready.gen.build_v2 import build_shape_v2
    return build_shape_v2(spec)
```

- [ ] **Step 4: Prompting.** In `simready/bench/prompting.py` keep `SYSTEM_PROMPT`, `_AGENT_ONLY_MARKER`, `_bench_tool` and `BUILD_PART_TOOL` exactly; add below them:

```python
ARMS = ("dsl-v1", "dsl-v2", "build123d")


def dsl_of(arm: str) -> str | None:
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; one of {ARMS}")
    return None if arm == "build123d" else arm.removeprefix("dsl-")


def bench_tool(arm: str = "dsl-v1") -> dict | None:
    dsl = dsl_of(arm)
    if dsl is None:
        return None
    if dsl == "v1":
        return BUILD_PART_TOOL
    from simready.gen.dsl import tool_schema
    return copy.deepcopy(tool_schema(dsl))  # v2 schema carries no agent-only sentence and no timeout


def system_prompt(arm: str = "dsl-v1") -> str:
    if dsl_of(arm) is None:
        from simready.bench.code_arm import CODE_SYSTEM_PROMPT
        return CODE_SYSTEM_PROMPT
    return SYSTEM_PROMPT
```

and replace `build_messages` and `system_prompt_sha256` with:

```python
def build_messages(prompt: str, arm: str = "dsl-v1") -> list[dict]:
    return [{"role": "system", "content": system_prompt(arm)}, {"role": "user", "content": prompt}]


def system_prompt_sha256(arm: str = "dsl-v1") -> str:
    tool = bench_tool(arm)
    payload = {"system": system_prompt(arm), "tool": tool} if tool is not None else {"system": system_prompt(arm), "arm": arm}
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

The v1 payload `{"system": SYSTEM_PROMPT, "tool": BUILD_PART_TOOL}` is unchanged, so the SP1 hash holds. (`code_arm` arrives in Task 5; until then `system_prompt("build123d")` is not called by any test.)

- [ ] **Step 5: Attempt.** In `simready/bench/attempt.py`:

1. `classify_spec(spec: dict, dsl: str = "v1")`: replace `KNOWN_OPS` in the unknown-op test with `known_ops(dsl)` and `PartSpec.model_validate(spec)` with `spec_model(dsl).model_validate(spec)` (import both from `simready.gen.dsl`). Keep `KNOWN_OPS` defined (other modules import it).
2. `_tool_argument_failure(arguments, dsl="v1")` passes `dsl` to both `classify_spec` calls.
3. `_grade_worker(spec_dict, checks_json, expected_solids, out_queue, dsl="v1")`: replace `spec = PartSpec.model_validate(spec_dict)` with `spec_model(dsl).model_validate(spec_dict)` and `shape = build_shape(spec)` with `shape = dsl_build(dsl, spec_dict)` (`from simready.gen.dsl import build as dsl_build`). In the native-exception test add the v2 marker:

```python
        native = (type(exc).__module__ in ("OCP.OCP.Standard", "OCP.Standard", "OCC.Core.Standard")
                  or type(exc).__name__ == "KernelBuildError")
```

4. `grade_spec(..., dsl: str = "v1")` and `_spawn_grade(..., dsl)` pass `dsl` into `args=(spec_dict, checks_json, expected_solids, mailbox, dsl)` — note the worker's positional order becomes `(spec_dict, checks_json, expected_solids, out_queue, dsl)`.
5. `evaluate_reply(parsed, checks, expected_solids, grade=grade_spec, dsl="v1")`: pass `dsl` to `_tool_argument_failure` and `classify_spec`; the `grade` callable keeps its 3-argument signature — callers bind the version with `functools.partial(grade_spec, dsl=...)`.

- [ ] **Step 6: Runner.** In `simready/bench/runner.py`:

```python
def run_benchmark(*, ..., extra_body: dict | None = None, arm: str = "dsl-v1") -> RunSummary:
    from functools import partial
    from simready.bench.prompting import bench_tool, build_messages, dsl_of, system_prompt_sha256
    from simready.bench.concepts import v2_reference_ids

    dsl = dsl_of(arm)
    if grade is grade_spec and dsl is not None:
        grade = partial(grade_spec, dsl=dsl)
    tools = [bench_tool(arm)] if bench_tool(arm) is not None else []
    in_vocab_v2 = v2_reference_ids()
```

Header: add `"arm": arm` and `"system_prompt_sha256": system_prompt_sha256(arm)`. Insert `"arm"` into `_PINNED` **immediately before** `"system_prompt_sha256"` (the resume check walks `_PINNED` in order and v1/v2 also differ on the prompt hash, so `arm` must be compared first for the error to name it). In the resume loop read the existing value with `existing.get(key, "dsl-v1" if key == "arm" else None)`. Put the per-arm in-vocab rule in one shared function in `simready/bench/concepts.py`, used by the runner here and by `regrade` in Step 7:

```python
def in_vocab_for(arm: str, concept: Concept, v2_ids: set[str]) -> bool:
    return {"dsl-v1": concept.in_vocab, "dsl-v2": concept.concept_id in v2_ids, "build123d": True}[arm]
```

In `work()`:

```python
        base = {..., "in_vocab": in_vocab_for(arm, item.concept, in_vocab_v2), ...}
        reply = client.complete(build_messages(prompt, arm), tools, TEMPERATURE, seed=item.idx)
```

and `evaluate_reply(..., grade=grade, dsl=dsl or "v1")`. The build123d branch of `work()` is added in Task 7; until then `arm="build123d"` raises `NotImplementedError("build123d arm: Task 7")` at the top of `run_benchmark`.

`v2_reference_ids()` comes from Task 4; for this task add a stub in `simready/bench/concepts.py`:

```python
REFERENCE_SPECS_V2 = BENCH_DIR / "prompts" / "reference_specs_v2.json"


def load_v2_reference_specs(path: str | Path = REFERENCE_SPECS_V2) -> dict[str, dict]:
    """concept_id -> v2 reference spec. v1 in-vocab concepts fall back to their v1 spec."""
    import json
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def v2_reference_ids() -> set[str]:
    ids = {c.concept_id for c in load_concepts(CONCEPTS_V1) if c.in_vocab}
    ids |= {c.concept_id for c in load_concepts(CONCEPTS_V2) if c.in_vocab}
    return ids | set(load_v2_reference_specs())
```

- [ ] **Step 7: Replay/regrade.** In `simready/bench/replay.py`:
  - `regrade(run_path, out_path, concepts_path=None, grade=None)` and `replay(run_path, attempt_id, concepts_path=None)` read `arm = header.get("arm", "dsl-v1")`.
  - When `concepts_path` is `None`, they resolve the concept file from the header: `BENCH_DIR / "prompts" / header["prompt_file"]`. SP1 headers carry `"prompt_file": "concepts_v1.jsonl"`, so SP1 behaviour is unchanged.
  - They call `evaluate_reply(..., dsl=dsl_of(arm))` with `grade = grade or partial(grade_spec, dsl=dsl_of(arm))`.
  - They replace the line `record["in_vocab"] = concept.in_vocab` with `record["in_vocab"] = in_vocab_for(arm, concept, v2_reference_ids())`.
  - A `build123d` log raises `NotImplementedError` until Task 7.
  - Add `--concepts` to the `regrade` and `replay` CLI parsers (`g` and `p` in `main()`), passed through as `concepts_path`.

  Test, appended to `tests/test_bench_replay.py`. Write a two-attempt fake log whose header has `"arm": "dsl-v2"` and `"prompt_file"` pointing at a temp concept file holding one concept with id `c041` and `in_vocab: false` (v1 says out of vocab; `reference_specs_v2.json` from Task 4 says in, so write this test in Task 4 or monkeypatch `v2_reference_ids` to return `{"c041"}` here). Regrade it with an injected passing `grade`, then assert every output record has `in_vocab is True`. Also assert that a header naming `concepts_v2.jsonl` regrades without `KeyError`.

- [ ] **Step 8: CLI.** In `simready/bench/__main__.py` `main()`, the `run` parser variable is `r`; add:

```python
    r.add_argument("--arm", choices=("dsl-v1", "dsl-v2", "build123d"), default="dsl-v1")
    r.add_argument("--concepts", default=None, help="concept file (default concepts_v1.jsonl)")
```

In `_run`, replace the run-id line (`__main__.py:58`) with a deterministic id — no timestamp, so re-running the same command resumes the same log:

```python
    concepts = Path(args.concepts) if args.concepts else CONCEPTS_V1
    run_id = args.run_id or (f"{args.model}-{args.arm}-{concepts.stem}-k{args.k}"
                             + (f"-smoke{args.limit}" if args.limit else ""))
```

and pass `arm=args.arm, concepts_path=concepts` to `run_benchmark` (import `CONCEPTS_V1` from `simready.bench.concepts`). SP1's official logs were named `runs-<model>.jsonl.gz` when copied into `docs/validation/`; existing local SP1 run files under `data/bench_runs/` keep their old names and are not resumed by the new id.

- [ ] **Step 9: Run tests + SP1 regression**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_arms.py tests/test_bench_runner.py tests/test_bench_attempt.py tests/test_bench_replay.py tests/test_gen_spec_v2.py -q`
Expected: all pass.

SP1 regression check. The regrade must not move. It takes about 21 minutes per log, so run both logs in parallel in the background, writing outside the repo:

```bash
OUT=$(mktemp -d)
for m in gpt-6.1-sol gemini-4-argon; do
  ~/.venvs/simready-ocp/bin/python -m simready.bench regrade docs/validation/bench_v1/runs-$m.jsonl.gz --out $OUT/regrade-$m.jsonl &
done; wait
for m in gpt-6.1-sol gemini-4-argon; do
  python3 scripts/bench_compare_regrade.py docs/validation/bench_v1/runs-$m.jsonl.gz $OUT/regrade-$m.jsonl | tail -1
done
```

Expected output (`scripts/bench_compare_regrade.py` is committed; it compares `passed`, `partial`, `failure_class`, `fingerprint` and per-check status, and ignores every other field, `features` included):
- `attempts 750, regraded-with-spec 571, differing 0, in-vocab passed 534 -> 534`
- `attempts 750, regraded-with-spec 564, differing 0, in-vocab passed 530 -> 530`

Negative control first: `python3 scripts/bench_compare_regrade.py X X` on either log prints `differing 0`.

- [ ] **Step 10: Commit**

```bash
git add simready/gen/dsl.py simready/bench/prompting.py simready/bench/attempt.py simready/bench/runner.py simready/bench/replay.py simready/bench/__main__.py simready/bench/concepts.py tests/test_bench_arms.py tests/test_bench_runner.py tests/test_bench_replay.py && git commit -m "feat(bench): arm selection (dsl-v1/dsl-v2) pinned in run headers; SP1 hash and regrade unchanged"
```

---

### Task 4: DSL v2 reference specs (positive controls for v2 in-vocab)

**Files:**
- Create: `simready/bench/prompts/reference_specs_v2.json`
- Test: `tests/test_bench_reference_specs_v2.py`

**Interfaces:**
- Consumes: `load_v2_reference_specs()`, `v2_reference_ids()` (Task 3), `dsl.build("v2", spec)`.
- Produces: the JSON map `concept_id -> {"steps": [...]}` for the 21 concepts that are out of vocab in v1 and in vocab in v2: `c022 c026 c033 c034 c037 c040 c041 c042 c043 c047` and `c051 c054 c055 c056 c059 c060 c061 c062 c063 c064 c065`. Not listed: `c044`, `c045`, `c046` (stay out of vocab); every v1 in-vocab concept reuses its v1 `reference_spec`. An entry is one spec, or, for `c060` only, one spec per phrasing (`{"explicit": ..., "engineer": ..., "intent": ...}`), because its explicit bore 8.4–8.6 and engineer bore 8.9–9.1 are disjoint. The JSON is generated by `scripts/bench_reference_specs_v2.py`.

- [ ] **Step 1: Write the failing test** — `tests/test_bench_reference_specs_v2.py`:

```python
"""Positive controls for DSL v2: every v2 in-vocab concept has a v2 spec that
passes its explicit and engineer checks (design E2)."""

from __future__ import annotations

import pytest

from simready.occ_compat import OCC_AVAILABLE

if not OCC_AVAILABLE:
    pytest.skip("OCC bindings not available", allow_module_level=True)

from simready.bench.checker import grade_shape  # noqa: E402
from simready.bench.concepts import CONCEPTS_V1, CONCEPTS_V2, load_concepts, load_v2_reference_specs  # noqa: E402
from simready.gen.dsl import build  # noqa: E402

V2_ONLY = ["c022", "c026", "c033", "c034", "c037", "c040", "c041", "c042", "c043", "c047",
           "c051", "c054", "c055", "c056", "c059", "c060", "c061", "c062", "c063", "c064", "c065"]
CONCEPTS = {c.concept_id: c for c in load_concepts(CONCEPTS_V1) + load_concepts(CONCEPTS_V2)}
FALLBACK = sorted(cid for cid, c in CONCEPTS.items() if c.in_vocab)  # 37 v1 + 4 concepts_v2 = 41


def _assert_passes(concept, spec):
    shape = build("v2", spec)
    for phrasing in PHRASINGS:
        report = grade_shape(shape, getattr(concept.checks, phrasing), concept.solids)
        assert report["gate"]["passed"], (phrasing, report["gate"])
        assert not [c for c in report["checks"] if c["status"] == "fail"], (phrasing, report["checks"])


def test_reference_file_covers_exactly_the_v2_only_concepts():
    assert sorted(load_v2_reference_specs()) == V2_ONLY


def test_v2_in_vocab_is_63_concepts():
    assert len(FALLBACK) == 41 and len(set(FALLBACK) | set(V2_ONLY)) == 62


@pytest.mark.parametrize("cid", V2_ONLY)
def test_v2_reference_spec_passes_all_phrasings(cid):
    _assert_passes(CONCEPTS[cid], load_v2_reference_specs()[cid])


@pytest.mark.parametrize("cid", FALLBACK)
def test_v1_reference_spec_passes_under_the_v2_executor(cid):
    _assert_passes(CONCEPTS[cid], CONCEPTS[cid].reference_spec)
```

(Import `PHRASINGS` from `simready.bench.concepts` as well. Every v2 in-vocab concept, 21 hand-written plus 41 fallbacks, is now built with the v2 executor and graded on all three phrasings, as v1's `tests/test_bench_reference_specs.py` does.)

- [ ] **Step 2: Run to verify failure**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_reference_specs_v2.py -q`
Expected: FAIL, the file does not exist (`[] == [...]`).

- [ ] **Step 3: Write the 21 specs.** Author `simready/bench/prompts/reference_specs_v2.json` concept by concept, reading each concept's explicit prompt and checks (`concepts_v1.jsonl` / `concepts_v2.jsonl`); where explicit and engineer ranges differ, choose values inside both (as v1's `c038` does with tolerance mid-points). Recipe per concept:

| id | recipe |
|---|---|
| c022 | box; one cutter = `cyl` r 2.25 through + `cone` r1 = 2.25 at z = top − 2.25, r2 = 4.5 at the top face, fused; `grid` nx = 3 (20 mm pitch) along the hole line; `cut` |
| c026 | two `box` legs fused; base holes `cyl` axis z; upright holes `cyl` axis y (or x, matching the upright's plane); `grid` per pair; cuts |
| c033 / c034 | `regular_prism` sides 6; `cyl` bore; `cut` |
| c037 | `box`; groove `cyl` axis along the 30 mm width; 2 vertical `cyl`; cuts |
| c040 | disc `cyl`; centre `cyl`; one hole `cyl` + `polar` count 8; cuts |
| c041 | `box`; `fillet` edges `">z"` r 3 |
| c042 | `cyl` axis z; `chamfer` edges `"all"` d 1 |
| c043 | outer `cone` + spout `cyl` fused; inner `cone` + spout bore `cyl` fused; `cut` |
| c044 | **dropped during execution (2026-11-20, user decision):** the frozen bbox check needs all three extents at 30 mm; an axis-aligned hole removes one pole (29.61 mm), so no v2 spec passes. c044 stays out of v2 vocab. |
| c047 | `cyl` axis z; cross `cyl` axis x at mid-length; `cut` |
| c051 | head `cyl` + shank `cyl` fused; `regular_prism` sides 6 socket from the top face; `cut` |
| c054 | pin `cyl` + head `cyl` fused; cross `cyl` axis x 3.5 mm from the free end; `cut` |
| c055 | base `box` + upright `box` + `prism` triangle axis y at mid-width fused; hole `cyl` + `grid` ny = 2; `cut` |
| c056 | `box`; centre `cyl`; ring hole + `polar` count 6; corner hole + `grid` 2 × 2; cuts |
| c059 | `cyl`; `chamfer` `"all"` d 0.5; groove ring = `cyl` r 5 − `cyl` r 4.8 (h 1.1); `cut` |
| c060 | `cyl` OD; bore `cyl`; countersink `cone` (r1 = 4.25 at depth 3.75, r2 = 8 at the face); fuse cutters; `cut` |
| c061 | `cyl` + `sphere` (centre on the top face) fused; trim box below z = 0 cut; blind `cyl`; `cut` |
| c062 | tube = `cyl` − `cyl`; cross `cyl` axis x and axis y at mid-length; cuts |
| c063 | base `box` + pedestal `box` + boss `cyl` axis y fused; bore `cyl` axis y; base hole + `grid` nx = 2; cuts |
| c064 | outer `box` − inner `box`; post `cyl` + `grid` 2 × 2 fused; pilot `cyl` + `grid` 2 × 2; `cut` |
| c065 | `box`; `cyl` axis x, `cyl` axis y, `cyl` axis z placed as in `scripts/bench_concepts_v2.py` `_c065`; cuts |

Two worked entries (copy their style):

```json
{
  "c041": {"steps": [
    {"op": "box", "dx": 80, "dy": 50, "dz": 10},
    {"op": "fillet", "a": 0, "r": 3, "edges": ">z"}]},
  "c040": {"steps": [
    {"op": "cyl", "r": 50, "h": 10},
    {"op": "cyl", "r": 15, "h": 10},
    {"op": "cut", "a": 0, "b": 1},
    {"op": "cyl", "r": 4.5, "h": 10, "at": [37.5, 0, 0]},
    {"op": "polar", "of": 3, "count": 8, "center": [0, 0, 0]},
    {"op": "cut", "a": 2, "b": 4}]}
}
```

Validate each entry as you add it:
Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_reference_specs_v2.py -q -k <cid>`
Expected: that concept passes. A spec that cannot be made to pass with the documented op semantics is a finding about DSL v2 (report it to the user), not a reason to edit a frozen check.

- [ ] **Step 4: Run all**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_reference_specs_v2.py tests/test_bench_reference_specs.py -q`
Expected: 64 (2 + 21 + 41) + 37 passed.

- [ ] **Step 5: Commit**

```bash
git add simready/bench/prompts/reference_specs_v2.json tests/test_bench_reference_specs_v2.py && git commit -m "feat(bench): DSL v2 reference specs for 21 concepts (v2 in-vocab positive controls)"
```

---

### Task 5: build123d arm — prompt, code extraction, AST gate (pure)

**Files:**
- Create: `simready/bench/code_arm.py`
- Test: `tests/test_bench_code_arm.py`

**Interfaces:**
- Produces: `CODE_SYSTEM_PROMPT: str`; `extract_code(content: str | None) -> str | None` (the last fenced ```python block, else `None`); `gate_code(code: str) -> list[str]` (empty list = allowed; otherwise human-readable rejections).

- [ ] **Step 1: Write the failing tests** — `tests/test_bench_code_arm.py`:

```python
from __future__ import annotations

import pytest

from simready.bench.code_arm import CODE_SYSTEM_PROMPT, extract_code, gate_code

OK = """from build123d import *
import math
with BuildPart() as p:
    Box(42, 42, 5)
    Hole(radius=11.25)
part = p.part
"""


def test_extract_last_python_block():
    text = f"Plan first.\n```python\nx = 1\n```\nFinal:\n```python\n{OK}```\n"
    assert extract_code(text) == OK
    assert extract_code("no code here") is None
    assert extract_code(None) is None


def test_allowed_code_passes_gate():
    assert gate_code(OK) == []


@pytest.mark.parametrize("bad", [
    "import os\npart = None",
    "from subprocess import run\npart = None",
    "open('x', 'w')\npart = None",
    "exec('1')\npart = None",
    "__import__('os')\npart = None",
    "x = (1).__class__\npart = None",
    "getattr(math, 'pi')\npart = None",
    "async def f():\n    pass\npart = None",
    "import build123d.exporters as e\npart = None",
    "x = '{0.__class__}'.format(1)\npart = None",
    "x = '{a}'.format_map({'a': 1})\npart = None",
    "from build123d import import_step\npart = import_step('/home/u/.env')",
    "import build123d\npart = build123d.export_stl(None, '/tmp/x')",
    "from build123d import *\npart = import_svg('/etc/passwd')",
])
def test_gate_rejects(bad):
    assert gate_code(bad)


def test_syntax_error_is_rejected_not_raised():
    assert gate_code("def (:")


def test_prompt_states_contract():
    assert "part" in CODE_SYSTEM_PROMPT and "build123d" in CODE_SYSTEM_PROMPT and "millimetres" in CODE_SYSTEM_PROMPT
```

- [ ] **Step 2: Run to verify failure**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_code_arm.py -q`
Expected: FAIL, module missing.

- [ ] **Step 3: Implement** `simready/bench/code_arm.py`:

```python
"""Free-form build123d arm (design E4): prompt, code extraction, AST gate.

The gate is a first filter, not the sandbox: code_exec.py still runs the code
in a separate venv child with rlimits and no secrets (ADR 0005).
"""

from __future__ import annotations

import ast
import re

CODE_SYSTEM_PROMPT = (
    "You design mechanical parts as solid models with the build123d Python library. Answer each "
    "request with exactly one fenced ```python code block that builds the requested part and assigns "
    "the final solid to a variable named part; dimensions are in millimetres. Use only "
    "`from build123d import ...` / `import build123d` and `import math`; no file, network or OS access. "
    "Make sensible engineering choices for anything the request leaves open. If the part cannot be "
    "built, say so instead of writing code."
)

_BLOCK = re.compile(r"```(?:python|py)[ \t]*\n(.*?)```", re.DOTALL)
_ALLOWED_MODULES = {"build123d", "math"}
_FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars",
                    "getattr", "setattr", "delattr", "input", "breakpoint", "memoryview"}
# str.format / format_map reach attributes through the format string ("{0.__class__}"),
# which no Attribute node shows; build123d's import_*/export_* read and write arbitrary paths.
_FORBIDDEN_ATTRS = {"format", "format_map"}


def _forbidden_identifier(name: str) -> bool:
    return name.startswith(("_", "import_", "export_"))


def extract_code(content: str | None) -> str | None:
    if not content:
        return None
    blocks = _BLOCK.findall(content)
    return blocks[-1] if blocks else None


def gate_code(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"syntax error: {exc.msg} (line {exc.lineno})"]
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in _ALLOWED_MODULES:
                    errors.append(f"line {node.lineno}: import {alias.name} is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if node.module not in _ALLOWED_MODULES or node.level:
                errors.append(f"line {node.lineno}: from {node.module} import is not allowed")
            for alias in node.names:
                if _forbidden_identifier(alias.name):
                    errors.append(f"line {node.lineno}: importing {alias.name} is not allowed")
        elif isinstance(node, ast.Name) and (node.id in _FORBIDDEN_NAMES or _forbidden_identifier(node.id)):
            errors.append(f"line {node.lineno}: name {node.id} is not allowed")
        elif isinstance(node, ast.Attribute) and (node.attr in _FORBIDDEN_ATTRS or _forbidden_identifier(node.attr)):
            errors.append(f"line {node.lineno}: attribute {node.attr} is not allowed")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith)):
            errors.append(f"line {node.lineno}: async code is not allowed")
    return errors
```

- [ ] **Step 4: Run tests**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_code_arm.py tests/test_bench_arms.py -q`
Expected: all pass. Add to `tests/test_bench_arms.py`: `assert system_prompt_sha256("build123d") not in (SP1_HASH, system_prompt_sha256("dsl-v2"))`.

- [ ] **Step 5: Commit**

```bash
git add simready/bench/code_arm.py tests/test_bench_code_arm.py tests/test_bench_arms.py && git commit -m "feat(bench): build123d arm prompt, code extraction and AST gate"
```

---

### Task 6: ADR 0005 and the build123d sandbox (venv approval gate)

**Files:**
- Create: `docs/adr/0005-bench-free-form-code-arm.md`
- Create: `simready/bench/_b123d_child.py`, `simready/bench/code_exec.py`
- Test: `tests/test_bench_code_exec.py`

**Interfaces:**
- Consumes: `gate_code` (Task 5).
- Produces: `B123D_PYTHON: Path` (default `~/.venvs/simready-b123d/bin/python`, override env `SIMREADY_B123D_PYTHON`); `run_code(code: str, timeout_s: float = 90.0, python: Path | None = None) -> dict` with `{"stage": "built", "step_path": str, "workdir": TemporaryDirectory}` or `{"stage": "build_error" | "timeout" | "infra_error", "error": str}`; the caller owns `workdir` and calls `.cleanup()`.

- [ ] **Step 1: ADR.** Write `docs/adr/0005-bench-free-form-code-arm.md` with: Status Accepted (2026-11-20), Context (D1 deferred Option C to a measured comparison; ADR 0001 forbids exec in the product), Decision (benchmark-only arm; dedicated venv; AST gate; child limits: `python -I`, empty temp cwd, env only `PATH`, `HOME`=temp dir, `PYTHONNOUSERSITE=1`; `RLIMIT_CPU` 60 s, `RLIMIT_AS` 4 GiB, `RLIMIT_FSIZE` 64 MiB, `RLIMIT_CORE` 0; 90 s wall clock; output exactly `part.step`), Consequences:
  - **No network isolation.** `kernel.apparmor_restrict_unprivileged_userns = 1`, `unshare -rn` fails, and bwrap/docker are not installed.
  - **No filesystem isolation.** The child runs as the user, so it can read anything the user can, the repo `.env` included. The AST gate removes the direct routes: `open`, dunder access, `str.format`/`format_map`, and build123d's `import_*`/`export_*` path functions. A gate is a filter, not a jail, so this risk is accepted, not removed.
  - The risk is acceptable because the code comes from the benchmarked models, not from users, and every answer is logged and reviewable.
  - The arm is never wired into the copilot, and ADR 0001 stays in force for the product.
  - Revisit if the arm ever runs untrusted prompts., Alternatives (docker `--network none`: needs sudo and a system dependency; Kaggle/Colab: slow, not reproducible, the local model does not fit).

- [ ] **Step 2: Create the venv (user approval required).** Ask the user, then:

```bash
python3 -m venv ~/.venvs/simready-b123d
~/.venvs/simready-b123d/bin/python -m pip install "build123d==0.13.0"
~/.venvs/simready-b123d/bin/python -c "import build123d, OCP; print(build123d.__version__)"
```

Expected last line: `0.13.0`.

- [ ] **Step 3: Write the failing tests** — `tests/test_bench_code_exec.py`:

```python
"""Sandboxed build123d execution. Skips without the dedicated venv."""

from __future__ import annotations

import pytest

from simready.bench.code_exec import B123D_PYTHON, run_code

if not B123D_PYTHON.exists():
    pytest.skip(f"build123d venv missing: {B123D_PYTHON}", allow_module_level=True)

PLATE = "from build123d import *\nwith BuildPart() as p:\n    Box(40, 30, 5)\npart = p.part\n"


def test_builds_a_step():
    r = run_code(PLATE)
    try:
        assert r["stage"] == "built", r
        assert r["step_path"].endswith("part.step")
    finally:
        r.get("workdir") and r["workdir"].cleanup()


def test_missing_part_is_build_error():
    r = run_code("from build123d import *\nx = Box(1, 1, 1)\n")
    assert r["stage"] == "build_error" and "part" in r["error"]


def test_exception_is_build_error():
    r = run_code("import math\npart = 1 / 0\n")
    assert r["stage"] == "build_error" and "ZeroDivisionError" in r["error"]


def test_child_gets_only_the_scrubbed_env(monkeypatch):
    import subprocess
    from simready.bench import code_exec
    monkeypatch.setenv("DLAB_API_KEY", "sentinel")
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        raise subprocess.TimeoutExpired(cmd, 0)

    monkeypatch.setattr(code_exec.subprocess, "run", fake_run)
    code_exec.run_code("import math\npart = None\n")
    assert set(seen["env"]) == {"PATH", "HOME", "PYTHONNOUSERSITE"}
    assert "sentinel" not in seen["env"].values()
    assert "preexec_fn" not in seen  # limits are set inside the child, never via preexec_fn (thread-unsafe)


def test_cpu_limit_is_set_inside_the_child():
    r = run_code("import math\nwhile True:\n    math.sqrt(2)\n", timeout_s=120)
    assert r["stage"] == "timeout"  # RLIMIT_CPU 60 s fires (SIGXCPU) before the 120 s wall clock


def test_timeout_kills():
    r = run_code("import math\nwhile True:\n    math.sqrt(2)\n", timeout_s=3)
    assert r["stage"] == "timeout"
```

(The env test fails if the `env=` argument is removed, or if the limits go back to `preexec_fn`. That makes it a real check, not a restatement of `_child_env`. `test_cpu_limit_is_set_inside_the_child` takes about 60 s; mark it `@pytest.mark.slow` if the repo has that marker, and check `pyproject.toml` `[tool.pytest.ini_options]` before using it.)

- [ ] **Step 4: Implement** `simready/bench/_b123d_child.py` (runs inside the build123d venv; imports nothing from simready):

```python
"""Child entry point for the build123d arm. argv: code_path out_step_path. Exit 0 = STEP written.

Resource limits are set here, before the answer runs, not through
subprocess preexec_fn: the parent calls run_code from runner worker threads,
where preexec_fn can deadlock the child before exec.
"""

import resource
import sys

_GIB = 1024 ** 3
LIMITS = {
    resource.RLIMIT_CPU: (60, 60),
    resource.RLIMIT_AS: (4 * _GIB, 4 * _GIB),
    resource.RLIMIT_FSIZE: (64 * 1024 ** 2, 64 * 1024 ** 2),
    resource.RLIMIT_CORE: (0, 0),
}


def main() -> int:
    for which, value in LIMITS.items():
        resource.setrlimit(which, value)
    code_path, out_path = sys.argv[1], sys.argv[2]
    with open(code_path, encoding="utf-8") as f:
        code = f.read()
    namespace = {"__name__": "answer"}
    try:
        exec(compile(code, "answer.py", "exec"), namespace)
    except BaseException as exc:  # noqa: BLE001 — every failure is the answer's
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    part = namespace.get("part")
    if part is None:
        print("the code did not assign a solid to 'part'", file=sys.stderr)
        return 2
    import build123d

    if not isinstance(part, build123d.Shape):
        print(f"'part' is a {type(part).__name__}, not a build123d shape", file=sys.stderr)
        return 2
    try:
        ok = build123d.export_step(part, out_path)
    except BaseException as exc:  # noqa: BLE001
        print(f"STEP export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    return 0 if ok is not False else 3


if __name__ == "__main__":
    raise SystemExit(main())
```

`simready/bench/code_exec.py`:

```python
"""Run gated model code in the dedicated build123d venv (ADR 0005)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

B123D_PYTHON = Path(os.environ.get("SIMREADY_B123D_PYTHON", str(Path.home() / ".venvs/simready-b123d/bin/python")))
CHILD = Path(__file__).resolve().parent / "_b123d_child.py"  # sets its own rlimits (thread-safe)


def _child_env(home: str) -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin", "HOME": home, "PYTHONNOUSERSITE": "1"}


def run_code(code: str, timeout_s: float = 90.0, python: Path | None = None) -> dict:
    python = python or B123D_PYTHON
    if not python.exists():
        return {"stage": "infra_error", "error": f"build123d venv missing: {python}"}
    workdir = tempfile.TemporaryDirectory(prefix="simready-b123d-")
    code_path = Path(workdir.name) / "answer.py"
    code_path.write_text(code, encoding="utf-8")
    step = Path(workdir.name) / "part.step"
    try:
        proc = subprocess.run(
            [str(python), "-I", str(CHILD), str(code_path), str(step)],
            cwd=workdir.name, env=_child_env(workdir.name),
            capture_output=True, text=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        workdir.cleanup()
        return {"stage": "timeout", "error": f"code ran longer than {timeout_s:g} s"}
    except OSError as exc:
        workdir.cleanup()
        return {"stage": "infra_error", "error": f"{type(exc).__name__}: {exc}"}
    if proc.returncode == 0 and step.exists() and step.stat().st_size > 0:
        return {"stage": "built", "step_path": str(step), "workdir": workdir}
    workdir.cleanup()
    tail = (proc.stderr or "").strip().splitlines()[-1:] or [f"exit code {proc.returncode}"]
    if proc.returncode < 0:  # killed by a signal: rlimit CPU (SIGXCPU) counts as timeout
        return {"stage": "timeout", "error": f"child killed by signal {-proc.returncode}"}
    return {"stage": "build_error", "error": tail[0][:500]}
```

- [ ] **Step 5: Run tests**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_code_exec.py -q`
Expected: all pass. If `test_builds_a_step` fails with `MemoryError` or an import error, the 4 GiB `RLIMIT_AS` is too small for OCP. Print the child's stderr, raise the limit to 8 GiB in both `_b123d_child.py` `LIMITS` and the ADR, then re-run.

- [ ] **Step 6: Commit**

```bash
git add docs/adr/0005-bench-free-form-code-arm.md simready/bench/_b123d_child.py simready/bench/code_exec.py tests/test_bench_code_exec.py && git commit -m "feat(bench): sandboxed build123d execution in a dedicated venv (ADR 0005)"
```

---

### Task 7: build123d arm in the grader and runner

**Files:**
- Modify: `simready/bench/attempt.py`, `simready/bench/runner.py`, `simready/bench/replay.py`
- Test: `tests/test_bench_code_attempt.py`

**Interfaces:**
- Consumes: `extract_code`, `gate_code` (Task 5), `run_code` (Task 6).
- Produces: `grade_step(step_path: str, checks: list, expected_solids: int = 1, timeout_s: float = GRADE_TIMEOUT_S) -> dict` (same result protocol as `grade_spec`); `evaluate_code_reply(content: str | None, checks: list, expected_solids: int, run=run_code, grade=grade_step) -> dict` returning the same keys as `evaluate_reply` plus `"code"`; `run_benchmark(arm="build123d")` works end to end; `regrade` re-runs logged `code`.

- [ ] **Step 1: Write the failing tests** — `tests/test_bench_code_attempt.py` (no venv needed: `run` and `grade` are injected):

```python
from __future__ import annotations

from simready.bench.attempt import F1, F2, F4, F8, evaluate_code_reply

GOOD = "```python\nfrom build123d import *\npart = Box(1, 1, 1)\n```"


def fake_run(stage, **extra):
    class _W:
        def cleanup(self):
            pass
    return lambda code, timeout_s=90.0: {"stage": stage, "step_path": "/x/part.step", "workdir": _W(), **extra}


def graded(passed):
    report = {"passed": passed, "partial": 1.0 if passed else 0.0, "failure_class": None if passed else "F6_dimension_miss",
              "checks": [], "gate": {"passed": True}}
    return lambda path, checks, solids: {"stage": "graded", "fingerprint": {"volume": 1.0}, "report": report}


def test_no_block_is_f1():
    assert evaluate_code_reply("I cannot.", [], 1, run=fake_run("built"), grade=graded(True))["failure_class"] == F1


def test_gate_rejection_is_f2():
    out = evaluate_code_reply("```python\nimport os\npart=None\n```", [], 1, run=fake_run("built"), grade=graded(True))
    assert out["failure_class"] == F2 and out["schema_errors"]


def test_build_error_and_timeout():
    assert evaluate_code_reply(GOOD, [], 1, run=fake_run("build_error", error="boom"), grade=graded(True))["failure_class"] == F4
    assert evaluate_code_reply(GOOD, [], 1, run=fake_run("timeout", error="slow"), grade=graded(True))["failure_class"] == F8


def test_graded_pass_keeps_code():
    out = evaluate_code_reply(GOOD, [], 1, run=fake_run("built"), grade=graded(True))
    assert out["passed"] is True and out["code"].startswith("from build123d")


def test_grader_exception_is_excluded_not_raised():
    def boom(path, checks, solids):
        raise RuntimeError("grader bug")
    out = evaluate_code_reply(GOOD, [], 1, run=fake_run("built"), grade=boom)
    assert out["failure_class"] == "checker_error" and out["passed"] is None


def test_corrupt_step_is_build_error(tmp_path):
    from simready.occ_compat import OCC_AVAILABLE
    if not OCC_AVAILABLE:
        pytest.skip("OCC bindings not available")
    from simready.bench.attempt import grade_step
    bad = tmp_path / "part.step"
    bad.write_text("ISO-10303-21;\nnot a step file\n", encoding="utf-8")
    result = grade_step(str(bad), [], 1)
    assert result["stage"] == "build_error" and result["error_type"] == "step_read"
```

(Add `import pytest` at the top of the file.)

- [ ] **Step 2: Run to verify failure**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_code_attempt.py -q`
Expected: FAIL, `ImportError: cannot import name 'evaluate_code_reply'`.

- [ ] **Step 3: Implement.** In `simready/bench/attempt.py`:

1. Generalize the worker's source: `_grade_worker(source: dict, checks_json, expected_solids, out_queue)` where `source` is `{"kind": "spec", "spec": ..., "dsl": "v1"|"v2"}` or `{"kind": "step", "path": ...}`. This breaks existing callers, so update them in the same task:
   - The four direct calls `attempt._grade_worker(spec, checks, solids, out)` in `tests/test_bench_attempt.py` (lines 258, 271, 380, 407) become `attempt._grade_worker({"kind": "spec", "spec": spec, "dsl": "v1"}, checks, solids, out)`.
   - The monkeypatched fake workers in that file (around lines 255–306 and 358) keep their 4-parameter shape; rename the first parameter to `source` where the body reads it.
   - Grep the tests for `_grade_worker` and `_spawn_grade` before editing (`grep -n "_grade_worker\|_spawn_grade" tests/*.py`), and update every hit.

   The spec branch is the Task 3 code. The step branch runs **after** the worker has put `{"stage": "ready"}`, so a slow read counts toward the model's F8 budget, not infra. It runs inside the build `try`. Add an explicit `except ValueError as exc:` before the generic handler that puts `{"stage": "build_error", "error_type": "step_read", "error": ...}`, because the generic handler maps non-native exceptions to `checker_error`. The read itself:

```python
def _read_step(path: str):
    from simready.occ_compat import IFSelect_RetDone, STEPControl_Reader
    reader = STEPControl_Reader()
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise ValueError(f"STEP read failed: {path}")
    reader.TransferRoots()
    return reader.OneShape()
```

A `ValueError` from `_read_step` is a `build_error` (the model's code wrote an unreadable file). `grade_spec` builds `{"kind": "spec", ...}`; new:

```python
def grade_step(step_path: str, checks: list, expected_solids: int = 1, timeout_s: float = GRADE_TIMEOUT_S) -> dict:
    with tempfile.TemporaryDirectory(prefix="simready-grade-") as directory:
        return _spawn_grade({"kind": "step", "path": step_path}, checks, expected_solids, timeout_s, _GradeMailbox(directory))
```

2. Add:

```python
def evaluate_code_reply(content, checks, expected_solids, run=None, grade=grade_step) -> dict:
    from simready.bench.code_arm import extract_code, gate_code
    if run is None:
        from simready.bench.code_exec import run_code as run
    out = {"via": "text", "n_tool_calls": 0, "spec": None, "code": None, "schema_errors": [], "build_error": None,
           "fingerprint": None, "check_report": None, "partial": 0.0, "passed": False, "failure_class": None,
           "error": None, "error_type": None}
    code = extract_code(content)
    if code is None:
        out.update(failure_class=F1, schema_errors=["no fenced python block"])
        return out
    out["code"] = code
    errors = gate_code(code)
    if errors:
        out.update(failure_class=F2, schema_errors=errors)
        return out
    built = run(code)
    if built["stage"] != "built":
        cls = {"build_error": F4, "timeout": F8}.get(built["stage"], INFRA)
        out.update(failure_class=cls, error=built["error"], error_type=built["stage"])
        if cls == INFRA:
            out.update(partial=None, passed=None)
        else:
            out["build_error"] = built["error"]
        return out
    try:
        result = validate_grade_result(grade(built["step_path"], checks, expected_solids))
    except Exception as exc:  # same guard as evaluate_reply: a grader bug never kills the run
        result = {"stage": CHECKER_ERROR, "error_type": "grader_exception", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        built["workdir"].cleanup()
    if result["stage"] != "graded":
        cls = {"build_error": F4, "timeout": F8, CHECKER_ERROR: CHECKER_ERROR}.get(result["stage"], INFRA)
        out.update(failure_class=cls, error=result["error"], error_type=result.get("error_type"))
        if cls in (INFRA, CHECKER_ERROR):
            out.update(partial=None, passed=None)
        return out
    report = result["report"]
    out.update(fingerprint=result["fingerprint"], check_report=report, partial=report["partial"],
               passed=report["passed"], failure_class=report["failure_class"])
    return out
```

3. `runner.py`: remove the `NotImplementedError`; in `work()`, for `arm == "build123d"` call `evaluate_code_reply(reply["content"], checks, item.concept.solids)` instead of `parse_reply` + `evaluate_reply`.
4. `replay.py`: for `arm == "build123d"`, `regrade` re-runs `evaluate_code_reply(att["response"]["content"], ...)`; `replay` compares the rebuilt fingerprint the same way as for specs.

- [ ] **Step 4: Run tests**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_code_attempt.py tests/test_bench_attempt.py tests/test_bench_code_exec.py tests/test_bench_runner.py tests/test_bench_replay.py -q`
Expected: all pass, with `tests/test_bench_attempt.py` edited as in Step 3.1. Then rerun the Task 3 SP1 regression (both logs must print `differing 0`), because the worker changed.

- [ ] **Step 5: End-to-end smoke without an API** — grade a hand-written build123d answer for `c001/explicit` through `evaluate_code_reply` with the real venv:

```bash
~/.venvs/simready-ocp/bin/python - <<'EOF'
from simready.bench.attempt import evaluate_code_reply
from simready.bench.concepts import load_concepts
c = load_concepts()[0]
ans = """```python
from build123d import *
with BuildPart() as p:
    Box(42, 42, 5)
    Hole(radius=11.25)
    with Locations((15.5, 15.5), (-15.5, 15.5), (15.5, -15.5), (-15.5, -15.5)):
        Hole(radius=1.7)
part = p.part
```"""
out = evaluate_code_reply(ans, c.checks.explicit, c.solids)
print(out["failure_class"], out["passed"], [x["status"] for x in out["check_report"]["checks"]])
EOF
```

Expected: `None True ['pass', 'pass', 'pass']`.

- [ ] **Step 6: Commit**

```bash
git add simready/bench/attempt.py simready/bench/runner.py simready/bench/replay.py tests/test_bench_code_attempt.py tests/test_bench_attempt.py && git commit -m "feat(bench): build123d arm graded by the unchanged checker"
```

---

### Task 8: Repair pass with measured, leak-free feedback

**Files:**
- Modify: `simready/bench/attempt.py` (worker adds `features` to graded results)
- Create: `simready/bench/repair.py`
- Modify: `simready/bench/__main__.py` (`repair` subcommand)
- Test: `tests/test_bench_repair.py`

**Interfaces:**
- Consumes: `grade_spec`, `grade_step`, `evaluate_reply`, `evaluate_code_reply`, `build_messages`, `bench_tool`, `dsl_of`.
- Produces:
  - graded results gain `"features": [{"diameter": float, "kind": "hole"|"boss", "through": bool|None, "length": float}]`, stored on the attempt record as `features`.
  - `feedback_text(record: dict, features: list[dict] | None) -> str`.
  - `repair_run(run_path, out_path, client, model_id, max_rounds=2, concepts_paths=(CONCEPTS_V1, CONCEPTS_V2)) -> RepairSummary` writes a log whose header copies the source header plus `"repair_of"` and `"max_rounds"`. It writes one record per round, with `attempt_id` = `<source attempt_id>/repair<round>`, `repair_of_attempt`, `round` (1 or 2) and the usual outcome fields. It is sequential (no `workers`), resumable, and refuses a `model_id` that differs from the source header's `model`.
  - `RepairSummary(path: Path, repaired: int, infra_errors: int, stopped_reason: str | None)`.
  - CLI: `python -m simready.bench repair RUN --out OUT --model ALIAS [--max-rounds 2]`.

- [ ] **Step 1: Write the failing tests** — `tests/test_bench_repair.py`:

```python
from __future__ import annotations

import re

from simready.bench.concepts import CONCEPTS_V1, load_concepts
from simready.bench.repair import feedback_text

# Shaped on the SP1 failure c027/explicit/0 (gpt-6.1-sol, bench_v1.md 7.1): extents and check
# details as logged there; volume, face and edge counts are illustrative.
C027 = {c.concept_id: c for c in load_concepts(CONCEPTS_V1)}["c027"]
DIM_MISS = {
    "failure_class": "F6_dimension_miss",
    "fingerprint": {"volume": 21155.2, "extents": [40.0, 45.0, 50.0], "solids": 1, "faces": 16, "edges": 40, "area": 1.0},
    "check_report": {"gate": {"passed": True, "reason": ""}, "checks": [
        {"type": "bbox_sorted", "status": "fail", "detail": "extents [40.0, 45.0, 50.0] vs [(39.9, 40.1), (39.9, 40.1), (49.9, 50.1)]"},
        {"type": "hole_set", "status": "pass", "detail": "pairwise distances [25.0] vs [(24.9, 25.1)]"}]},
    "schema_errors": [], "build_error": None,
}
FEATURES = [{"diameter": 5.5, "kind": "hole", "through": True, "length": 5.0}]


def _bounds(checks) -> set[str]:
    """Every numeric bound in the concept's checks, as the strings a leak would print."""
    out: set[str] = set()

    def walk(x):
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            out.update({f"{x:g}", f"{float(x):.1f}", f"{float(x):.3f}"})
        elif isinstance(x, (list, tuple)):
            for y in x:
                walk(y)
        elif isinstance(x, dict):
            for k, y in x.items():
                if k not in ("type", "what", "through"):
                    walk(y)
    for ch in checks:
        walk(ch.model_dump())
    return out


def test_feedback_reports_measurements():
    text = feedback_text(DIM_MISS, FEATURES)
    assert "F6_dimension_miss" in text and "40.0 x 45.0 x 50.0" in text and "5.5" in text and "21155" in text


def test_feedback_never_leaks_target_ranges_or_details():
    text = feedback_text(DIM_MISS, FEATURES)
    numbers = set(re.findall(r"\d+(?:\.\d+)?", text))
    measured = {"40.0", "45.0", "50.0", "5.5", "5.0", "21155", "1", "6"}  # the part's own values and the class id
    leaked = (numbers - measured) & _bounds(C027.checks.explicit)
    assert not leaked, leaked
    assert " vs " not in text and "bbox_sorted" not in text and "hole_set" not in text


def test_schema_and_build_errors_are_passed_through():
    rec = {"failure_class": "F4_build_error", "build_error": "Standard_ConstructionError: fillet failed",
           "schema_errors": [], "fingerprint": None, "check_report": None}
    assert "fillet failed" in feedback_text(rec, None)
```

(The bounds come from the real `c027` explicit checks, not literals. A measured value can equal a bound by coincidence: 40.0 is both the part's height and the target's nominal. So the measured values are subtracted first, and only a bound that is not a measurement counts as a leak. Negative control: temporarily append `record["check_report"]["checks"][0]["detail"]` to the text returned by `feedback_text`, run the test, see it fail on `39.9`/`40.1`, then revert. This is Working Rule 9.)

- [ ] **Step 2: Run to verify failure**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_repair.py -q`
Expected: FAIL, module missing.

- [ ] **Step 3: Implement features.** In `_grade_worker` after `grade_shape`, add to the graded payload:

```python
        feats = [{"diameter": round(f.diameter, 3), "kind": "hole" if f.concave else "boss",
                  "through": f.through, "length": round(f.depth, 3)}
                 for f in geo.cylindrical_features(shape) if f.full]
        out_queue.put({"stage": "graded", "fingerprint": fingerprint(shape), "report": report, "features": feats})
```

(`from simready.bench import geometry as geo` inside the worker's import block.) `evaluate_reply` and `evaluate_code_reply` copy `result.get("features")` into `out["features"]`. Regrade of SP1 logs adds a `features` field only; the compare script ignores it — re-run Task 3's SP1 regression to confirm `differing 0`.

- [ ] **Step 4: Implement** `simready/bench/repair.py`:

```python
"""Repair pass (design E5): feed back only what was measured on the model's own
part, up to two rounds, logged apart from single-shot.

Never sent: target ranges, the check list, check ``detail`` strings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from simready.bench import runlog
from simready.bench.attempt import INFRA, evaluate_code_reply, evaluate_reply, grade_spec, parse_reply
from simready.bench.concepts import CONCEPTS_V1, CONCEPTS_V2, load_concepts
from simready.bench.providers import InfraError, QuotaExhausted
from simready.bench.prompting import bench_tool, build_messages, dsl_of
from simready.bench.runner import MAX_CONSECUTIVE_INFRA, TEMPERATURE

PRE_BUILD = {"F1_no_parse", "F2_schema", "F3_reference", "F9_out_of_vocab"}


def _fmt(x: float) -> str:
    return f"{x:.1f}"


def feedback_text(record: dict, features: list[dict] | None) -> str:
    cls = record.get("failure_class")
    lines = [f"Your part was rejected: {cls}."]
    if cls in PRE_BUILD:
        lines += [f"- {e}" for e in record.get("schema_errors") or []]
    elif cls in ("F4_build_error", "F8_timeout"):
        lines.append(f"- {record.get('build_error') or record.get('error')}")
    else:
        gate = (record.get("check_report") or {}).get("gate") or {}
        if gate.get("reason"):
            lines.append(f"- solid check: {gate['reason']}")
        fp = record.get("fingerprint") or {}
        if fp.get("extents"):
            lines.append("- bounding box: " + " x ".join(_fmt(e) for e in fp["extents"]) + " mm")
        if fp.get("volume") is not None:
            lines.append(f"- volume: {fp['volume']:.0f} mm^3, solids: {fp.get('solids')}")
        for f in features or []:
            through = "" if f["kind"] == "boss" else (" through" if f["through"] else " blind")
            lines.append(f"- {f['kind']}{through}: diameter {_fmt(f['diameter'])} mm, length {_fmt(f['length'])} mm")
    lines.append("Compare these measurements with the request and answer again with a corrected part.")
    return "\n".join(lines)


def _previous_turn(record: dict) -> dict:
    resp = record.get("response") or {}
    if record.get("spec") is not None and resp.get("tool_calls"):
        return {"role": "assistant", "content": "build_part(" + json.dumps({"spec": record["spec"]}) + ")"}
    return {"role": "assistant", "content": resp.get("content") or ""}


@dataclass
class RepairSummary:
    path: Path
    repaired: int
    infra_errors: int
    stopped_reason: str | None


def _done_rounds(out_path: Path) -> dict[str, list[dict]]:
    """Scored repair records already in the log, by source attempt (resume)."""
    done: dict[str, list[dict]] = {}
    for rec in runlog.attempts(out_path):
        if rec.get("failure_class") not in runlog.EXCLUDED_CLASSES:
            done.setdefault(rec["repair_of_attempt"], []).append(rec)
    return done


def repair_run(run_path, out_path, client, model_id: str, max_rounds: int = 2,
               concepts_paths=(CONCEPTS_V1, CONCEPTS_V2)) -> RepairSummary:
    run_path, out_path = Path(run_path), Path(out_path)
    header = runlog.read_header(run_path)
    if model_id != header["model"]:
        raise RuntimeError(f"repair model {model_id!r} differs from the run's model {header['model']!r}")
    arm = header.get("arm", "dsl-v1")
    dsl = dsl_of(arm)
    concepts = {c.concept_id: c for p in concepts_paths for c in load_concepts(p)}
    new_header = {**header, "repair_of": str(run_path), "max_rounds": max_rounds}
    if out_path.exists():
        existing = runlog.read_header(out_path)
        for key in ("repair_of", "max_rounds", "model", "system_prompt_sha256", "prompt_sha256", "checker_version"):
            if existing.get(key) != new_header.get(key):
                raise RuntimeError(f"resume mismatch on {key}: log has {existing.get(key)!r}, now {new_header.get(key)!r}")
    else:
        runlog.append(out_path, new_header)
    done = _done_rounds(out_path)
    tools = [bench_tool(arm)] if bench_tool(arm) is not None else []
    grade = partial(grade_spec, dsl=dsl) if dsl else None
    repaired = infra = consecutive = 0
    for att in runlog.attempts(run_path):
        if att.get("passed") is not False or not att.get("in_vocab"):
            continue  # passed, excluded (None), or out of vocab for this arm: never repaired
        prior = sorted(done.get(att["attempt_id"], []), key=lambda r: r["round"])
        if prior and (prior[-1].get("passed") or prior[-1]["round"] >= max_rounds):
            continue  # finished in an earlier invocation
        concept = concepts[att["concept_id"]]
        checks = getattr(concept.checks, att["phrasing"])
        messages = build_messages(att["prompt"], arm)
        current = att
        for rec in prior:  # rebuild the conversation so far
            messages += [_previous_turn(current), {"role": "user", "content": feedback_text(current, current.get("features"))}]
            current = rec
        for rnd in range(len(prior) + 1, max_rounds + 1):
            features = current.get("features")
            if features is None and current.get("spec") is not None and dsl:
                measured = grade(current["spec"], [], concept.solids)
                features = measured.get("features") if measured.get("stage") == "graded" else None
            turn = messages + [_previous_turn(current), {"role": "user", "content": feedback_text(current, features)}]
            try:
                reply = client.complete(turn, tools, TEMPERATURE, seed=att["attempt_idx"] * 10 + rnd)
            except QuotaExhausted as exc:
                return RepairSummary(out_path, repaired, infra, f"quota exhausted: {exc}")
            except InfraError as exc:
                runlog.append(out_path, {**att, "attempt_id": f"{att['attempt_id']}/repair{rnd}",
                                         "repair_of_attempt": att["attempt_id"], "round": rnd,
                                         "failure_class": INFRA, "passed": None, "partial": None,
                                         "error": str(exc), "error_type": "provider_exception"})
                infra += 1
                consecutive += 1
                if consecutive >= MAX_CONSECUTIVE_INFRA:
                    return RepairSummary(out_path, repaired, infra, f"{MAX_CONSECUTIVE_INFRA} consecutive infra errors")
                break  # retried on resume
            if reply["model_returned"] != model_id:
                return RepairSummary(out_path, repaired, infra,
                                     f"model substituted: asked {model_id!r}, got {reply['model_returned']!r}")
            consecutive = 0
            messages = turn
            if dsl:
                outcome = evaluate_reply(parse_reply(reply["tool_calls"], reply["content"]), checks, concept.solids,
                                         grade=grade, dsl=dsl)
            else:
                outcome = evaluate_code_reply(reply["content"], checks, concept.solids)
            current = {**att, "response": {"content": reply["content"], "tool_calls": reply["tool_calls"]},
                       "usage": reply["usage"], "latency_s": reply["latency_s"], **outcome,
                       "attempt_id": f"{att['attempt_id']}/repair{rnd}",
                       "repair_of_attempt": att["attempt_id"], "round": rnd}
            runlog.append(out_path, current)
            if current.get("passed") or current.get("failure_class") in runlog.EXCLUDED_CLASSES:
                break
        repaired += 1
    return RepairSummary(out_path, repaired, infra, None)
```

(Sequential on purpose. SP1 has 21 failed in-vocab attempts for gpt-6.1-sol and 25 for gemini-4-argon (`bench_v1.md` § 4), Only in-vocab attempts for the log's arm are repaired. An out-of-vocab decline is the right answer, and pushing the model to retry it would measure pressure to fake rather than repair. So SP1's 179 and 184 declines and its 5 and 1 out-of-vocab fakes (§ 5) are skipped. Under `build123d` every concept is in vocab, so every failure is repaired. Parallelize only if a run's measured wall time demands it. An excluded repair round, whether infra or checker error, ends that attempt's repair for this invocation. Because `_done_rounds` skips excluded records, the round is retried on resume.)

- [ ] **Step 5: Add `repair_run` tests** in `tests/test_bench_repair.py`. Use a small local fake client. `tests/test_bench_runner.py`'s `FakeClient` stores only `(prompt, seed)`, so it can't show the feedback message:

```python
class RecordingClient:
    def __init__(self, replies):
        self.replies, self.messages = list(replies), []

    def complete(self, messages, tools, temperature, seed=None):
        self.messages.append(messages)
        return self.replies.pop(0)


def _reply(spec, model="m"):
    return {"tool_calls": [{"name": "build_part", "arguments": json.dumps({"spec": spec})}], "content": None,
            "finish_reason": "tool_calls", "model_returned": model, "usage": {}, "latency_s": 0.1}
```

Write a one-attempt source log: an SP1-style header with `"model": "m"` and `"prompt_file": "concepts_v1.jsonl"`, plus the `DIM_MISS` record above with `attempt_id "c027/explicit/0"`, `concept_id "c027"`, `phrasing "explicit"`, `attempt_idx 0`, `passed False` and the logged spec from `bench_v1.md` § 7.1. Monkeypatch `simready.bench.repair.grade_spec` to a fake that returns `{"stage": "graded", "fingerprint": {...}, "report": {...passed True...}, "features": []}`. Then assert:
- round 1 passes, and the log holds exactly one record with `round == 1` and `passed is True`;
- `client.messages[0][-1]["content"]` contains no bound from `_bounds(C027.checks.explicit)` other than measured values (the same rule as the leak test);
- calling `repair_run` again on the same output appends nothing (resume);
- `repair_run(..., model_id="other")` raises `RuntimeError("repair model ...")`;
- a client reply with `model_returned="x"` stops with `stopped_reason` starting `model substituted`.

- [ ] **Step 6: CLI** — add a `repair` subparser with `run`, `--out`, `--model` and `--max-rounds` (default 2). It builds `ModelClient(load_providers()[args.model])` the way `_run` does, calls `repair_run(..., model_id=provider.model)`, and prints `{path}: repaired {n}, infra errors {k}, stopped: {reason or 'no'}`. It exits 0 only when `stopped_reason is None`.

- [ ] **Step 7: Run tests**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_repair.py tests/test_bench_attempt.py tests/test_bench_runner.py -q`
Expected: all pass. Then rerun the Task 3 SP1 regression (worker changed; both logs `differing 0`).

- [ ] **Step 8: Commit**

```bash
git add simready/bench/attempt.py simready/bench/repair.py simready/bench/__main__.py tests/test_bench_repair.py && git commit -m "feat(bench): repair pass with measured, leak-free feedback"
```

---

### Task 9: Report — arms, paired comparisons, repair

**Files:**
- Modify: `simready/bench/report.py`, `simready/bench/__main__.py`
- Test: `tests/test_bench_report.py`

**Interfaces:**
- Consumes: run logs from Tasks 3, 7, 8 (`arm`, `in_vocab`, `repair_of_attempt`, `round`).
- Produces: `paired_diff(a: ModelRun, b: ModelRun, concept_ids: set[str]) -> dict` (`diff`, `diff_ci`, `n_concepts`; per-concept mean pass@1 difference, paired bootstrap over concepts with the existing `BOOT_SEED`/`N_BOOT`); `subset_p1(run, concept_ids) -> dict` (`p1`, `p1_ci`, `n_concepts`); `repair_summary(single: ModelRun, repair_log: str | Path, concept_ids: set[str]) -> dict` (`p1_single`, `p1_after`, `diff`, `diff_ci`, `n_concepts`, `repaired_attempts`, `fixed_in_round`); concept-id set files in `docs/validation/bench_v2/sets/`; CLI `compare` and `repair-summary` (Step 5).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_bench_report.py`; build `ModelRun` objects from small literal attempt lists, as that file already does):

```python
from simready.bench.report import ModelRun, paired_diff, subset_p1


def _run(passes: dict[str, list[bool]]) -> ModelRun:
    attempts = [{"concept_id": cid, "phrasing": "explicit", "in_vocab": True, "passed": p, "failure_class": None if p else "F6_dimension_miss"}
                for cid, ps in passes.items() for p in ps]
    return ModelRun({"model": "m"}, attempts, 0)


def test_paired_diff_is_per_concept_mean_difference():
    a = _run({"c1": [True, True], "c2": [True, False]})
    b = _run({"c1": [True, False], "c2": [False, False]})
    out = paired_diff(a, b, {"c1", "c2"})
    assert out["diff"] == 0.5 and out["n_concepts"] == 2
    lo, hi = out["diff_ci"]
    assert lo <= 0.5 <= hi


def test_subset_ignores_other_concepts():
    r = _run({"c1": [True], "c2": [False]})
    assert subset_p1(r, {"c1"})["p1"] == 1.0
```

- [ ] **Step 2: Run to verify failure**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_report.py -q`
Expected: FAIL, `ImportError: cannot import name 'paired_diff'`.

- [ ] **Step 3: Implement** in `simready/bench/report.py`:

```python
def _per_concept_p1(run: ModelRun, concept_ids: set[str]) -> dict[str, float]:
    by: dict[str, list[float]] = defaultdict(list)
    for (cid, _), results in _prompts_any(run).items():
        if cid in concept_ids:
            by[cid].append(_mean([float(r) for r in results]))
    return {cid: _mean(v) for cid, v in by.items()}


def _prompts_any(run: ModelRun) -> dict[tuple[str, str], list[bool]]:
    table: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for a in run.attempts:
        table[(a["concept_id"], a["phrasing"])].append(bool(a["passed"]))
    return table


def subset_p1(run: ModelRun, concept_ids: set[str]) -> dict:
    per = _per_concept_p1(run, concept_ids)
    return {"p1": _mean(list(per.values())), "p1_ci": _bootstrap({k: [v] for k, v in per.items()}), "n_concepts": len(per)}


def paired_diff(a: ModelRun, b: ModelRun, concept_ids: set[str]) -> dict:
    pa, pb = _per_concept_p1(a, concept_ids), _per_concept_p1(b, concept_ids)
    common = sorted(set(pa) & set(pb))
    diffs = {cid: [pa[cid] - pb[cid]] for cid in common}
    return {"diff": _mean([d[0] for d in diffs.values()]), "diff_ci": _bootstrap(diffs), "n_concepts": len(common)}
```

Note: `subset_p1` averages per concept (each concept weight 1), while `headline` averages per prompt; state this in the report method section.

```python
def repair_summary(single: ModelRun, repair_log: str | Path, concept_ids: set[str]) -> dict:
    """Single-shot vs after-repair pass@1 on the same attempts (design E5, result 4)."""
    final: dict[str, dict] = {}
    for rec in runlog.attempts(repair_log):
        if rec.get("failure_class") in runlog.EXCLUDED_CLASSES:
            continue
        prev = final.get(rec["repair_of_attempt"])
        if prev is None or rec["round"] > prev["round"]:
            final[rec["repair_of_attempt"]] = rec
    after_attempts = [{**a, "passed": final[a["attempt_id"]]["passed"]} if a["attempt_id"] in final else a
                      for a in single.attempts]
    after = ModelRun(single.header, after_attempts, single.excluded)
    d = paired_diff(after, single, concept_ids)
    return {
        "p1_single": subset_p1(single, concept_ids)["p1"],
        "p1_after": subset_p1(after, concept_ids)["p1"],
        "diff": d["diff"], "diff_ci": d["diff_ci"], "n_concepts": d["n_concepts"],
        "repaired_attempts": len(final),
        "fixed_in_round": Counter(r["round"] for r in final.values() if r["passed"]),
    }
```

Test (append):

```python
def test_repair_summary_uses_last_round(tmp_path):
    single = _run({"c1": [False, True]})
    single.attempts[0]["attempt_id"], single.attempts[1]["attempt_id"] = "c1/explicit/0", "c1/explicit/1"
    log = tmp_path / "rep.jsonl"
    runlog.append(log, {"record": "header"})
    for rnd, ok in ((1, False), (2, True)):
        runlog.append(log, {"record": "attempt", "attempt_id": f"c1/explicit/0/repair{rnd}", "repair_of_attempt": "c1/explicit/0",
                            "round": rnd, "passed": ok, "failure_class": None if ok else "F6_dimension_miss"})
    out = repair_summary(single, log, {"c1"})
    assert out["p1_single"] == 0.5 and out["p1_after"] == 1.0 and out["fixed_in_round"] == {2: 1}
```

`runlog.attempts` keeps only the latest record per `attempt_id` (`runlog.py:38-43`). That is why every repair record carries its own id, `<source attempt_id>/repair<round>`: rounds 1 and 2 must not overwrite each other. An infra-excluded round is replaced by its retry under the same id, as in the runner.

- [ ] **Step 4: Pre-registered concept sets.** These are the denominators of the design's pre-registered results. They are written by code, never by hand. Create `scripts/bench_v2_sets.py`, which writes one concept id per line to `docs/validation/bench_v2/sets/`:

```python
"""Write the SP2 pre-registered concept-id sets (design: Pre-registered results)."""
from pathlib import Path

from simready.bench.concepts import CONCEPTS_V1, CONCEPTS_V2, load_concepts, v2_reference_ids

OUT = Path(__file__).resolve().parents[1] / "docs" / "validation" / "bench_v2" / "sets"
v1 = load_concepts(CONCEPTS_V1)
v2 = load_concepts(CONCEPTS_V2)
v2_vocab = v2_reference_ids()
SETS = {
    "regression": sorted(c.concept_id for c in v1 if c.in_vocab),                       # result 1
    "design": sorted(c.concept_id for c in v1 if not c.in_vocab and c.concept_id in v2_vocab),  # result 2
    "heldout": sorted(c.concept_id for c in v2),                                          # result 2
    "dsl_vs_code": sorted(c.concept_id for c in v1 + v2 if c.concept_id in v2_vocab),    # result 3
    "c044_c045_c046": ["c044", "c045", "c046"],                                           # result 3, apart
}
EXPECTED = {"regression": 37, "design": 10, "heldout": 15, "dsl_vs_code": 62, "c044_c045_c046": 3}
assert {k: len(v) for k, v in SETS.items()} == EXPECTED, {k: len(v) for k, v in SETS.items()}
OUT.mkdir(parents=True, exist_ok=True)
for name, ids in SETS.items():
    (OUT / f"{name}.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
print({k: len(v) for k, v in SETS.items()})
```

Run: `~/.venvs/simready-ocp/bin/python scripts/bench_v2_sets.py`
Expected: `{'regression': 37, 'design': 10, 'heldout': 15, 'dsl_vs_code': 62, 'c044_c045_c046': 3}`. The script's assert fails if Task 4's reference file changes v2 vocab.

- [ ] **Step 5: CLI.** Two subcommands. Each side may list several logs, because one arm's results span the `concepts_v1` and `concepts_v2` logs. A side's logs are pooled as `ModelRun(header=<first log's header>, attempts=<all attempts concatenated>, excluded=<sum>)`. Set files hold one concept id per line.

```
python -m simready.bench compare --a LOG [LOG ...] --b LOG [LOG ...] --concepts SET.txt
python -m simready.bench repair-summary --single LOG [LOG ...] --repair LOG [LOG ...] --concepts SET.txt
```

`compare` prints one markdown row, `| A model/arm | B model/arm | n concepts | A pass@1 | B pass@1 | diff | 95% CI |`. `repair-summary` prints `| model/arm | n | single | after repair | diff | 95% CI | fixed in round 1 / 2 |`.

- [ ] **Step 6: Run tests**

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/test_bench_report.py -q`
Expected: all pass. Then confirm the SP1 report is unchanged:

Run: `~/.venvs/simready-ocp/bin/python -m simready.bench report docs/validation/bench_v1/runs-gpt-6.1-sol.jsonl.gz docs/validation/bench_v1/runs-gemini-4-argon.jsonl.gz | grep -E "96.2%|95.5%"`
Expected: both headline rows print, with the same CIs as `bench_v1.md` § 2.

- [ ] **Step 7: Commit**

```bash
git add simready/bench/report.py simready/bench/__main__.py tests/test_bench_report.py scripts/bench_v2_sets.py docs/validation/bench_v2/sets/ && git commit -m "feat(bench): paired arm comparison, repair summary, pre-registered concept sets"
```

---

### Task 10: Small model — survey, local server, smoke (approval gates)

**Files:**
- Modify: `simready/bench/providers.json`
- Create: `docs/validation/bench_v2/small-model-choice.md`

- [ ] **Step 1: Survey (no install).** List ~3–4B instruct models with (a) Unsloth GRPO support and (b) an official or Unsloth GGUF, (c) a chat template with tool calling that `llama-server --jinja` accepts. Record 3–5 candidates with sources and the pick + reason in `docs/validation/bench_v2/small-model-choice.md`. This also closes the survey half of `sp3-entry-gate` (spec D5 "Open").

- [ ] **Step 2: Approval.** Ask the user to approve: installing `llama-server` (llama.cpp release binary into `~/.local/bin`, or a build), downloading the chosen GGUF (state size), and the quantization (q4_K_M unless the user says otherwise).

- [ ] **Step 3: Serve.** After approval, start detached with a log:

```bash
cd ~/projects/Mech/SimReady
set -a; . ./.env; set +a
nohup llama-server -m ~/models/<file>.gguf --alias <alias> --jinja --host 127.0.0.1 --port 8080 --api-key "$LLAMA_SERVER_KEY" -c 8192 > ~/llama-server.log 2>&1 &
```

(`<alias>` and `<file>` are filled in from Step 1's pick before the command is run or handed to the user. `LLAMA_SERVER_KEY` is any local secret; add it to `.env` first. The `set -a` line exports `.env` into this shell only, so `--api-key` is not empty. The bench reads the same variable through `resolve_key`. Never print the value.)

- [ ] **Step 4: Provider entry.** Add to `simready/bench/providers.json`:

```json
  "<alias>": {"base_url": "http://127.0.0.1:8080/v1", "model": "<alias>", "key_env": "LLAMA_SERVER_KEY",
              "rpm": 0, "max_tokens": 4096, "supports_seed": true, "extra_body": {}}
```

(`rpm: 0` disables the limiter, see `RateLimiter`.)

- [ ] **Step 5: Smoke and timing.**

Run: `~/.venvs/simready-ocp/bin/python -m simready.bench smoke --model <alias>` (VPS, repo root)
Expected: models.list shows the alias, one `build_part` tool call parsed. Then a timed 10-prompt run per arm:

```bash
PY=~/.venvs/simready-ocp/bin/python
$PY -m simready.bench run --model <alias> --arm dsl-v1 --k 1 --limit 10
$PY -m simready.bench run --model <alias> --arm dsl-v2 --k 1 --limit 10
$PY -m simready.bench run --model <alias> --arm build123d --k 1 --limit 10
```

Record median seconds per call per arm; multiply out the full matrix (Task 11) and report the projected hours to the user. If it exceeds ~48 h, the user decides whether the small model uses a smaller `k` (recorded in `bench_v2.md` if so).

- [ ] **Step 6: Commit**

```bash
git add simready/bench/providers.json docs/validation/bench_v2/small-model-choice.md && git commit -m "feat(bench): local small-model provider for SP2 and the SP3 entry gate"
```

---

### Task 11: Official runs (approval gate per batch)

**Files:**
- Create: `docs/validation/bench_v2/runs-*.jsonl.gz` (copied from `data/bench_runs/`)

- [ ] **Step 1: Pre-flight.** `git status` clean; `concepts_v2.sha256` matches; full bench test suite green:

Run: `~/.venvs/simready-ocp/bin/python -m pytest tests/ -q -k "bench or gen_spec_v2 or gen_build_v2"`
Expected: all pass.

- [ ] **Step 2: Ask approval** with the call count per batch (each concept file × arm × model = prompts × 5: v1 = 750 calls, v2 = 225 calls) and the projected local hours from Task 10.

- [ ] **Step 3: Run the matrix.** Run on the VPS from the repo root, inside a `tmux` session so the block survives a disconnect. The runs are sequential, and each writes its own `.out` log. Re-running the same command resumes the same file, because the run id is deterministic (Task 3 Step 8): `data/bench_runs/<model>-<arm>-<concepts>-k5.jsonl`.

```bash
cd ~/projects/Mech/SimReady
PY=~/.venvs/simready-ocp/bin/python
SMALL=<alias>   # from docs/validation/bench_v2/small-model-choice.md, filled in before running
run() { nohup $PY -m simready.bench run --model "$1" --arm "$2" --concepts "simready/bench/prompts/$3.jsonl" --k 5 --official > "data/bench_runs/$1-$2-$3.out" 2>&1; }
run "$SMALL" dsl-v1 concepts_v1          # SP3 entry gate; reference pair reuses the SP1 logs
for m in gpt-6.1-sol gemini-4-argon "$SMALL"; do
  run "$m" dsl-v1 concepts_v2
  for arm in dsl-v2 build123d; do
    for c in concepts_v1 concepts_v2; do run "$m" "$arm" "$c"; done
  done
done
```

Done when every `.out` file ends with `stopped: no`, the CLI's print of `RunSummary.stopped_reason is None`. Any excluded attempts must be explained in `bench_v2.md`.

- [ ] **Step 4: Repair runs.** Every repair uses the model of its source log, and `repair_run` refuses any other. Run them on the two SP1 logs and on every DSL v2 and build123d log:

```bash
rep() { nohup $PY -m simready.bench repair "$1" --out "${1%.jsonl*}.repair.jsonl" --model "$2" > "${1%.jsonl*}.repair.out" 2>&1; }
rep docs/validation/bench_v1/runs-gpt-6.1-sol.jsonl.gz gpt-6.1-sol
rep docs/validation/bench_v1/runs-gemini-4-argon.jsonl.gz gemini-4-argon
for m in gpt-6.1-sol gemini-4-argon "$SMALL"; do
  for arm in dsl-v2 build123d; do
    for c in concepts_v1 concepts_v2; do rep "data/bench_runs/$m-$arm-$c-k5.jsonl" "$m"; done
  done
done
```

The SP1 repair outputs land next to the SP1 logs as `docs/validation/bench_v1/runs-<model>.repair.jsonl`. Move them to `docs/validation/bench_v2/` in Step 5, because they are SP2 results.

- [ ] **Step 5: Copy and compress** the official logs into `docs/validation/bench_v2/` (`gzip -9`), verify each with `~/.venvs/simready-ocp/bin/python -m simready.bench report <log>`, then commit:

```bash
git add docs/validation/bench_v2/*.jsonl.gz && git commit -m "data(bench): SP2 official run logs"
```

---

### Task 12: Publish `bench_v2`

**Files:**
- Create: `docs/validation/bench_v2.md`
- Modify: `README.md` (§ Now and next, results), `BACKLOG.md` (close `sp2-vocab-v2`; update `sp3-entry-gate`), `docs/validation/bench_v1.md` (link forward only)

- [ ] **Step 0: Produce every pre-registered number with these commands** (VPS, repo root; `PY`, `SMALL` as in Task 11; `L=docs/validation/bench_v2`, `S=$L/sets`, `B1=docs/validation/bench_v1`). For each model `m`, with `$m` the alias and `R1` the reference pair's SP1 log `$B1/runs-$m.jsonl.gz` (for `$SMALL`, use `$L/$SMALL-dsl-v1-concepts_v1-k5.jsonl.gz`):

```bash
# 1. regression: DSL v2 - DSL v1 on the 37 v1 in-vocab concepts
$PY -m simready.bench compare --a $L/$m-dsl-v2-concepts_v1-k5.jsonl.gz --b $R1 --concepts $S/regression.txt
# 2. vocabulary: before (DSL v1) and after (DSL v2) on the design set and the held-out set
$PY -m simready.bench compare --a $L/$m-dsl-v2-concepts_v1-k5.jsonl.gz --b $R1 --concepts $S/design.txt
$PY -m simready.bench compare --a $L/$m-dsl-v2-concepts_v2-k5.jsonl.gz --b $L/$m-dsl-v1-concepts_v2-k5.jsonl.gz --concepts $S/heldout.txt
# 3. DSL v2 - build123d on the 62 v2-vocab concepts; build123d alone on c044/c045/c046
$PY -m simready.bench compare --a $L/$m-dsl-v2-concepts_v1-k5.jsonl.gz $L/$m-dsl-v2-concepts_v2-k5.jsonl.gz \
    --b $L/$m-build123d-concepts_v1-k5.jsonl.gz $L/$m-build123d-concepts_v2-k5.jsonl.gz --concepts $S/dsl_vs_code.txt
$PY -m simready.bench compare --a $L/$m-build123d-concepts_v1-k5.jsonl.gz --b $L/$m-build123d-concepts_v1-k5.jsonl.gz --concepts $S/c044_c045_c046.txt  # A column = pass@1; diff is 0 by construction
# 4. repair, per arm, on that arm's own concept set
$PY -m simready.bench repair-summary --single $L/$m-dsl-v2-concepts_v1-k5.jsonl.gz $L/$m-dsl-v2-concepts_v2-k5.jsonl.gz \
    --repair $L/$m-dsl-v2-concepts_v1-k5.repair.jsonl.gz $L/$m-dsl-v2-concepts_v2-k5.repair.jsonl.gz --concepts $S/dsl_vs_code.txt
$PY -m simready.bench repair-summary --single $L/$m-build123d-concepts_v1-k5.jsonl.gz $L/$m-build123d-concepts_v2-k5.jsonl.gz \
    --repair $L/$m-build123d-concepts_v1-k5.repair.jsonl.gz $L/$m-build123d-concepts_v2-k5.repair.jsonl.gz --concepts $S/dsl_vs_code.txt
$PY -m simready.bench repair-summary --single $R1 --repair $L/runs-$m.repair.jsonl.gz --concepts $S/regression.txt   # reference pair only
# 5. failure classes and cost
$PY -m simready.bench report $L/$m-*-k5.jsonl.gz
```

No number in `bench_v2.md` may come from any other command. A number these commands cannot produce is reported missing, never computed ad hoc.

- [ ] **Step 1: Write `bench_v2.md`** with exactly the pre-registered results of the design doc, in order: method (arms, models, frozen hashes, checker 1.0.0, the E1 honest limit, per-concept averaging in comparisons), (1) regression, (2) vocabulary on design set and held-out set, (3) DSL v2 vs build123d with paired CIs and c044/c045/c046 apart, (4) repair, (5) failure classes and cost; three annotated failures rendered with `simready/copilot/png_render.py`; known limits (no network isolation in the code arm; small checks noted in `concepts_v2` sources). Publish regardless of outcome.

- [ ] **Step 2: Verify every number** in `bench_v2.md` and README by re-running `report`/`compare` on the committed logs (Working Rule 7); grep README, `bench_v1.md`, BACKLOG and STATE for claims the results change (Working Rule 19) and fix them in the same commit.

- [ ] **Step 3: Commit**

```bash
git add docs/validation/bench_v2.md README.md BACKLOG.md docs/validation/bench_v1.md && git commit -m "docs(bench): publish SP2 bench_v2 results

Closes: sp2-vocab-v2"
```

---

## Self-review notes (2026-11-20)

- Spec coverage: E1 → Task 0; E2 → Tasks 1, 2, 4; E3 → Task 10; E4 → Tasks 5–7; E5 → Task 8; run matrix → Task 11; pre-registered results → Tasks 9, 12.
- Task 4 lists recipes plus two complete entries instead of all 21 JSON specs: the specs are data whose correctness is proven only by the test in that task, and writing them blind in the plan would put untested geometry in a document. Each recipe names the ops and placements; the test is the acceptance criterion.
- Dry run 2026-11-20: the Task 1 and Task 2 code and tests, copied verbatim from this plan into a scratch copy of the repo, pass (29 tests, OCP backend); the run found that OCCT returns an invalid solid with `IsDone()` true for an oversized fillet, hence the `BRepCheck_Analyzer` guard in `_edge_op`. The two Task 4 worked entries (c040, c041) pass their explicit and engineer checks. Tasks 3–12 have not been dry-run.
- Plan review 2026-11-20 (one fresh `plan-review` reviewer, verdict READY AFTER FIXES, 10 Majors + 3 nits). All were accepted and applied:
  1. child rlimits moved out of `preexec_fn` (thread-unsafe);
  2. ADR states filesystem exposure; the gate blocks `format`/`format_map`/`import_*`/`export_*`; the env test now inspects the real `subprocess.run` call;
  3. deterministic run id `{model}-{arm}-{concepts}-k{k}`, parser `r`;
  4. `regrade` computes `in_vocab` per arm and resolves the concept file from the header;
  5. tests rewritten against the real `FakeClient`/`concepts` fixtures, with `arm` placed before `system_prompt_sha256` in `_PINNED`;
  6. the `_grade_worker` signature change lists its test edits, with STEP read errors classed `build_error`/`step_read` after the ready signal;
  7. `scripts/bench_compare_regrade.py` committed, with both regrade commands and expected outputs;
  8. all v2 in-vocab concepts built with the v2 executor on all phrasings (62 after Task 4 moved c044 out: 21 hand-written + 41 fallback);
  9. grader guard in `evaluate_code_reply`; `repair_run` resumable, model-checked and infra-aware, with unique `/repair<round>` ids because `runlog.attempts` keeps the latest record per id; `repair_summary` implemented and tested;
  10. pre-registered concept sets written by `scripts/bench_v2_sets.py` with expected counts, plus exact commands per result in Task 12 Step 0.

  Nits: the leak test uses the real `c027` check bounds; the exception test uses `1 / 0`; `stopped: no` is defined as the CLI print. Decided during the fixes: only in-vocab failures are repaired (design E5 updated).
- Signatures used across tasks: `grade_spec(..., dsl=)`, `evaluate_reply(..., dsl=)`, `evaluate_code_reply(content, checks, expected_solids, run=, grade=)`, `grade_step(step_path, checks, expected_solids)`, `run_code(code, timeout_s, python)`, `feedback_text(record, features)`, `paired_diff(a, b, concept_ids)` — consistent between definition and use.
