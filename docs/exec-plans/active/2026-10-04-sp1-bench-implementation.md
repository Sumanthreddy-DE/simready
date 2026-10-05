# SP1 Benchmark + Harness Implementation Plan

**Status:** active
**Last verified:** 2026-10-04
**Spec:** `docs/exec-plans/active/2026-09-25-sp1-cad-benchmark-design.md` (reviewed 2026-10-04, `c99ace2`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `simready/bench/`, a checker-scored, replayable text-to-CAD benchmark (50 concepts × 3 phrasings, k=5), run it on GLM-5.3 and DeepSeek V4.1 Flash, and publish `docs/validation/bench_v1.md` with committed logs that anyone can re-grade.

**Architecture:** A pydantic concept file defines prompts and range checks. Each attempt goes: model reply → parse (tool call or JSON in text) → pre-build classification (F1/F2/F3/F9) → build + gate + checks in a killable spawn subprocess (F4–F8) → one append-only JSONL line. The OCC-free modules (`concepts`, `runlog`, `report`) let `report` run in plain Python; geometry lives only in `geometry`/`checker`, which are imported inside the subprocess.

**Tech Stack:** Python 3.10 (sr env `C:\mm\sr\python.exe`), pythonocc-core 7.9.0, pydantic 2.13, openai 2.36 (OpenAI-compatible endpoints), pytest. Report: stdlib only.

## Global Constraints

- Tests and runs use the sr env: `C:/mm/sr/python.exe -m pytest ...` (base Python 3.12 lacks OCC and torch_geometric).
- The DSL stays as it is: `box`, `cyl` (axis fixed to +Z), `fuse`, `cut`; at most 16 steps (`simready/gen/spec.py`). SP1 must not change it.
- No LLM-written code is ever executed (ADR 0001). The executor is `simready.gen.build.build_shape`.
- Every check returns `pass` / `fail` / `not_checked`. An attempt passes iff the gate passes and no check fails.
- Explicit-phrasing tolerance: ±0.1 mm on stated numbers. Engineer: the standard's own range. Intent: wide ranges / `any_of`.
- Build/check timeout: 60 s per attempt, in a spawn subprocess killed with `terminate()`.
- Temperature 0.7, k = 5, seed = attempt index where the provider supports it; all params logged.
- API keys are never logged or printed. Only the env-var *name* and base URL appear in config and logs.
- Never `Read` `.env`. To check that keys load, use a redacted one-liner (prints names and lengths only).
- `infra_error` (API failure after retries) and `checker_error` (our own crash) are excluded from scoring and retried on resume.
- SP3's metric is fixed: single-shot pass@1 on held-out prompts. Nothing in SP1 may change that.
- Run output goes to `data/bench_runs/` (gitignored). Official logs go to `docs/validation/bench_v1/runs-<model>.jsonl.gz` (tracked).
- `docs/jobs/` stays gitignored and is never referenced from tracked files (public repo).
- No AI attribution in commits. Never `git push` (the user pushes).

## Deviations from the spec (Rule 2: fixed here, reported)

1. **`solid_count` is a gate parameter, not a check type.** The gate already checks the solid count (`Concept.solids`, default 1). A separate check type would grade the same thing twice.
2. **The checker grades the in-memory shape; no STEP file is written per attempt.** Spec §2 says "build STEP → checker", but STEPs are never stored (replay uses the fingerprint). Writing and re-reading one would only test the STEP writer.
3. **A new excluded class, `checker_error`.** A crash inside our own checker must not be blamed on the model. It is logged, excluded like `infra_error`, and fixed via `regrade`.
4. **The system prompt allows a refusal** ("if it cannot be built with these operations, say so"). Without it, spec §3 table 5 ("admits it can't vs fakes the feature") would have no "admits" path.

Task 1 writes these four into the spec.

## File map

| File | Responsibility | Needs OCC |
|---|---|---|
| `simready/bench/__init__.py` | package docstring, `CHECKER_VERSION` | no |
| `simready/bench/concepts.py` | concept/check schema, loader, file hash | no |
| `simready/bench/prompts/concepts_v1.jsonl` | the 50 concepts | — |
| `simready/bench/prompts/concepts_v1.sha256` | frozen hash (written at freeze) | — |
| `simready/bench/geometry.py` | gate, extents, cylindrical features, fingerprint | yes |
| `simready/bench/checker.py` | evaluate checks on a shape | yes |
| `simready/bench/attempt.py` | parse reply, classify, grade in subprocess | parent no, child yes |
| `simready/bench/prompting.py` | system prompt, bench tool schema, hash | imports copilot.tools (OCC) |
| `simready/bench/providers.py` + `providers.json` | provider config, key lookup, retrying client, rate limiter | no |
| `simready/bench/runlog.py` | JSONL / JSONL.gz read and append | no |
| `simready/bench/runner.py` | work items, threads, resume, header | parent no |
| `simready/bench/replay.py` | `regrade`, `replay` | via subprocess |
| `simready/bench/report.py` | metrics, bootstrap, markdown tables | no |
| `simready/bench/__main__.py` | CLI: `smoke`, `run`, `regrade`, `replay`, `report` | lazy imports |
| `tests/test_bench_*.py` | one test file per module | mixed |

---

### Task 1: Concept schema, loader, package skeleton, spec deviations

**Files:**
- Create: `simready/bench/__init__.py`
- Create: `simready/bench/concepts.py`
- Create: `tests/test_bench_concepts.py`
- Modify: `docs/exec-plans/active/2026-09-25-sp1-cad-benchmark-design.md` (record deviations 1–4)
- Modify: `.gitignore` (add `data/bench_runs/`)

**Interfaces:**
- Produces: `CHECKER_VERSION: str`; `PHRASINGS = ("explicit", "engineer", "intent")`; `Range = tuple[float|None, float|None]`; `in_range(value, rng) -> bool`; check models `BBoxSorted`, `BBoxMinDim`, `VolumeCheck`, `HoleSet`, `Bore`, `Boss`, `AnyOf`, `NotChecked`; the `Check` union; `CHECK_LIST: TypeAdapter[list[Check]]`; `Concept` (fields `concept_id, name, in_vocab, solids, prompts, checks, sources, reference_spec`); `load_concepts(path) -> list[Concept]`; `file_sha256(path) -> str`; `frozen_sha256(path) -> str | None`; `CONCEPTS_V1`, `CONCEPTS_V1_FROZEN` paths.

- [ ] **Step 1: Write the failing tests**

`tests/test_bench_concepts.py`:

```python
"""Concept-file schema tests. No OCC, no network."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from simready.bench.concepts import (
    CHECK_LIST,
    Concept,
    HoleSet,
    file_sha256,
    in_range,
    load_concepts,
)

PLATE_SPEC = {
    "steps": [
        {"op": "box", "dx": 40, "dy": 30, "dz": 5},
        {"op": "cyl", "r": 3, "h": 5, "at": [20, 15, 0]},
        {"op": "cut", "a": 0, "b": 1},
    ]
}


def _concept(**over):
    base = {
        "concept_id": "c900",
        "name": "test plate",
        "in_vocab": True,
        "prompts": {
            "explicit": "A 40 x 30 x 5 mm plate with a 6 mm through hole in the centre.",
            "engineer": "Small 5 mm cover plate with an M5 clearance hole.",
            "intent": "A little plate with a hole for a screw.",
        },
        "checks": {
            "explicit": [{"type": "bbox_sorted", "ranges": [[4.9, 5.1], [29.9, 30.1], [39.9, 40.1]]}],
            "engineer": [{"type": "hole_set", "diameter": [5.3, 5.8], "count": [1, 1], "through": True}],
            "intent": [{"type": "not_checked", "what": "outline"}],
        },
        "sources": ["ISO 273 M5 clearance 5.3-5.8"],
        "reference_spec": PLATE_SPEC,
    }
    base.update(over)
    return base


def test_in_range_open_and_closed_bounds():
    assert in_range(5.0, (4.9, 5.1))
    assert not in_range(5.2, (4.9, 5.1))
    assert in_range(1e6, (3.0, None))
    assert in_range(-1.0, (None, 0.0))


def test_valid_concept_parses_with_discriminated_checks():
    c = Concept.model_validate(_concept())
    assert isinstance(c.checks.engineer[0], HoleSet)
    assert c.solids == 1


def test_in_vocab_requires_reference_spec_and_vice_versa():
    with pytest.raises(ValidationError, match="needs reference_spec"):
        Concept.model_validate(_concept(reference_spec=None))
    with pytest.raises(ValidationError, match="must not carry"):
        Concept.model_validate(_concept(in_vocab=False))


def test_bad_concept_id_and_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Concept.model_validate(_concept(concept_id="plate1"))
    with pytest.raises(ValidationError):
        Concept.model_validate(_concept(extra_field=1))


def test_hole_pattern_needs_exact_count_and_pair_count():
    ok = {"type": "hole_set", "diameter": [3.3, 3.5], "count": [3, 3],
          "pattern": [[9.9, 10.1], [9.9, 10.1], [19.9, 20.1]]}
    CHECK_LIST.validate_python([ok])
    with pytest.raises(ValidationError, match="exact count"):
        CHECK_LIST.validate_python([{**ok, "count": [2, 3]}])
    with pytest.raises(ValidationError, match="3 distances"):
        CHECK_LIST.validate_python([{**ok, "pattern": [[9.9, 10.1]]}])


def test_any_of_nests_checks():
    checks = CHECK_LIST.validate_python([
        {"type": "any_of", "checks": [
            {"type": "bore", "diameter": [7.9, 8.1]},
            {"type": "boss", "diameter": [7.9, 8.1]},
        ]}
    ])
    assert checks[0].checks[1].type == "boss"


def test_load_concepts_rejects_duplicate_ids(tmp_path):
    p = tmp_path / "c.jsonl"
    line = json.dumps(_concept())
    p.write_text(line + "\n" + line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate concept_id c900"):
        load_concepts(p)


def test_load_concepts_and_hash(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps(_concept()) + "\n\n", encoding="utf-8")
    assert [c.concept_id for c in load_concepts(p)] == ["c900"]
    assert len(file_sha256(p)) == 64
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_concepts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'simready.bench'`

- [ ] **Step 3: Write the package and schema**

`simready/bench/__init__.py`:

```python
"""Checker-scored text-to-CAD benchmark (SP1).

Design: docs/exec-plans/active/2026-09-25-sp1-cad-benchmark-design.md.
OCC-free modules (concepts, runlog, report) must stay importable in plain
Python so ``python -m simready.bench report`` works without pythonocc.
"""

# Bump on any checker change. Drop "-dev" when tagging the official run;
# ``run --official`` refuses a "-dev" version.
CHECKER_VERSION = "1.0.0-dev"
```

`simready/bench/concepts.py`:

```python
"""Benchmark concept file: schema, loader and hash. No OCC, no network.

One JSONL line per concept. Each concept has three phrasings (explicit /
engineer / intent), a check list per phrasing, the standards the ranges
come from, and, for in-vocab concepts, a hand-built ``reference_spec``
that must pass all of its own checks (tests/test_bench_reference_specs.py).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

PHRASINGS = ("explicit", "engineer", "intent")

BENCH_DIR = Path(__file__).resolve().parent
CONCEPTS_V1 = BENCH_DIR / "prompts" / "concepts_v1.jsonl"
CONCEPTS_V1_FROZEN = BENCH_DIR / "prompts" / "concepts_v1.sha256"

Bound = Optional[float]
Range = tuple[Bound, Bound]  # inclusive; None = open-ended


def in_range(value: float, rng: Range) -> bool:
    lo, hi = rng
    return (lo is None or value >= lo) and (hi is None or value <= hi)


class _Check(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BBoxSorted(_Check):
    """Bounding-box extents, compared smallest-to-largest (placement-invariant)."""

    type: Literal["bbox_sorted"]
    ranges: tuple[Range, Range, Range]


class BBoxMinDim(_Check):
    """Smallest bounding-box extent is at least ``min`` (e.g. plate thickness)."""

    type: Literal["bbox_min_dim"]
    min: float


class VolumeCheck(_Check):
    type: Literal["volume"]
    range: Range  # mm^3


class HoleSet(_Check):
    """Full concave cylinders with diameter in range (and through/depth if given).

    ``count`` is how many such holes must exist. ``pattern`` = the sorted
    pairwise axis distances between them, as ranges; needs an exact count.
    """

    type: Literal["hole_set"]
    diameter: Range
    count: Range
    through: Optional[bool] = None
    depth_min: Optional[float] = None
    pattern: Optional[list[Range]] = None

    @model_validator(mode="after")
    def _pattern_shape(self) -> "HoleSet":
        if self.pattern is None:
            return self
        lo, hi = self.count
        if lo is None or lo != hi:
            raise ValueError("pattern requires an exact count [n, n]")
        n = int(lo)
        pairs = n * (n - 1) // 2
        if len(self.pattern) != pairs:
            raise ValueError(f"pattern for {n} holes needs {pairs} distances, got {len(self.pattern)}")
        return self


class Bore(_Check):
    """At least one full concave cylinder with diameter in range (and depth/through if given)."""

    type: Literal["bore"]
    diameter: Range
    depth_min: Optional[float] = None
    through: Optional[bool] = None


class Boss(_Check):
    """Full convex cylinders (boss, shaft, tube OD) with diameter in range."""

    type: Literal["boss"]
    diameter: Range
    height_min: Optional[float] = None
    count: Range = (1, None)


class AnyOf(_Check):
    """Passes if any sub-check passes (intent phrasings with several valid answers)."""

    type: Literal["any_of"]
    checks: list["Check"] = Field(min_length=2)


class NotChecked(_Check):
    """A genuinely free design choice, logged as not_checked, never silently passed."""

    type: Literal["not_checked"]
    what: str


Check = Annotated[
    Union[BBoxSorted, BBoxMinDim, VolumeCheck, HoleSet, Bore, Boss, AnyOf, NotChecked],
    Field(discriminator="type"),
]
AnyOf.model_rebuild()
CHECK_LIST: TypeAdapter[list[Check]] = TypeAdapter(list[Check])


class Prompts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explicit: str = Field(min_length=10)
    engineer: str = Field(min_length=10)
    intent: str = Field(min_length=10)


class PhrasingChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explicit: list[Check] = Field(min_length=1)
    engineer: list[Check] = Field(min_length=1)
    intent: list[Check] = Field(min_length=1)


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str = Field(pattern=r"^c\d{3}$")
    name: str
    in_vocab: bool
    solids: int = Field(default=1, ge=1)
    prompts: Prompts
    checks: PhrasingChecks
    sources: list[str] = Field(default_factory=list)
    reference_spec: Optional[dict] = None

    @model_validator(mode="after")
    def _reference_iff_in_vocab(self) -> "Concept":
        if self.in_vocab and self.reference_spec is None:
            raise ValueError(f"{self.concept_id}: in-vocab concept needs reference_spec")
        if not self.in_vocab and self.reference_spec is not None:
            raise ValueError(f"{self.concept_id}: out-of-vocab concept must not carry reference_spec")
        return self


def load_concepts(path: str | Path = CONCEPTS_V1) -> list[Concept]:
    concepts: list[Concept] = []
    seen: set[str] = set()
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        concept = Concept.model_validate_json(line)
        if concept.concept_id in seen:
            raise ValueError(f"line {lineno}: duplicate concept_id {concept.concept_id}")
        seen.add(concept.concept_id)
        concepts.append(concept)
    return concepts


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_sha256(path: str | Path = CONCEPTS_V1_FROZEN) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").strip() or None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_concepts.py -v`
Expected: 8 passed

- [ ] **Step 5: Gitignore the run directory and record the spec deviations**

Append to `.gitignore`:

```
# SP1 benchmark working runs (official logs are copied, gzipped, to docs/validation/bench_v1/)
data/bench_runs/
```

In the spec, add this block at the end of `## Design §3`:

```markdown
### Implementation deviations (plan 2026-10-04, reported per Rule 2)

1. `solid_count` is the gate's `Concept.solids` parameter, not a separate check type (it would grade the gate twice).
2. The checker grades the in-memory shape; no STEP is written per attempt (STEPs are not stored; replay uses the fingerprint).
3. New excluded class `checker_error`: a crash in our checker is excluded from scoring like `infra_error` and fixed via `regrade`.
4. The system prompt allows a refusal ("say so instead of calling the tool"), which gives table 5 its "admits it can't" path.
```

- [ ] **Step 6: Commit**

```bash
git add simready/bench/__init__.py simready/bench/concepts.py tests/test_bench_concepts.py .gitignore docs/exec-plans/active/2026-09-25-sp1-cad-benchmark-design.md
git commit -m "feat(bench): concept schema and loader; record plan deviations in SP1 spec"
```

---

### Task 2: Write the 50 concepts (draft for user proofreading)

The user proofreads this while Tasks 3–8 are built. The reference specs are checked mechanically in Task 4.

**Files:**
- Create: `simready/bench/prompts/concepts_v1.jsonl`
- Create: `tests/test_bench_concepts_file.py`

**Interfaces:**
- Consumes: `load_concepts`, `Concept`, `PartSpec` (`simready/gen/spec.py`).
- Produces: `concepts_v1.jsonl`, read by every later task.

**Authoring rules (the assistant follows these while writing):**

1. IDs `c001`–`c050` in the order of the table below. Append-only from here on (D4).
2. Explicit prompt: every dimension stated, in mm. Its checks use ±0.1 mm around the stated numbers.
3. Engineer prompt: function + standard, without dimensions the standard defines. Checks use the standard's range. Each range gets a `sources` entry naming the standard and value. **Every standard value is checked against a primary source (standard table, manufacturer drawing) while writing.** If it can't be verified, the engineer check falls back to what the prompt states and `sources` says "unverified".
4. Intent prompt: no numbers the user wouldn't know. Checks: only implied constraints, as wide ranges or `any_of`. Free choices become `not_checked` entries naming what is free.
5. The explicit numbers must lie inside the engineer and intent ranges, so **one `reference_spec` per in-vocab concept passes all three check lists.**
6. In-vocab = a reference spec exists: axis-aligned boxes, +Z cylinders, fuse/cut, ≤16 steps. Count steps before choosing in-vocab. A plate with n holes = 1 + 2n steps.
7. Out-of-vocab concepts have `"in_vocab": false`, no `reference_spec`, and checks that would still grade a faked attempt (bbox, bore).
8. No check that can't be computed (wall thickness, keyway, chamfer size) → use `not_checked`.
9. Prompts are written fresh, never from a template (D2: SP3's training prompts are templated).

**Concept list (themes; the user may swap themes while proofreading):**

| id | concept | expected in_vocab | key constraint / source to verify |
|---|---|---|---|
| c001 | NEMA 17 motor plate | yes | 31.0 mm square pattern, M3 clearance, 22 mm boss clearance |
| c002 | NEMA 23 motor plate | yes | 47.14 mm pattern, M5 clearance, 38.1 mm boss clearance |
| c003 | 608 bearing seat block | yes | 22 mm seat bore, blind, ≥7 mm deep; shaft clearance through |
| c004 | M8 spacer tube | yes | ID M8 clearance (ISO 273), OD, length |
| c005 | M3 standoff spacer | yes | ID 3.2–3.6, length |
| c006 | shaft collar body (no set screw) | yes | bore = shaft Ø, OD, width |
| c007 | 4-hole hub flange | yes | bolt circle, hub boss, bore (13 steps) |
| c008 | 6-hole flat flange ring (no hub) | yes | 6 holes on a bolt circle, 15 steps |
| c009 | wall plate, 4 corner M5 holes | yes | ISO 273 M5 clearance |
| c010 | slotted adjustment plate (2 slots) | yes | slot = box + 2 cyl (13 steps); slot width = clearance |
| c011 | DIN 125 M6 washer | yes | 6.4 / 12 / 1.6 |
| c012 | ISO 7089 M10 washer | yes | 10.5 / 20 / 2 |
| c013 | vertical-axis bearing seat plate | yes | 608 seat + through hole + 4 mounting holes (13 steps) |
| c014 | Arduino Uno mounting plate | yes | official hole positions (verify against the Arduino drawing) |
| c015 | Raspberry Pi 4 mounting plate | yes | 58 × 49 mm pattern, M2.5 clearance |
| c016 | 2020 extrusion end cap | yes | 20 × 20 outline, M5 centre hole |
| c017 | flanged cable bushing | yes | stacked cylinders + bore |
| c018 | spool / pulley blank | yes | flange-core-flange + bore |
| c019 | knob blank with blind shaft bore | yes | blind bore, depth |
| c020 | enclosure lid, 4 M3 holes + cable-gland hole | yes | gland hole size from the gland's spec |
| c021 | PCB plate with two standoff bosses | yes | bosses + insert pilot holes (9 steps) |
| c022 | countersunk hinge leaf | no | cone needed |
| c023 | 3-step gauge block | yes | step heights (bbox + volume) |
| c024 | T-bracket, holes in flange only | yes | Z holes only |
| c025 | U-channel | yes | outer/inner extents |
| c026 | L-bracket, holes in both legs | no | needs holes in two directions |
| c027 | L-bracket, holes in base leg only | yes | 7 steps |
| c028 | sensor block with M4 tap-drill blind holes | yes | ISO tap drill 3.3, depth |
| c029 | dowel locating plate (2 × 6H7) | yes | 6H7 range |
| c030 | DIN 1850 sleeve bushing | yes | ID/OD/length from table |
| c031 | 10 mm shaft spacer ring | yes | ID/OD/width |
| c032 | NEMA 17 → 2020 adapter plate | yes | NEMA pattern + 2 × M5 (15 steps) |
| c033 | hex standoff | no | hexagon not expressible |
| c034 | ISO 4032 M8 hex nut | no | hexagon |
| c035 | linear 5-hole flat bar | yes | pitch pattern |
| c036 | cylindrical cup / container | yes | wall, bottom thickness via blind bore depth |
| c037 | pipe clamp half | no | horizontal bore |
| c038 | stepped shaft (3 diameters) | yes | boss diameters, lengths |
| c039 | rounded-corner plate (corner R via cylinders) | yes | 11 steps; tests construction reasoning |
| c040 | 8-hole bolt-circle disc | no | 19 steps > 16 |
| c041 | plate with filleted top edges | no | fillet |
| c042 | shaft with chamfered ends | no | chamfer |
| c043 | funnel | no | cone |
| c044 | ball knob | no | sphere |
| c045 | M6 threaded rod | no | thread |
| c046 | 20-tooth spur gear | no | involute profile |
| c047 | cross-drilled shaft | no | horizontal hole |
| c048 | open-top electronics box | yes | box cut box |
| c049 | 40 mm fan mount plate | yes | 32 mm pattern, M3, airflow hole |
| c050 | MGN12H carriage plate | yes | 20 × 20 M3 pattern (verify against the rail datasheet) |

Expected count: 38 in-vocab, 12 out-of-vocab. The final count is whatever the reference specs prove.

- [ ] **Step 1: Write the file-level test**

`tests/test_bench_concepts_file.py`:

```python
"""The shipped concept file: schema, IDs, vocabulary limits. No OCC."""

from __future__ import annotations

from simready.bench.concepts import CONCEPTS_V1, load_concepts
from simready.gen.spec import PartSpec


def test_concepts_v1_parses_with_50_sequential_ids():
    concepts = load_concepts(CONCEPTS_V1)
    assert [c.concept_id for c in concepts] == [f"c{i:03d}" for i in range(1, 51)]


def test_reference_specs_are_valid_dsl():
    for c in load_concepts(CONCEPTS_V1):
        if c.in_vocab:
            PartSpec.model_validate(c.reference_spec)  # raises with the concept's error


def test_every_phrasing_has_a_gradable_check():
    for c in load_concepts(CONCEPTS_V1):
        for phrasing in ("explicit", "engineer"):
            checks = getattr(c.checks, phrasing)
            assert any(ch.type != "not_checked" for ch in checks), (c.concept_id, phrasing)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_concepts_file.py -v`
Expected: FAIL with `FileNotFoundError` (no `concepts_v1.jsonl`)

- [ ] **Step 3: Write the 50 concept lines**

Format: one JSON object per line, no line breaks inside an object. These two lines are verified examples (c001 in-vocab, c034 out-of-vocab). Write c001 as shown, then the other 49 in the same format:

```json
{"concept_id": "c001", "name": "NEMA 17 motor mounting plate", "in_vocab": true, "prompts": {"explicit": "Make a 42 x 42 x 5 mm plate. Put a 22.5 mm through hole in the centre and four 3.4 mm through holes on a 31 mm square pattern centred on the plate.", "engineer": "Mounting plate for a NEMA 17 stepper motor, 5 mm thick, with clearance for the motor's centring boss and its four M3 mounting screws.", "intent": "I need a plate to bolt a NEMA 17 stepper motor onto."}, "checks": {"explicit": [{"type": "bbox_sorted", "ranges": [[4.9, 5.1], [41.9, 42.1], [41.9, 42.1]]}, {"type": "bore", "diameter": [22.4, 22.6], "through": true}, {"type": "hole_set", "diameter": [3.3, 3.5], "count": [4, 4], "through": true, "pattern": [[30.9, 31.1], [30.9, 31.1], [30.9, 31.1], [30.9, 31.1], [43.74, 43.94], [43.74, 43.94]]}], "engineer": [{"type": "bbox_sorted", "ranges": [[4.9, 5.1], [38.0, 120.0], [38.0, 120.0]]}, {"type": "bore", "diameter": [22.1, 24.0], "through": true}, {"type": "hole_set", "diameter": [3.2, 3.6], "count": [4, 4], "through": true, "pattern": [[30.8, 31.2], [30.8, 31.2], [30.8, 31.2], [30.8, 31.2], [43.6, 44.1], [43.6, 44.1]]}], "intent": [{"type": "bore", "diameter": [22.1, 26.0], "through": true}, {"type": "hole_set", "diameter": [3.2, 3.6], "count": [4, 4], "through": true, "pattern": [[30.7, 31.3], [30.7, 31.3], [30.7, 31.3], [30.7, 31.3], [43.4, 44.3], [43.4, 44.3]]}, {"type": "not_checked", "what": "plate outline and thickness"}]}, "sources": ["NEMA 17: mounting holes on a 31.0 mm square, centring boss 22 mm diameter", "ISO 273 M3 clearance: fine 3.2, medium 3.4, coarse 3.6"], "reference_spec": {"steps": [{"op": "box", "dx": 42, "dy": 42, "dz": 5}, {"op": "cyl", "r": 11.25, "h": 5, "at": [21, 21, 0]}, {"op": "cut", "a": 0, "b": 1}, {"op": "cyl", "r": 1.7, "h": 5, "at": [5.5, 5.5, 0]}, {"op": "cut", "a": 2, "b": 3}, {"op": "cyl", "r": 1.7, "h": 5, "at": [36.5, 5.5, 0]}, {"op": "cut", "a": 4, "b": 5}, {"op": "cyl", "r": 1.7, "h": 5, "at": [5.5, 36.5, 0]}, {"op": "cut", "a": 6, "b": 7}, {"op": "cyl", "r": 1.7, "h": 5, "at": [36.5, 36.5, 0]}, {"op": "cut", "a": 8, "b": 9}]}}
{"concept_id": "c034", "name": "ISO 4032 M8 hex nut (thread not modelled)", "in_vocab": false, "prompts": {"explicit": "Model a hexagonal nut 13 mm across flats and 6.8 mm thick, with a plain 6.8 mm through hole along its axis.", "engineer": "An ISO 4032 M8 hex nut; model the threaded hole as a plain tap-drill bore.", "intent": "A nut for an M8 bolt; the thread itself doesn't need to be modelled."}, "checks": {"explicit": [{"type": "bbox_sorted", "ranges": [[6.7, 6.9], [12.9, 13.1], [14.9, 15.1]]}, {"type": "bore", "diameter": [6.7, 6.9], "through": true}], "engineer": [{"type": "bbox_sorted", "ranges": [[6.44, 6.8], [12.73, 13.0], [14.38, 15.1]]}, {"type": "bore", "diameter": [6.6, 8.0], "through": true}], "intent": [{"type": "bore", "diameter": [6.6, 8.5], "through": true}, {"type": "not_checked", "what": "outer shape (hexagon expected, not expressible in the DSL)"}]}, "sources": ["ISO 4032 M8: s = 13 mm (min 12.73), m = 6.8 mm (min 6.44), e min 14.38", "ISO 2306 M8 tap drill 6.8"], "reference_spec": null}
```

c034's ISO 4032 minimums are values to re-verify while writing (rule 3), the same as every other `sources` line.

- [ ] **Step 4: Run the file test**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_concepts_file.py -v`
Expected: 3 passed. If `test_reference_specs_are_valid_dsl` fails on a concept, fix its spec, or mark the concept out-of-vocab if it can't fit in 16 steps.

- [ ] **Step 5: Commit, then hand to the user for proofreading**

```bash
git add simready/bench/prompts/concepts_v1.jsonl tests/test_bench_concepts_file.py
git commit -m "feat(bench): concepts_v1 draft - 50 concepts x 3 phrasings, reference specs"
```

Ask the user to proofread `concepts_v1.jsonl`, focusing on: realism of each part, engineer ranges vs the cited standard, and whether each intent prompt is something a person would actually say. Tasks 3–8 continue in parallel. **The hash is frozen only in Task 11.**

---

### Task 3: Geometry module (gate, extents, cylindrical features, fingerprint)

**Files:**
- Create: `simready/bench/geometry.py`
- Create: `tests/test_bench_geometry.py`

**Interfaces:**
- Consumes: `simready.occ_utils.count_shapes, count_topology, iter_faces, shape_bounding_box`; `simready.gen.build.build_shape`, `PartSpec` (tests).
- Produces: `GateResult(passed, reason, brep_valid, free_edges, volume, solids)`; `run_gate(shape, expected_solids=1) -> GateResult`; `sorted_extents(shape) -> list[float]`; `volume(shape) -> float`; `surface_area(shape) -> float`; `CylFeature(diameter, axis_point, direction, t0, t1, sweep, concave, through)` with `.depth`, `.full`; `cylindrical_features(shape) -> list[CylFeature]`; `axis_distance(a, b) -> float`; `fingerprint(shape) -> dict`.

- [ ] **Step 1: Write the failing tests**

`tests/test_bench_geometry.py`:

```python
"""Geometry measurements on hand-built shapes (sr env; skips without OCC)."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC.Core.BRepPrimAPI")

from OCC.Core.BRep import BRep_Builder  # noqa: E402
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox  # noqa: E402
from OCC.Core.TopoDS import TopoDS_Shell, topods  # noqa: E402

from simready.bench import geometry as geo  # noqa: E402
from simready.gen.build import build_shape  # noqa: E402
from simready.gen.spec import PartSpec  # noqa: E402
from simready.occ_utils import iter_faces  # noqa: E402


def mk(steps):
    return build_shape(PartSpec.model_validate({"steps": steps}))


PLATE = [  # through hole d3.2 + blind 22 mm recess 3 deep
    {"op": "box", "dx": 42, "dy": 42, "dz": 5},
    {"op": "cyl", "r": 1.6, "h": 5, "at": [5.5, 5.5, 0]},
    {"op": "cut", "a": 0, "b": 1},
    {"op": "cyl", "r": 11, "h": 3, "at": [21, 21, 2]},
    {"op": "cut", "a": 2, "b": 3},
]


def _holes(shape):
    return sorted((f for f in geo.cylindrical_features(shape) if f.concave), key=lambda f: f.diameter)


def test_gate_passes_valid_box_and_reports_volume():
    g = geo.run_gate(BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape())
    assert g.passed and g.reason == "" and math.isclose(g.volume, 6000.0)


def test_gate_fails_open_shell():
    box = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape()
    builder, shell = BRep_Builder(), TopoDS_Shell()
    builder.MakeShell(shell)
    for i, face in iter_faces(box):
        if i < 5:
            builder.Add(shell, face)
    g = geo.run_gate(shell)
    assert not g.passed and g.reason == "open_shell" and g.free_edges > 0


def test_gate_fails_reversed_solid_on_volume():
    rev = topods.Solid(BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape().Reversed())
    g = geo.run_gate(rev)
    assert not g.passed and g.reason == "non_positive_volume"


def test_gate_fails_disjoint_fuse_on_solid_count():
    s = mk([
        {"op": "box", "dx": 10, "dy": 10, "dz": 10},
        {"op": "box", "dx": 10, "dy": 10, "dz": 10, "at": [50, 0, 0]},
        {"op": "fuse", "a": 0, "b": 1},
    ])
    g = geo.run_gate(s)
    assert not g.passed and g.reason == "solid_count 2 != 1"
    assert geo.run_gate(s, expected_solids=2).passed


def test_sorted_extents_are_placement_invariant():
    assert geo.sorted_extents(mk(PLATE)) == pytest.approx([5.0, 42.0, 42.0])


def test_through_hole_and_blind_recess():
    small, big = _holes(mk(PLATE))
    assert small.diameter == pytest.approx(3.2) and small.through and small.full
    assert small.depth == pytest.approx(5.0)
    assert big.diameter == pytest.approx(22.0) and big.through is False
    assert big.depth == pytest.approx(3.0)


def test_counterbore_small_is_through_large_is_blind():
    s = mk([
        {"op": "box", "dx": 20, "dy": 20, "dz": 10},
        {"op": "cyl", "r": 1.7, "h": 10, "at": [10, 10, 0]},
        {"op": "cut", "a": 0, "b": 1},
        {"op": "cyl", "r": 3, "h": 3, "at": [10, 10, 7]},
        {"op": "cut", "a": 2, "b": 3},
    ])
    small, big = _holes(s)
    assert small.through is True and big.through is False


def test_stacked_flange_bosses_and_bore():
    s = mk([
        {"op": "cyl", "r": 10, "h": 5},
        {"op": "cyl", "r": 6, "h": 10, "at": [0, 0, 5]},
        {"op": "fuse", "a": 0, "b": 1},
        {"op": "cyl", "r": 3, "h": 15},
        {"op": "cut", "a": 2, "b": 3},
    ])
    feats = geo.cylindrical_features(s)
    convex = sorted(f.diameter for f in feats if not f.concave)
    assert convex == pytest.approx([12.0, 20.0])
    (bore,) = [f for f in feats if f.concave]
    assert bore.diameter == pytest.approx(6.0) and bore.through and bore.depth == pytest.approx(15.0)


def test_hole_through_two_fused_slabs_merges_into_one_feature():
    s = mk([
        {"op": "box", "dx": 20, "dy": 20, "dz": 5},
        {"op": "box", "dx": 20, "dy": 20, "dz": 5, "at": [0, 0, 5]},
        {"op": "fuse", "a": 0, "b": 1},
        {"op": "cyl", "r": 2, "h": 10, "at": [10, 10, 0]},
        {"op": "cut", "a": 2, "b": 3},
    ])
    (hole,) = _holes(s)
    assert hole.depth == pytest.approx(10.0) and hole.through


def test_edge_notch_is_not_a_full_hole():
    s = mk([
        {"op": "box", "dx": 20, "dy": 20, "dz": 5},
        {"op": "cyl", "r": 3, "h": 5, "at": [0, 10, 0]},
        {"op": "cut", "a": 0, "b": 1},
    ])
    (notch,) = _holes(s)
    assert not notch.full


def test_axis_distance_between_parallel_holes():
    s = mk([
        {"op": "box", "dx": 42, "dy": 42, "dz": 5},
        {"op": "cyl", "r": 1.7, "h": 5, "at": [5.5, 5.5, 0]},
        {"op": "cut", "a": 0, "b": 1},
        {"op": "cyl", "r": 1.7, "h": 5, "at": [36.5, 36.5, 0]},
        {"op": "cut", "a": 2, "b": 3},
    ])
    a, b = _holes(s)
    assert geo.axis_distance(a, b) == pytest.approx(31.0 * math.sqrt(2))


def test_fingerprint_is_stable_across_rebuilds():
    fp = geo.fingerprint(mk(PLATE))
    assert fp == geo.fingerprint(mk(PLATE))
    assert fp["extents"] == [5.0, 42.0, 42.0] and fp["solids"] == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_geometry.py -v`
Expected: FAIL with `ImportError: cannot import name 'geometry' from 'simready.bench'`

- [ ] **Step 3: Write `simready/bench/geometry.py`**

This code was prototyped against pythonocc 7.9.0 on 2026-10-04, and every case in the tests above was observed.

```python
"""Geometric measurements for the text-to-CAD benchmark checker.

Everything here works on an in-memory ``TopoDS_Shape`` and returns plain
Python values, so the checker never needs a STEP round-trip. Needs
pythonocc (sr env): import it only inside the build/check subprocess or in
tests that skip without OCC.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.BRepGProp import BRepGProp_Face, brepgprop
from OCC.Core.BRepTools import breptools
from OCC.Core.GeomAbs import GeomAbs_Cylinder
from OCC.Core.GProp import GProp_GProps
from OCC.Core.ShapeAnalysis import ShapeAnalysis_FreeBounds
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_OUT
from OCC.Core.gp import gp_Pnt, gp_Vec

from simready.occ_utils import count_shapes, count_topology, iter_faces, shape_bounding_box

Vec3 = tuple[float, float, float]

# Geometric tolerances (mm / unitless). Far below any benchmark tolerance (±0.1 mm).
_LEN_TOL = 1e-4
_ANG_TOL = 1e-6
_PROBE_MM = 0.5  # how far past a hole's end the through-probe looks


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _perp_basis(d: Vec3) -> tuple[Vec3, Vec3]:
    """Two unit vectors perpendicular to unit vector ``d`` and to each other."""
    helper: Vec3 = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
    e1 = _sub(helper, _scale(d, _dot(helper, d)))
    e1 = _scale(e1, 1.0 / _norm(e1))
    e2 = (d[1] * e1[2] - d[2] * e1[1], d[2] * e1[0] - d[0] * e1[2], d[0] * e1[1] - d[1] * e1[0])
    return e1, e2


# ----------------------------------------------------------------------------
# Scalar properties
# ----------------------------------------------------------------------------


def volume(shape: Any) -> float:
    props = GProp_GProps()
    brepgprop.VolumeProperties(shape, props)
    return props.Mass()


def surface_area(shape: Any) -> float:
    props = GProp_GProps()
    brepgprop.SurfaceProperties(shape, props)
    return props.Mass()


def sorted_extents(shape: Any) -> list[float]:
    """Bounding-box side lengths, ascending. Placement- and axis-order-invariant."""
    bb = shape_bounding_box(shape)
    return sorted([bb["xmax"] - bb["xmin"], bb["ymax"] - bb["ymin"], bb["zmax"] - bb["zmin"]])


def free_edge_count(shape: Any) -> int:
    """Edges bounding only one face. 0 for a closed (watertight) shell."""
    bounds = ShapeAnalysis_FreeBounds(shape)
    return count_shapes(bounds.GetClosedWires(), TopAbs_EDGE) + count_shapes(
        bounds.GetOpenWires(), TopAbs_EDGE
    )


# ----------------------------------------------------------------------------
# Validity gate
# ----------------------------------------------------------------------------


@dataclass
class GateResult:
    passed: bool
    reason: str  # "" when passed, else a short machine-readable cause
    brep_valid: bool
    free_edges: int
    volume: float
    solids: int


def run_gate(shape: Any, expected_solids: int = 1) -> GateResult:
    """BRep valid, closed, positive volume, expected solid count — in that order."""
    try:
        brep_valid = bool(BRepCheck_Analyzer(shape).IsValid())
    except Exception:  # noqa: BLE001 — OCC raises on degenerate shapes
        brep_valid = False
    free = free_edge_count(shape)
    vol = volume(shape)
    solids = count_topology(shape)["solid_count"]
    if not brep_valid:
        reason = "brep_invalid"
    elif free > 0:
        reason = "open_shell"
    elif vol <= 0:
        reason = "non_positive_volume"
    elif solids != expected_solids:
        reason = f"solid_count {solids} != {expected_solids}"
    else:
        reason = ""
    return GateResult(reason == "", reason, brep_valid, free, vol, solids)


# ----------------------------------------------------------------------------
# Cylindrical features (holes and bosses)
# ----------------------------------------------------------------------------


@dataclass
class CylFeature:
    """One cylindrical feature, merged from all coaxial same-radius faces.

    ``concave`` = material outside the cylinder (hole/bore); convex = boss,
    shaft or outer tube wall. ``t0``/``t1`` are absolute positions along
    ``direction`` measured from ``axis_point``.
    """

    diameter: float
    axis_point: Vec3  # point on the axis closest to the origin
    direction: Vec3  # unit, canonical sign (first non-zero of z, y, x is > 0)
    t0: float
    t1: float
    sweep: float  # total angular coverage, radians (2*pi = full cylinder)
    concave: bool
    through: bool | None = None  # holes only; None for convex features

    @property
    def depth(self) -> float:
        return self.t1 - self.t0

    @property
    def full(self) -> bool:
        return self.sweep >= 2 * math.pi - 1e-3


def _canonical(d: Vec3) -> bool:
    """True if ``d`` already has the canonical sign."""
    for c in (d[2], d[1], d[0]):
        if abs(c) > _ANG_TOL:
            return c > 0
    return True


def _cyl_patch(face: Any) -> CylFeature | None:
    surf = BRepAdaptor_Surface(face, True)
    if surf.GetType() != GeomAbs_Cylinder:
        return None
    cyl = surf.Cylinder()
    ax = cyl.Axis()
    loc: Vec3 = (ax.Location().X(), ax.Location().Y(), ax.Location().Z())
    d: Vec3 = (ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z())
    u0, u1, v0, v1 = breptools.UVBounds(face)
    pnt, nrm = gp_Pnt(), gp_Vec()
    # BRepGProp_Face respects face orientation: the normal points out of material.
    BRepGProp_Face(face).Normal((u0 + u1) / 2, (v0 + v1) / 2, pnt, nrm)
    rel = _sub((pnt.X(), pnt.Y(), pnt.Z()), loc)
    radial = _sub(rel, _scale(d, _dot(rel, d)))
    concave = _dot((nrm.X(), nrm.Y(), nrm.Z()), radial) < 0
    if not _canonical(d):
        d, v0, v1 = _scale(d, -1.0), -v1, -v0
    axis_point = _sub(loc, _scale(d, _dot(loc, d)))
    base = _dot(loc, d)
    return CylFeature(2 * cyl.Radius(), axis_point, d, base + v0, base + v1, u1 - u0, concave)


def _same_axis(a: CylFeature, b: CylFeature) -> bool:
    return (
        a.concave == b.concave
        and abs(a.diameter - b.diameter) < _LEN_TOL
        and abs(_dot(a.direction, b.direction) - 1.0) < _ANG_TOL
        and _norm(_sub(a.axis_point, b.axis_point)) < _LEN_TOL
    )


def _probe_open(shape: Any, feat: CylFeature, t: float) -> bool:
    """True if four points at 0.9 r around the axis at position ``t`` are all outside material."""
    r = 0.45 * feat.diameter
    e1, e2 = _perp_basis(feat.direction)
    centre = _add(feat.axis_point, _scale(feat.direction, t))
    for e in (e1, _scale(e1, -1.0), e2, _scale(e2, -1.0)):
        q = _add(centre, _scale(e, r))
        if BRepClass3d_SolidClassifier(shape, gp_Pnt(*q), _LEN_TOL).State() != TopAbs_OUT:
            return False
    return True


def cylindrical_features(shape: Any) -> list[CylFeature]:
    """All cylindrical features, merged per (axis, diameter, concavity).

    Coaxial same-diameter faces merge when their axial spans touch or overlap
    (OCC may split one hole into several faces). A hole is ``through`` when
    probes ``_PROBE_MM`` past both ends, at 0.9 r, are all outside material —
    so the small hole of a counterbore is through and the counterbore is not.
    """
    merged: list[CylFeature] = []
    for _, face in iter_faces(shape):
        patch = _cyl_patch(face)
        if patch is None:
            continue
        for feat in merged:
            touching = patch.t0 <= feat.t1 + _LEN_TOL and patch.t1 >= feat.t0 - _LEN_TOL
            if _same_axis(feat, patch) and touching:
                same_span = abs(patch.t0 - feat.t0) < _LEN_TOL and abs(patch.t1 - feat.t1) < _LEN_TOL
                feat.sweep = feat.sweep + patch.sweep if same_span else max(feat.sweep, patch.sweep)
                feat.t0, feat.t1 = min(feat.t0, patch.t0), max(feat.t1, patch.t1)
                break
        else:
            merged.append(patch)
    for feat in merged:
        if feat.concave:
            feat.through = _probe_open(shape, feat, feat.t0 - _PROBE_MM) and _probe_open(
                shape, feat, feat.t1 + _PROBE_MM
            )
    return merged


def axis_distance(a: CylFeature, b: CylFeature) -> float:
    """Distance between two parallel axes (hole-pattern checks)."""
    diff = _sub(b.axis_point, a.axis_point)
    return _norm(_sub(diff, _scale(a.direction, _dot(diff, a.direction))))


# ----------------------------------------------------------------------------
# Replay fingerprint
# ----------------------------------------------------------------------------


def fingerprint(shape: Any) -> dict[str, Any]:
    """Rounded geometric summary, equal across rebuilds of the same spec on the
    same OCC version. ``replay`` compares this instead of a STEP byte hash,
    because STEP headers carry a timestamp."""
    topo = count_topology(shape)
    return {
        "volume": round(volume(shape), 2),
        "area": round(surface_area(shape), 2),
        "extents": [round(x, 3) for x in sorted_extents(shape)],
        "faces": topo["face_count"],
        "edges": topo["edge_count"],
        "solids": topo["solid_count"],
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_geometry.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add simready/bench/geometry.py tests/test_bench_geometry.py
git commit -m "feat(bench): geometry - validity gate, hole/boss features, replay fingerprint"
```

---

### Task 4: Checker + reference-spec positive controls

**Files:**
- Create: `simready/bench/checker.py`
- Create: `tests/test_bench_checker.py`
- Create: `tests/test_bench_reference_specs.py`

**Interfaces:**
- Consumes: Task 1 check models, `in_range`, `CHECKER_VERSION`; Task 3 `geometry`.
- Produces: `grade_shape(shape, checks: list[Check], expected_solids: int = 1) -> dict` with keys `checker_version, gate{passed, reason, brep_valid, free_edges, volume, solids}, checks[{type, status, detail}], n_pass, n_fail, n_not_checked, partial, passed, failure_class`. Failure-class strings `F5_invalid_solid`, `F6_dimension_miss`, `F7_feature_miss`; `PASS/FAIL/NOT_CHECKED` constants.

- [ ] **Step 1: Write the failing checker tests (known pass + known fail per check type)**

`tests/test_bench_checker.py`:

```python
"""Checker: one known-pass and one known-fail per check type (spec done-criterion 2)."""

from __future__ import annotations

import pytest

pytest.importorskip("OCC.Core.BRepPrimAPI")

from simready.bench.checker import grade_shape  # noqa: E402
from simready.bench.concepts import CHECK_LIST  # noqa: E402
from simready.gen.build import build_shape  # noqa: E402
from simready.gen.spec import PartSpec  # noqa: E402


def mk(steps):
    return build_shape(PartSpec.model_validate({"steps": steps}))


NEMA = mk([
    {"op": "box", "dx": 42, "dy": 42, "dz": 5},
    {"op": "cyl", "r": 11.25, "h": 5, "at": [21, 21, 0]},
    {"op": "cut", "a": 0, "b": 1},
    {"op": "cyl", "r": 1.7, "h": 5, "at": [5.5, 5.5, 0]},
    {"op": "cut", "a": 2, "b": 3},
    {"op": "cyl", "r": 1.7, "h": 5, "at": [36.5, 5.5, 0]},
    {"op": "cut", "a": 4, "b": 5},
    {"op": "cyl", "r": 1.7, "h": 5, "at": [5.5, 36.5, 0]},
    {"op": "cut", "a": 6, "b": 7},
    {"op": "cyl", "r": 1.7, "h": 5, "at": [36.5, 36.5, 0]},
    {"op": "cut", "a": 8, "b": 9},
])
FLANGE = mk([
    {"op": "cyl", "r": 10, "h": 5},
    {"op": "cyl", "r": 6, "h": 10, "at": [0, 0, 5]},
    {"op": "fuse", "a": 0, "b": 1},
    {"op": "cyl", "r": 3, "h": 15},
    {"op": "cut", "a": 2, "b": 3},
])
SQ = [[30.9, 31.1]] * 4 + [[43.74, 43.94]] * 2


def grade(shape, checks, solids=1):
    return grade_shape(shape, CHECK_LIST.validate_python(checks), solids)


@pytest.mark.parametrize(
    "shape,check,expected",
    [
        (NEMA, {"type": "bbox_sorted", "ranges": [[4.9, 5.1], [41.9, 42.1], [41.9, 42.1]]}, "pass"),
        (NEMA, {"type": "bbox_sorted", "ranges": [[5.9, 6.1], [41.9, 42.1], [41.9, 42.1]]}, "fail"),
        (NEMA, {"type": "bbox_min_dim", "min": 4.0}, "pass"),
        (NEMA, {"type": "bbox_min_dim", "min": 6.0}, "fail"),
        (NEMA, {"type": "volume", "range": [6500, 6800]}, "pass"),
        (NEMA, {"type": "volume", "range": [8000, 9000]}, "fail"),
        (NEMA, {"type": "hole_set", "diameter": [3.3, 3.5], "count": [4, 4], "through": True, "pattern": SQ}, "pass"),
        (NEMA, {"type": "hole_set", "diameter": [3.3, 3.5], "count": [6, 6]}, "fail"),
        (NEMA, {"type": "hole_set", "diameter": [3.3, 3.5], "count": [4, 4],
                "pattern": [[25.9, 26.1]] * 4 + [[36.7, 36.9]] * 2}, "fail"),
        (NEMA, {"type": "hole_set", "diameter": [3.3, 3.5], "count": [4, 4], "through": False}, "fail"),
        (NEMA, {"type": "bore", "diameter": [22.4, 22.6], "through": True}, "pass"),
        (NEMA, {"type": "bore", "diameter": [7.9, 8.1]}, "fail"),
        (FLANGE, {"type": "bore", "diameter": [5.9, 6.1], "depth_min": 15.0}, "pass"),
        (FLANGE, {"type": "bore", "diameter": [5.9, 6.1], "depth_min": 20.0}, "fail"),
        (FLANGE, {"type": "boss", "diameter": [11.9, 12.1], "height_min": 9.5}, "pass"),
        (FLANGE, {"type": "boss", "diameter": [11.9, 12.1], "height_min": 12.0}, "fail"),
        (FLANGE, {"type": "any_of", "checks": [{"type": "bore", "diameter": [7.9, 8.1]},
                                              {"type": "bore", "diameter": [5.9, 6.1]}]}, "pass"),
        (FLANGE, {"type": "any_of", "checks": [{"type": "bore", "diameter": [7.9, 8.1]},
                                              {"type": "boss", "diameter": [29, 31]}]}, "fail"),
        (FLANGE, {"type": "not_checked", "what": "flange outline"}, "not_checked"),
    ],
)
def test_each_check_type_pass_and_fail(shape, check, expected):
    report = grade(shape, [check])
    assert report["checks"][0]["status"] == expected, report["checks"][0]["detail"]


def test_attempt_passes_only_if_no_check_fails_and_partial_is_logged():
    report = grade(NEMA, [
        {"type": "bbox_min_dim", "min": 4.0},
        {"type": "bore", "diameter": [7.9, 8.1]},
        {"type": "not_checked", "what": "outline"},
    ])
    assert report["passed"] is False
    assert report["partial"] == pytest.approx(0.5)
    assert (report["n_pass"], report["n_fail"], report["n_not_checked"]) == (1, 1, 1)
    assert report["failure_class"] == "F6_dimension_miss"


def test_first_failing_check_sets_class_hole_set_is_feature_miss():
    report = grade(NEMA, [{"type": "hole_set", "diameter": [3.3, 3.5], "count": [6, 6]},
                          {"type": "bbox_min_dim", "min": 6.0}])
    assert report["failure_class"] == "F7_feature_miss"


def test_gate_failure_short_circuits_checks():
    two = mk([
        {"op": "box", "dx": 10, "dy": 10, "dz": 10},
        {"op": "box", "dx": 10, "dy": 10, "dz": 10, "at": [50, 0, 0]},
        {"op": "fuse", "a": 0, "b": 1},
    ])
    report = grade(two, [{"type": "bbox_min_dim", "min": 1.0}])
    assert report["gate"]["passed"] is False and report["checks"] == []
    assert report["failure_class"] == "F5_invalid_solid" and report["partial"] == 0.0


def test_all_pass_has_no_failure_class():
    report = grade(NEMA, [{"type": "bbox_min_dim", "min": 4.0}])
    assert report["passed"] is True and report["failure_class"] is None
```

`tests/test_bench_reference_specs.py`:

```python
"""Positive controls: every in-vocab concept's reference spec passes all of its
own checks, in all three phrasings (spec done-criterion 1, §1 rule 7)."""

from __future__ import annotations

import pytest

pytest.importorskip("OCC.Core.BRepPrimAPI")

from simready.bench.checker import grade_shape  # noqa: E402
from simready.bench.concepts import CONCEPTS_V1, PHRASINGS, load_concepts  # noqa: E402
from simready.gen.build import build_shape  # noqa: E402
from simready.gen.spec import PartSpec  # noqa: E402

IN_VOCAB = [c for c in load_concepts(CONCEPTS_V1) if c.in_vocab]


@pytest.mark.parametrize("concept", IN_VOCAB, ids=[c.concept_id for c in IN_VOCAB])
def test_reference_spec_passes_own_checks(concept):
    shape = build_shape(PartSpec.model_validate(concept.reference_spec))
    for phrasing in PHRASINGS:
        report = grade_shape(shape, getattr(concept.checks, phrasing), concept.solids)
        failed = [c for c in report["checks"] if c["status"] == "fail"]
        assert report["gate"]["passed"], (phrasing, report["gate"])
        assert not failed, (phrasing, failed)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_checker.py tests/test_bench_reference_specs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'simready.bench.checker'`

- [ ] **Step 3: Write `simready/bench/checker.py`**

```python
"""Grade a built shape against a concept's checks. Needs OCC (via geometry).

Order: validity gate first (fail => F5, no checks run), then every check in
list order. The attempt passes iff the gate passes and no check fails;
``not_checked`` never fails. ``partial`` = passed / (passed + failed) is
logged for analysis and as SP3's dense reward.
"""

from __future__ import annotations

import itertools
from typing import Any

from simready.bench import CHECKER_VERSION
from simready.bench import geometry as geo
from simready.bench.concepts import (
    AnyOf,
    BBoxMinDim,
    BBoxSorted,
    Boss,
    Bore,
    Check,
    HoleSet,
    NotChecked,
    VolumeCheck,
    in_range,
)

PASS, FAIL, NOT_CHECKED = "pass", "fail", "not_checked"
F5 = "F5_invalid_solid"
F6 = "F6_dimension_miss"
F7 = "F7_feature_miss"
_EPS = 1e-6


def _holes(features: list[geo.CylFeature], check: HoleSet | Bore) -> list[geo.CylFeature]:
    return [
        f
        for f in features
        if f.concave
        and f.full
        and in_range(f.diameter, check.diameter)
        and (check.through is None or f.through == check.through)
        and (check.depth_min is None or f.depth >= check.depth_min - _EPS)
    ]


def _status(ok: bool) -> str:
    return PASS if ok else FAIL


def _eval(check: Check, shape: Any, features: list[geo.CylFeature]) -> tuple[str, str]:
    if isinstance(check, NotChecked):
        return NOT_CHECKED, check.what
    if isinstance(check, BBoxSorted):
        ext = geo.sorted_extents(shape)
        ok = all(in_range(e, r) for e, r in zip(ext, check.ranges))
        return _status(ok), f"extents {[round(e, 3) for e in ext]} vs {list(check.ranges)}"
    if isinstance(check, BBoxMinDim):
        smallest = geo.sorted_extents(shape)[0]
        return _status(smallest >= check.min - _EPS), f"min extent {smallest:.3f} vs >= {check.min}"
    if isinstance(check, VolumeCheck):
        vol = geo.volume(shape)
        return _status(in_range(vol, check.range)), f"volume {vol:.1f} vs {check.range}"
    if isinstance(check, HoleSet):
        holes = _holes(features, check)
        if not in_range(len(holes), check.count):
            return FAIL, f"{len(holes)} matching holes vs count {check.count}"
        if check.pattern is None:
            return PASS, f"{len(holes)} matching holes"
        dists = sorted(geo.axis_distance(a, b) for a, b in itertools.combinations(holes, 2))
        ranges = sorted(check.pattern, key=lambda r: float("-inf") if r[0] is None else r[0])
        ok = all(in_range(d, r) for d, r in zip(dists, ranges))
        return _status(ok), f"pairwise distances {[round(d, 3) for d in dists]} vs {ranges}"
    if isinstance(check, Bore):
        hits = _holes(features, check)
        found = sorted(round(f.diameter, 3) for f in features if f.concave and f.full)
        return _status(bool(hits)), f"{len(hits)} matching bores; hole diameters {found}"
    if isinstance(check, Boss):
        hits = [
            f
            for f in features
            if not f.concave
            and f.full
            and in_range(f.diameter, check.diameter)
            and (check.height_min is None or f.depth >= check.height_min - _EPS)
        ]
        found = sorted(round(f.diameter, 3) for f in features if not f.concave and f.full)
        return _status(in_range(len(hits), check.count)), f"{len(hits)} matching bosses; convex diameters {found}"
    if isinstance(check, AnyOf):
        subs = [_eval(c, shape, features) for c in check.checks]
        return _status(any(s == PASS for s, _ in subs)), " | ".join(d for _, d in subs)
    raise TypeError(f"unknown check type {type(check).__name__}")


def _class_of(check: Check) -> str:
    return F7 if isinstance(check, HoleSet) else F6


def grade_shape(shape: Any, checks: list[Check], expected_solids: int = 1) -> dict[str, Any]:
    gate = geo.run_gate(shape, expected_solids)
    gate_d = {
        "passed": gate.passed,
        "reason": gate.reason,
        "brep_valid": gate.brep_valid,
        "free_edges": gate.free_edges,
        "volume": round(gate.volume, 3),
        "solids": gate.solids,
    }
    report: dict[str, Any] = {"checker_version": CHECKER_VERSION, "gate": gate_d, "checks": []}
    if not gate.passed:
        report.update(n_pass=0, n_fail=0, n_not_checked=0, partial=0.0, passed=False, failure_class=F5)
        return report
    features = geo.cylindrical_features(shape)
    first_fail: str | None = None
    for check in checks:
        status, detail = _eval(check, shape, features)
        report["checks"].append({"type": check.type, "status": status, "detail": detail})
        if status == FAIL and first_fail is None:
            first_fail = _class_of(check)
    statuses = [c["status"] for c in report["checks"]]
    n_pass, n_fail = statuses.count(PASS), statuses.count(FAIL)
    report.update(
        n_pass=n_pass,
        n_fail=n_fail,
        n_not_checked=statuses.count(NOT_CHECKED),
        partial=n_pass / (n_pass + n_fail) if n_pass + n_fail else 1.0,
        passed=n_fail == 0,
        failure_class=first_fail,
    )
    return report
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_checker.py tests/test_bench_reference_specs.py -v`
Expected: all checker cases pass, plus one passing reference test per in-vocab concept. A failing reference test means the concept or its checks are wrong. Fix the concept line (re-run Task 2's file test), never the checker, unless a checker case also fails.

- [ ] **Step 5: Commit**

```bash
git add simready/bench/checker.py tests/test_bench_checker.py tests/test_bench_reference_specs.py simready/bench/prompts/concepts_v1.jsonl
git commit -m "feat(bench): checker with pass/fail tests per type; reference specs as positive controls"
```

---

### Task 5: Attempt pipeline (parse, classify, grade in a subprocess)

**Files:**
- Create: `simready/bench/attempt.py`
- Create: `tests/test_bench_attempt.py`

**Interfaces:**
- Consumes: `PartSpec`, `build_shape`, `grade_shape`, `fingerprint`, `CHECK_LIST`.
- Produces: `ParsedReply(spec, via, n_tool_calls, error)`; `parse_reply(tool_calls: list[dict], content: str | None) -> ParsedReply` (tool-call dicts have `name`, `arguments`); `classify_spec(spec: dict) -> tuple[str | None, list[str]]`; `grade_spec(spec_dict, checks, expected_solids=1, timeout_s=60.0) -> dict` with `stage` ∈ `graded|build_error|checker_error|timeout`; `evaluate_reply(parsed, checks, expected_solids, grade=grade_spec) -> dict` with keys `via, n_tool_calls, spec, schema_errors, build_error, fingerprint, check_report, partial, passed, failure_class`. Constants `F1, F2, F3, F4, F8, F9, INFRA, CHECKER_ERROR, KNOWN_OPS, GRADE_TIMEOUT_S`.

- [ ] **Step 1: Write the failing tests**

`tests/test_bench_attempt.py`:

```python
"""Attempt pipeline: reply parsing, pre-build classes, subprocess grading."""

from __future__ import annotations

import json

import pytest

from simready.bench.attempt import (
    CHECKER_ERROR,
    F1,
    F2,
    F3,
    F4,
    F8,
    F9,
    ParsedReply,
    classify_spec,
    evaluate_reply,
    grade_spec,
    parse_reply,
)

SPEC = {"steps": [{"op": "box", "dx": 40, "dy": 30, "dz": 5}]}


def test_parse_tool_call_with_spec_key():
    r = parse_reply([{"name": "build_part", "arguments": json.dumps({"spec": SPEC})}], None)
    assert r.spec == SPEC and r.via == "tool" and r.n_tool_calls == 1


def test_parse_tool_call_with_steps_at_top_and_stringified_spec():
    r1 = parse_reply([{"name": "build_part", "arguments": json.dumps(SPEC)}], None)
    r2 = parse_reply([{"name": "build_part", "arguments": json.dumps({"spec": json.dumps(SPEC)})}], None)
    assert r1.spec == SPEC and r2.spec == SPEC


def test_parse_json_in_text_fenced_and_bare():
    fenced = "Here you go:\n```json\n" + json.dumps(SPEC, indent=2) + "\n```"
    bare = "Plan: a plate. " + json.dumps({"spec": SPEC}) + " Done."
    assert parse_reply([], fenced).spec == SPEC and parse_reply([], fenced).via == "text"
    assert parse_reply([], bare).spec == SPEC


def test_parse_nothing_usable():
    r = parse_reply([], "I can't build that with these operations.")
    assert r.spec is None and r.via is None and "no tool call" in r.error
    bad = parse_reply([{"name": "build_part", "arguments": "{not json"}], None)
    assert bad.spec is None and bad.via == "tool"


def test_classify_unknown_op_is_f9_before_schema():
    cls, errs = classify_spec({"steps": [{"op": "box", "dx": 1, "dy": 1, "dz": 1},
                                         {"op": "fillet", "edges": "all", "r": 1}]})
    assert cls == F9 and "fillet" in errs[0]


def test_classify_schema_vs_reference():
    assert classify_spec({"steps": [{"op": "box", "dx": -1, "dy": 1, "dz": 1}]})[0] == F2
    assert classify_spec({"steps": [{"dx": 1}]})[0] == F2  # missing op is schema, not F9
    orphan = {"steps": [{"op": "box", "dx": 1, "dy": 1, "dz": 1}, {"op": "cyl", "r": 1, "h": 1}]}
    assert classify_spec(orphan)[0] == F3
    assert classify_spec(SPEC) == (None, [])


def _fake_grade(stage, **extra):
    def grade(spec, checks, solids):
        return {"stage": stage, **extra}
    return grade


def test_evaluate_reply_maps_stages_to_classes():
    p = ParsedReply(SPEC, "tool", 1)
    assert evaluate_reply(ParsedReply(None, None, 0, "x"), [], 1)["failure_class"] == F1
    assert evaluate_reply(p, [], 1, grade=_fake_grade("timeout", error="t"))["failure_class"] == F8
    assert evaluate_reply(p, [], 1, grade=_fake_grade("build_error", error="b"))["failure_class"] == F4
    assert evaluate_reply(p, [], 1, grade=_fake_grade("checker_error", error="c"))["failure_class"] == CHECKER_ERROR
    report = {"partial": 1.0, "passed": True, "failure_class": None}
    out = evaluate_reply(p, [], 1, grade=_fake_grade("graded", fingerprint={"v": 1}, report=report))
    assert out["passed"] is True and out["failure_class"] is None and out["fingerprint"] == {"v": 1}


def test_grade_spec_in_subprocess_end_to_end():
    pytest.importorskip("OCC.Core.BRepPrimAPI")
    spec = {"steps": [{"op": "box", "dx": 40, "dy": 30, "dz": 5},
                      {"op": "cyl", "r": 3, "h": 5, "at": [20, 15, 0]},
                      {"op": "cut", "a": 0, "b": 1}]}
    checks = [{"type": "hole_set", "diameter": [5.9, 6.1], "count": [1, 1], "through": True}]
    out = grade_spec(spec, checks, 1)
    assert out["stage"] == "graded", out
    assert out["report"]["passed"] is True and out["fingerprint"]["solids"] == 1


def test_grade_spec_timeout_is_reported_not_raised():
    pytest.importorskip("OCC.Core.BRepPrimAPI")
    out = grade_spec(SPEC, [], 1, timeout_s=0.01)
    assert out["stage"] == "timeout"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_attempt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'simready.bench.attempt'`

- [ ] **Step 3: Write `simready/bench/attempt.py`**

```python
"""One benchmark attempt: parse a model reply, classify pre-build failures,
then build + grade in a killable spawn subprocess.

Failure classes (spec §3) — one primary class per failed attempt, first
failing stage wins: F1 no_parse, F2 schema, F3 reference, F9 out_of_vocab
(checked before schema, because the DSL's discriminator would otherwise
report an unknown op as F2), F4 build_error, F8 timeout, then the checker's
F5/F6/F7. ``infra_error`` and ``checker_error`` are excluded from scoring.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import queue as queue_mod
import re
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from simready.gen.spec import PartSpec

KNOWN_OPS = frozenset({"box", "cyl", "fuse", "cut"})
GRADE_TIMEOUT_S = 60.0

F1 = "F1_no_parse"
F2 = "F2_schema"
F3 = "F3_reference"
F4 = "F4_build_error"
F8 = "F8_timeout"
F9 = "F9_out_of_vocab"
INFRA = "infra_error"
CHECKER_ERROR = "checker_error"


@dataclass
class ParsedReply:
    spec: dict | None
    via: str | None  # "tool" | "text" | None
    n_tool_calls: int
    error: str = ""


_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def _as_spec(obj: Any) -> dict | None:
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return None
    if not isinstance(obj, dict):
        return None
    if "steps" in obj:
        return obj
    if "spec" in obj:
        return _as_spec(obj["spec"])
    return None


def _spec_in_text(text: str) -> dict | None:
    for match in _FENCE.finditer(text):
        spec = _as_spec(match.group(1).strip())
        if spec is not None:
            return spec
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        spec = _as_spec(obj)
        if spec is not None:
            return spec
    return None


def parse_reply(tool_calls: list[dict], content: str | None) -> ParsedReply:
    """Accept a ``build_part`` tool call or a JSON spec in text (logged as ``via``)."""
    for call in tool_calls:
        if call.get("name") == "build_part":
            spec = _as_spec(call.get("arguments") or "")
            if spec is not None:
                return ParsedReply(spec, "tool", len(tool_calls))
            return ParsedReply(None, "tool", len(tool_calls), "build_part arguments are not a spec")
    if content:
        spec = _spec_in_text(content)
        if spec is not None:
            return ParsedReply(spec, "text", len(tool_calls))
    return ParsedReply(None, None, len(tool_calls), "no tool call and no JSON spec in text")


def classify_spec(spec: dict) -> tuple[str | None, list[str]]:
    """Pre-build classification: (failure_class or None, error messages)."""
    steps = spec.get("steps")
    if isinstance(steps, list):
        unknown = sorted(
            {str(s["op"]) for s in steps if isinstance(s, dict) and "op" in s and s["op"] not in KNOWN_OPS}
        )
        if unknown:
            return F9, [f"unknown ops: {unknown}"]
    try:
        PartSpec.model_validate(spec)
    except ValidationError as exc:
        errors = exc.errors()
        messages = [f"{'.'.join(map(str, e['loc'])) or '<root>'}: {e['msg']}" for e in errors]
        # Reference/orphan rules are PartSpec model validators: root loc, value_error.
        if all(not e["loc"] and e["type"] == "value_error" for e in errors):
            return F3, messages
        return F2, messages
    return None, []


def _grade_worker(spec_dict: dict, checks_json: list, expected_solids: int, out_queue) -> None:
    """Spawn-child entry point. Build errors and checker errors are kept apart:
    the first is the model's failure, the second is ours."""
    from simready.gen.build import build_shape

    try:
        shape = build_shape(PartSpec.model_validate(spec_dict))
        if shape is None or shape.IsNull():
            raise RuntimeError("build produced a null shape")
    except Exception as exc:  # noqa: BLE001 — any kernel failure is F4
        out_queue.put({"stage": "build_error", "error": f"{type(exc).__name__}: {exc}"})
        return
    try:
        from simready.bench.checker import grade_shape
        from simready.bench.concepts import CHECK_LIST
        from simready.bench.geometry import fingerprint

        report = grade_shape(shape, CHECK_LIST.validate_python(checks_json), expected_solids)
        out_queue.put({"stage": "graded", "fingerprint": fingerprint(shape), "report": report})
    except Exception as exc:  # noqa: BLE001 — our bug, excluded from scoring
        out_queue.put({"stage": "checker_error", "error": f"{type(exc).__name__}: {exc}"})


def grade_spec(
    spec_dict: dict,
    checks: list,
    expected_solids: int = 1,
    timeout_s: float = GRADE_TIMEOUT_S,
) -> dict:
    """Build + gate + check in a spawn child; killed after ``timeout_s``."""
    checks_json = [c.model_dump() if hasattr(c, "model_dump") else c for c in checks]
    ctx = mp.get_context("spawn")
    out_queue = ctx.Queue()
    proc = ctx.Process(target=_grade_worker, args=(spec_dict, checks_json, expected_solids, out_queue))
    proc.start()
    try:
        result = out_queue.get(timeout=timeout_s)  # read before join: large payloads block the child
    except queue_mod.Empty:
        result = {"stage": "timeout", "error": f"build/check over {timeout_s:g}s"}
    finally:
        proc.join(1)
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            if proc.is_alive():
                proc.kill()
    return result


def evaluate_reply(
    parsed: ParsedReply,
    checks: list,
    expected_solids: int,
    grade: Callable[[dict, list, int], dict] = grade_spec,
) -> dict:
    out: dict[str, Any] = {
        "via": parsed.via,
        "n_tool_calls": parsed.n_tool_calls,
        "spec": parsed.spec,
        "schema_errors": [],
        "build_error": None,
        "fingerprint": None,
        "check_report": None,
        "partial": 0.0,
        "passed": False,
        "failure_class": None,
    }
    if parsed.spec is None:
        out.update(failure_class=F1, schema_errors=[parsed.error])
        return out
    cls, errors = classify_spec(parsed.spec)
    if cls is not None:
        out.update(failure_class=cls, schema_errors=errors)
        return out
    result = grade(parsed.spec, checks, expected_solids)
    stage_class = {"timeout": F8, "build_error": F4, "checker_error": CHECKER_ERROR}
    if result["stage"] in stage_class:
        out.update(failure_class=stage_class[result["stage"]], build_error=result["error"])
        return out
    report = result["report"]
    out.update(
        fingerprint=result["fingerprint"],
        check_report=report,
        partial=report["partial"],
        passed=report["passed"],
        failure_class=report["failure_class"],
    )
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_attempt.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add simready/bench/attempt.py tests/test_bench_attempt.py
git commit -m "feat(bench): attempt pipeline - reply parsing, F1-F9 classes, killable grading"
```

---

### Task 6: Prompting, providers, smoke command; verify model IDs live

**Files:**
- Create: `simready/bench/prompting.py`
- Create: `simready/bench/providers.py`
- Create: `simready/bench/providers.json`
- Create: `simready/bench/__main__.py` (with `smoke`; later tasks add subcommands)
- Create: `tests/test_bench_providers.py`

**Split (user decision 2026-10-05):** steps 1–5, 7 and 8 run now ("Task 6-code"). Step 6 (live key and model-id verification) runs after Task 9 ("Task 6-live"), once the user gives the provider's base URL. The key is from a provider the user calls "D Labs"; nothing about it may be assumed.

**Interfaces:**
- Consumes: `simready.copilot.tools.TOOL_SCHEMAS`; `parse_reply`, `classify_spec`.
- Produces: `SYSTEM_PROMPT: str`; `BUILD_PART_TOOL: dict`; `build_messages(prompt) -> list[dict]`; `system_prompt_sha256() -> str`. `Provider` dataclass (`alias, base_url, model, key_env, rpm, max_tokens, supports_seed, extra_body`); `load_providers(path=PROVIDERS_JSON) -> dict[str, Provider]`; `resolve_key(provider, env=os.environ, dotenv_path=...) -> str`; `RateLimiter(rpm, clock, sleep).wait()`; `InfraError`, `QuotaExhausted`; `ModelClient(provider, client=None, sleep=time.sleep, max_retries=6, initial_backoff=2.0, max_backoff=120.0).complete(messages, tools, temperature, seed=None) -> dict` with keys `tool_calls, content, finish_reason, model_returned, usage, latency_s`. CLI `main(argv) -> int`.

- [ ] **Step 1: Write the failing tests**

`tests/test_bench_providers.py`:

```python
"""Provider client: retries, quota stop, key lookup, rate limit, prompt hash. No network."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from simready.bench.prompting import BUILD_PART_TOOL, SYSTEM_PROMPT, build_messages, system_prompt_sha256
from simready.bench.providers import (
    PROVIDERS_JSON,
    InfraError,
    ModelClient,
    Provider,
    QuotaExhausted,
    RateLimiter,
    load_providers,
    resolve_key,
)

P = Provider("t", "http://x/v1", "m", "BENCH_TEST_KEY", 0, 512, True, {})
REQ = httpx.Request("POST", "http://x/v1/chat/completions")


def _resp(content=None, calls=()):
    tool_calls = [SimpleNamespace(function=SimpleNamespace(name=n, arguments=a)) for n, a in calls]
    msg = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="stop")],
        model="m-2026",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _client(outcomes, provider=P, **kw):
    comp = FakeCompletions(outcomes)
    fake = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    return ModelClient(provider, client=fake, sleep=lambda s: None, **kw), comp


def _rate_limited():
    return openai.RateLimitError("slow down", response=httpx.Response(429, request=REQ), body=None)


def test_complete_returns_tool_calls_usage_and_passes_seed():
    client, comp = _client([_resp(calls=[("build_part", json.dumps({"spec": {"steps": []}}))])])
    out = client.complete(build_messages("x"), [BUILD_PART_TOOL], 0.7, seed=3)
    assert out["tool_calls"][0]["name"] == "build_part"
    assert out["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}
    assert out["model_returned"] == "m-2026"
    assert comp.calls[0]["seed"] == 3 and comp.calls[0]["temperature"] == 0.7


def test_seed_not_sent_when_unsupported():
    no_seed = Provider("t", "http://x/v1", "m", "K", 0, 512, False, {})
    client, comp = _client([_resp(content="hi")], provider=no_seed)
    client.complete(build_messages("x"), [BUILD_PART_TOOL], 0.7, seed=3)
    assert "seed" not in comp.calls[0]


def test_transient_errors_retry_then_succeed():
    server = openai.InternalServerError("boom", response=httpx.Response(500, request=REQ), body=None)
    client, comp = _client([server, _rate_limited(), _resp(content="ok")])
    assert client.complete(build_messages("x"), [], 0.7)["content"] == "ok"
    assert len(comp.calls) == 3


def test_persistent_429_means_quota_exhausted():
    client, _ = _client([_rate_limited() for _ in range(3)], max_retries=3)
    with pytest.raises(QuotaExhausted):
        client.complete(build_messages("x"), [], 0.7)


def test_persistent_connection_error_is_infra():
    client, _ = _client([openai.APIConnectionError(request=REQ) for _ in range(3)], max_retries=3)
    with pytest.raises(InfraError):
        client.complete(build_messages("x"), [], 0.7)


def test_client_error_is_infra_without_retry():
    bad = openai.BadRequestError("bad param", response=httpx.Response(400, request=REQ), body=None)
    client, comp = _client([bad, _resp(content="never")])
    with pytest.raises(InfraError, match="HTTP 400"):
        client.complete(build_messages("x"), [], 0.7)
    assert len(comp.calls) == 1


def test_resolve_key_env_then_dotenv_never_echoes(tmp_path):
    assert resolve_key(P, env={"BENCH_TEST_KEY": "sk-1"}, dotenv_path=tmp_path / ".env") == "sk-1"
    (tmp_path / ".env").write_text("BENCH_TEST_KEY=sk-2\n", encoding="utf-8")
    assert resolve_key(P, env={}, dotenv_path=tmp_path / ".env") == "sk-2"
    with pytest.raises(KeyError) as exc:
        resolve_key(P, env={}, dotenv_path=tmp_path / "missing.env")
    assert "sk-" not in str(exc.value)


def test_rate_limiter_spaces_calls():
    t = {"now": 0.0}
    slept = []
    lim = RateLimiter(60, clock=lambda: t["now"], sleep=slept.append)
    lim.wait()
    lim.wait()
    assert slept == [pytest.approx(1.0)]


def test_bench_tool_drops_agent_only_instructions():
    desc = BUILD_PART_TOOL["function"]["description"]
    assert "analyze_geometry" not in desc and "axis is +Z" in desc
    assert "timeout_seconds" not in BUILD_PART_TOOL["function"]["parameters"]["properties"]
    assert "say so" in SYSTEM_PROMPT
    assert len(system_prompt_sha256()) == 64


@pytest.mark.live_llm  # deselected by default until Task 6-live fills in verified values
def test_providers_json_is_complete():
    providers = load_providers(PROVIDERS_JSON)
    assert {"glm-5.3", "deepseek-v4.1-flash"} <= set(providers)
    for p in providers.values():
        blob = json.dumps(p.__dict__)
        assert "<VERIFY" not in blob, f"{p.alias}: fill in verified values (Task 6 step 6)"
        assert p.key_env and not p.key_env.startswith("sk-")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_providers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'simready.bench.prompting'`

- [ ] **Step 3: Write `simready/bench/prompting.py`**

```python
"""System prompt and tool schema shared by every benchmarked model.

The tool schema is the product's own ``build_part`` schema (single source of
truth), minus the agent-only sentence about calling analyze_geometry and the
timeout parameter. Their combined hash goes in every run header, so a prompt
change can never be mixed into an existing run.
"""

from __future__ import annotations

import copy
import hashlib
import json

from simready.copilot.tools import TOOL_SCHEMAS

_AGENT_ONLY_MARKER = "After calling this, ALWAYS call analyze_geometry"

SYSTEM_PROMPT = (
    "You design mechanical parts as solid models. Answer each request with exactly one "
    "build_part call whose spec builds the requested part; dimensions are in millimetres. "
    "Make sensible engineering choices for anything the request leaves open. If your "
    "client cannot call tools, reply with only the JSON object {\"steps\": [...]}. "
    "If the part cannot be built with these operations, say so instead of calling the tool."
)


def _bench_tool() -> dict:
    source = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == "build_part")
    tool = copy.deepcopy(source)
    description = tool["function"]["description"]
    if _AGENT_ONLY_MARKER not in description:
        raise RuntimeError("build_part description changed; update _AGENT_ONLY_MARKER in prompting.py")
    tool["function"]["description"] = description.split(_AGENT_ONLY_MARKER)[0].strip()
    tool["function"]["parameters"]["properties"].pop("timeout_seconds", None)
    return tool


BUILD_PART_TOOL = _bench_tool()


def build_messages(prompt: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]


def system_prompt_sha256() -> str:
    blob = json.dumps({"system": SYSTEM_PROMPT, "tool": BUILD_PART_TOOL}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Write `simready/bench/providers.py`**

```python
"""Provider config, API-key lookup and a retrying, rate-limited chat client.

Keys are looked up by env-var NAME (environment first, then repo .env) and
are never logged or printed. Retry policy: 429 and transient errors back off
exponentially; if every try was a 429 the daily quota is assumed spent
(QuotaExhausted -> the runner stops cleanly). Other 4xx are config bugs:
no retry, InfraError.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_JSON = Path(__file__).resolve().parent / "providers.json"


class InfraError(Exception):
    """API failure after retries; the attempt is excluded and retried on resume."""


class QuotaExhausted(Exception):
    """Every retry hit HTTP 429: stop the run, resume tomorrow."""


@dataclass
class Provider:
    alias: str
    base_url: str
    model: str
    key_env: str
    rpm: int
    max_tokens: int
    supports_seed: bool
    extra_body: dict = field(default_factory=dict)


def load_providers(path: str | Path = PROVIDERS_JSON) -> dict[str, Provider]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {alias: Provider(alias=alias, **cfg) for alias, cfg in raw.items()}


def resolve_key(
    provider: Provider,
    env: Mapping[str, str] = os.environ,
    dotenv_path: Path = REPO_ROOT / ".env",
) -> str:
    if env.get(provider.key_env):
        return env[provider.key_env]
    if dotenv_path.exists():
        from dotenv import dotenv_values

        value = dotenv_values(dotenv_path).get(provider.key_env)
        if value:
            return value
    raise KeyError(f"API key variable {provider.key_env} is not set (environment or .env)")


class RateLimiter:
    """Spaces call starts at least 60/rpm seconds apart, across threads."""

    def __init__(self, rpm: int, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], Any] = time.sleep):
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self._clock, self._sleep = clock, sleep
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            start = max(now, self._next)
            self._next = start + self.interval
        if start > now:
            self._sleep(start - now)


def _reply(resp: Any, latency_s: float) -> dict:
    choice = resp.choices[0]
    msg = choice.message
    usage = resp.usage
    return {
        "tool_calls": [
            {"name": tc.function.name, "arguments": tc.function.arguments} for tc in (msg.tool_calls or [])
        ],
        "content": msg.content,
        "finish_reason": choice.finish_reason,
        "model_returned": getattr(resp, "model", None),
        "usage": (
            {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}
            if usage is not None
            else None
        ),
        "latency_s": round(latency_s, 3),
    }


class ModelClient:
    def __init__(
        self,
        provider: Provider,
        client: Any = None,
        sleep: Callable[[float], Any] = time.sleep,
        max_retries: int = 6,
        initial_backoff: float = 2.0,
        max_backoff: float = 120.0,
    ):
        self.provider = provider
        if client is None:
            from openai import OpenAI

            # SDK retries off: our loop owns retry counting and quota detection.
            client = OpenAI(api_key=resolve_key(provider), base_url=provider.base_url, timeout=300, max_retries=0)
        self.client = client
        self.limiter = RateLimiter(provider.rpm, sleep=sleep)
        self._sleep = sleep
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff

    def complete(self, messages: list[dict], tools: list[dict], temperature: float, seed: int | None = None) -> dict:
        import openai

        kwargs: dict[str, Any] = {
            "model": self.provider.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.provider.max_tokens,
        }
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        if seed is not None and self.provider.supports_seed:
            kwargs["seed"] = seed
        if self.provider.extra_body:
            kwargs["extra_body"] = self.provider.extra_body

        backoff = self.initial_backoff
        rate_limited = 0
        last = ""
        for attempt in range(1, self.max_retries + 1):
            self.limiter.wait()
            started = time.monotonic()
            try:
                resp = self.client.chat.completions.create(**kwargs)
            except openai.RateLimitError as exc:
                rate_limited += 1
                last = f"HTTP 429: {exc}"
            except (openai.APIConnectionError, openai.InternalServerError) as exc:
                last = f"{type(exc).__name__}: {exc}"
            except openai.APIStatusError as exc:
                raise InfraError(f"HTTP {exc.status_code}: {exc}") from exc
            else:
                return _reply(resp, time.monotonic() - started)
            if attempt < self.max_retries:
                self._sleep(min(backoff, self.max_backoff))
                backoff *= 2
        if rate_limited == self.max_retries:
            raise QuotaExhausted(last)
        raise InfraError(last)
```

- [ ] **Step 5: Write `providers.json` with `<VERIFY>` markers, plus the smoke CLI**

`simready/bench/providers.json`. The `<VERIFY ...>` markers are deliberate: the values are only known after step 6, and `test_providers_json_is_complete` fails until they are filled in.

```json
{
  "glm-5.3": {
    "base_url": "<VERIFY: base URL of the provider that issued the GLM key>",
    "model": "<VERIFY: exact model id from models.list>",
    "key_env": "GLM_API_KEY",
    "rpm": 20,
    "max_tokens": 8192,
    "supports_seed": false,
    "extra_body": {}
  },
  "deepseek-v4.1-flash": {
    "base_url": "<VERIFY: base URL of the provider that issued the DeepSeek key>",
    "model": "<VERIFY: exact model id from models.list>",
    "key_env": "DEEPSEEK_API_KEY",
    "rpm": 20,
    "max_tokens": 8192,
    "supports_seed": false,
    "extra_body": {}
  }
}
```

`simready/bench/__main__.py`:

```python
"""CLI: python -m simready.bench {smoke,run,regrade,replay,report}.

Imports are lazy per subcommand so ``report`` runs in plain Python
(no OCC, no openai) on the committed logs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "data" / "bench_runs"

SMOKE_PROMPT = "A 40 x 30 x 5 mm plate with one 6 mm through hole in the centre."


def _smoke(args: argparse.Namespace) -> int:
    from simready.bench.attempt import classify_spec, parse_reply
    from simready.bench.prompting import BUILD_PART_TOOL, build_messages
    from simready.bench.providers import ModelClient, load_providers

    provider = load_providers()[args.model]
    client = ModelClient(provider, max_retries=2)
    try:
        ids = sorted(m.id for m in client.client.models.list())
        print(f"models.list: {len(ids)} ids; configured id present: {provider.model in ids}")
        if provider.model not in ids:
            print("  ids containing the alias stem:", [i for i in ids if args.model.split("-")[0] in i.lower()][:20])
    except Exception as exc:  # noqa: BLE001 — some providers don't serve models.list
        print(f"models.list unavailable: {type(exc).__name__}")
    reply = client.complete(build_messages(SMOKE_PROMPT), [BUILD_PART_TOOL], 0.7, seed=0)
    parsed = parse_reply(reply["tool_calls"], reply["content"])
    cls = classify_spec(parsed.spec)[0] if parsed.spec is not None else "F1_no_parse"
    print(json.dumps({
        "model_returned": reply["model_returned"],
        "finish_reason": reply["finish_reason"],
        "via": parsed.via,
        "n_tool_calls": parsed.n_tool_calls,
        "pre_build_class": cls,
        "usage": reply["usage"],
        "latency_s": reply["latency_s"],
    }, indent=2))
    return 0 if parsed.spec is not None else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m simready.bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke", help="one live call: model id, tool calling, parse")
    s.add_argument("--model", required=True)
    args = ap.parse_args(argv)
    handlers = {"smoke": _smoke}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Verify keys and model IDs live (needs the user)**

1. Ask the user which provider issued each key (GLM-5.3 and DeepSeek V4.1 Flash) and to add the keys to `.env` as `GLM_API_KEY` and `DEEPSEEK_API_KEY` themselves. As of 2026-10-04, `.env` holds only `OPENAI_API_KEY` (NIM), `OPENAI_BASE_URL`, `OPENAI_MODEL` and `KIMI_API_KEY`. If both models are served on NIM with the existing key, set `key_env` to `OPENAI_API_KEY` instead.
2. Check the keys load without printing them:
   `C:/mm/sr/python.exe -c "from dotenv import dotenv_values as d; v=d('.env'); print({k: len(v.get(k) or '') for k in ('GLM_API_KEY','DEEPSEEK_API_KEY')})"`
   Expected: both lengths > 0.
3. Fill in each `base_url` from the provider's own documentation (the user confirms it). Then run, for each alias:
   `C:/mm/sr/python.exe -m simready.bench smoke --model glm-5.3`
   The first run prints `configured id present: False` plus the candidate ids. Copy the exact id into `model` and re-run until it prints `True` (or `models.list unavailable` with a successful reply).
4. Record per provider: whether the reply came `via: tool` or `via: text`; `finish_reason`; whether a `seed` causes an HTTP 400 (try `"supports_seed": true` once; keep it only if accepted); and any thinking-mode parameter the provider documents. Leave thinking mode at the provider default and note the default in `bench_v1.md` setup.

Expected end state: both smokes exit 0 with `pre_build_class: null`.

- [ ] **Step 7: Run the tests**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_providers.py -v`
Expected: 9 passed, 1 deselected (`test_providers_json_is_complete` is `live_llm`).
After Task 6-live (step 6), also run `C:/mm/sr/python.exe -m pytest tests/test_bench_providers.py -m live_llm -v`; expected: 1 passed.

- [ ] **Step 8: Commit**

```bash
git add simready/bench/prompting.py simready/bench/providers.py simready/bench/providers.json simready/bench/__main__.py tests/test_bench_providers.py
git commit -m "feat(bench): provider client with quota-aware retries, smoke command, verified model ids"
```

---

### Task 7: Run log + runner + `run` command

**Files:**
- Create: `simready/bench/runlog.py`
- Create: `simready/bench/runner.py`
- Modify: `simready/bench/__main__.py` (add `run`)
- Create: `tests/test_bench_runner.py`

**Interfaces:**
- Consumes: `load_concepts`, `file_sha256`, `frozen_sha256`, `PHRASINGS`, `CHECKER_VERSION`; `parse_reply`, `evaluate_reply`, `grade_spec`, `INFRA`; `build_messages`, `BUILD_PART_TOOL`, `system_prompt_sha256`; `InfraError`, `QuotaExhausted`; the client object's `.complete(messages, tools, temperature, seed)`.
- Produces: `runlog.read_records(path)`, `runlog.read_header(path)`, `runlog.attempts(path) -> list[dict]` (latest record per `attempt_id`), `runlog.done_attempt_ids(path) -> set[str]`, `runlog.append(path, record)`, `runlog.EXCLUDED_CLASSES`. `runner.run_benchmark(*, client, model_alias, model_id, base_url, k, out_path, concepts_path=CONCEPTS_V1, limit=None, workers=4, official=False, grade=grade_spec, max_tokens=None) -> RunSummary(path, written, infra_errors, stopped_reason)`. Attempt record keys: `record="attempt", attempt_id, concept_id, name, in_vocab, phrasing, attempt_idx, prompt, model, prompt_sha256, checker_version, seed, ts, response, usage, latency_s`, plus every `evaluate_reply` key (or `error` for infra).

- [ ] **Step 1: Write the failing tests**

`tests/test_bench_runner.py`:

```python
"""Runner with a fake model client and fake grader: no network, no OCC."""

from __future__ import annotations

import json

import pytest

from simready.bench import runlog
from simready.bench.providers import InfraError, QuotaExhausted
from simready.bench.runner import run_benchmark

SPEC = {"steps": [{"op": "box", "dx": 40, "dy": 30, "dz": 5}]}


def _concept_line(cid):
    return json.dumps({
        "concept_id": cid, "name": cid, "in_vocab": True,
        "prompts": {"explicit": f"{cid} explicit prompt", "engineer": f"{cid} engineer prompt",
                    "intent": f"{cid} intent prompt"},
        "checks": {p: [{"type": "bbox_min_dim", "min": 1.0}] for p in ("explicit", "engineer", "intent")},
        "reference_spec": SPEC,
    })


@pytest.fixture
def concepts(tmp_path):
    p = tmp_path / "concepts.jsonl"
    p.write_text(_concept_line("c001") + "\n" + _concept_line("c002") + "\n", encoding="utf-8")
    return p


class FakeClient:
    def __init__(self, script=None):
        self.script = script or {}
        self.calls = []

    def complete(self, messages, tools, temperature, seed=None):
        prompt = messages[-1]["content"]
        self.calls.append((prompt, seed))
        action = self.script.get((prompt, seed))
        if isinstance(action, Exception):
            raise action
        return {"tool_calls": [{"name": "build_part", "arguments": json.dumps({"spec": SPEC})}],
                "content": None, "finish_reason": "tool_calls", "model_returned": "m",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "latency_s": 0.01}


def fake_grade(spec, checks, solids):
    report = {"checker_version": "t", "gate": {"passed": True}, "checks": [], "n_pass": 1, "n_fail": 0,
              "n_not_checked": 0, "partial": 1.0, "passed": True, "failure_class": None}
    return {"stage": "graded", "fingerprint": {"volume": 6000.0}, "report": report}


def _run(client, out, concepts, **kw):
    return run_benchmark(client=client, model_alias="fake", model_id="m", base_url="http://x",
                         k=2, out_path=out, concepts_path=concepts, workers=2, grade=fake_grade, **kw)


def test_full_run_writes_header_and_all_attempts(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    summary = _run(FakeClient(), out, concepts)
    assert summary.written == 12 and summary.stopped_reason is None  # 2 concepts x 3 phrasings x k=2
    header = runlog.read_header(out)
    assert header["k"] == 2 and header["model"] == "m" and len(header["prompt_sha256"]) == 64
    atts = runlog.attempts(out)
    assert {a["attempt_id"] for a in atts} >= {"c001/explicit/0", "c002/intent/1"}
    a = atts[0]
    assert a["passed"] is True and a["via"] == "tool" and a["prompt"].endswith("prompt")
    assert "api_key" not in json.dumps(a).lower()


def test_resume_skips_done_and_retries_infra(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    flaky = FakeClient({("c001 explicit prompt", 0): InfraError("HTTP 503")})
    first = _run(flaky, out, concepts)
    assert first.infra_errors == 1 and first.written == 11
    second_client = FakeClient()
    second = _run(second_client, out, concepts)
    assert second_client.calls == [("c001 explicit prompt", 0)] and second.written == 1
    assert {a["failure_class"] for a in runlog.attempts(out)} == {None}


def test_quota_exhausted_stops_cleanly(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    client = FakeClient({("c001 explicit prompt", 0): QuotaExhausted("429")})
    summary = _run(client, out, concepts, workers=1)
    assert summary.stopped_reason.startswith("quota")
    assert summary.written < 12


def test_limit_takes_first_items(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    assert _run(FakeClient(), out, concepts, limit=3).written == 3


def test_resume_refuses_changed_prompt_file(tmp_path, concepts):
    out = tmp_path / "run.jsonl"
    _run(FakeClient(), out, concepts, limit=1)
    concepts.write_text(_concept_line("c001") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="prompt_sha256"):
        _run(FakeClient(), out, concepts)


def test_official_requires_frozen_hash(tmp_path, concepts):
    with pytest.raises(RuntimeError, match="frozen"):
        _run(FakeClient(), tmp_path / "run.jsonl", concepts, official=True)


def test_runlog_reads_gzip(tmp_path, concepts):
    import gzip
    import shutil

    out = tmp_path / "run.jsonl"
    _run(FakeClient(), out, concepts, limit=2)
    gz = tmp_path / "run.jsonl.gz"
    with open(out, "rb") as src, gzip.open(gz, "wb") as dst:
        shutil.copyfileobj(src, dst)
    assert len(runlog.attempts(gz)) == 2
```

- [ ] **Step 2: Run them to verify they fail**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'simready.bench.runlog'`

- [ ] **Step 3: Write `simready/bench/runlog.py`**

```python
"""Read/append benchmark JSONL logs (.jsonl or .jsonl.gz). Stdlib only.

Line 1 is a ``record: header``; every other line is a ``record: attempt``.
Append-only: a resumed attempt that previously hit infra_error gets a new
line, and readers keep the latest line per attempt_id.
"""

from __future__ import annotations

import gzip
import json
import threading
from pathlib import Path
from typing import IO

EXCLUDED_CLASSES = frozenset({"infra_error", "checker_error"})
_WRITE_LOCK = threading.Lock()


def _open_text(path: str | Path, mode: str) -> IO[str]:
    if str(path).endswith(".gz"):
        return gzip.open(path, mode + "t", encoding="utf-8")
    return open(path, mode, encoding="utf-8")


def read_records(path: str | Path) -> list[dict]:
    with _open_text(path, "r") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def read_header(path: str | Path) -> dict:
    for rec in read_records(path):
        if rec.get("record") == "header":
            return rec
    raise ValueError(f"{path}: no header record")


def attempts(path: str | Path) -> list[dict]:
    latest: dict[str, dict] = {}
    for rec in read_records(path):
        if rec.get("record") == "attempt":
            latest[rec["attempt_id"]] = rec
    return list(latest.values())


def done_attempt_ids(path: str | Path) -> set[str]:
    return {a["attempt_id"] for a in attempts(path) if a.get("failure_class") not in EXCLUDED_CLASSES}


def append(path: str | Path, record: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _WRITE_LOCK, open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
```

- [ ] **Step 4: Write `simready/bench/runner.py`**

```python
"""Batch runner: concepts x phrasings x k attempts -> append-only JSONL log.

Resumable: (concept, phrasing, attempt_idx) already logged with a scored
outcome is skipped; infra/checker errors are retried. The header pins model,
prompt-file hash, checker version, system-prompt hash and k, and a resume
that disagrees with it is refused.
"""

from __future__ import annotations

import datetime as dt
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from simready.bench import CHECKER_VERSION, runlog
from simready.bench.attempt import INFRA, evaluate_reply, grade_spec, parse_reply
from simready.bench.concepts import CONCEPTS_V1, PHRASINGS, Concept, file_sha256, frozen_sha256, load_concepts
from simready.bench.providers import InfraError, QuotaExhausted

TEMPERATURE = 0.7
MAX_CONSECUTIVE_INFRA = 20
_PINNED = ("model", "prompt_sha256", "checker_version", "system_prompt_sha256", "k")


@dataclass
class WorkItem:
    concept: Concept
    phrasing: str
    idx: int

    @property
    def attempt_id(self) -> str:
        return f"{self.concept.concept_id}/{self.phrasing}/{self.idx}"


@dataclass
class RunSummary:
    path: Path
    written: int
    infra_errors: int
    stopped_reason: str | None


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def plan_items(concepts: list[Concept], k: int, done: set[str], limit: int | None = None) -> list[WorkItem]:
    items = [
        WorkItem(c, p, i)
        for c in concepts
        for p in PHRASINGS
        for i in range(k)
        if f"{c.concept_id}/{p}/{i}" not in done
    ]
    return items[:limit] if limit is not None else items


def run_benchmark(
    *,
    client: Any,
    model_alias: str,
    model_id: str,
    base_url: str,
    k: int,
    out_path: Path,
    concepts_path: Path = CONCEPTS_V1,
    limit: int | None = None,
    workers: int = 4,
    official: bool = False,
    grade: Callable[[dict, list, int], dict] = grade_spec,
    max_tokens: int | None = None,
) -> RunSummary:
    from simready.bench.prompting import BUILD_PART_TOOL, build_messages, system_prompt_sha256

    out_path = Path(out_path)
    prompt_sha = file_sha256(concepts_path)
    if official:
        if frozen_sha256() != prompt_sha:
            raise RuntimeError("official run needs the frozen prompt file (concepts_v1.sha256 must match)")
        if CHECKER_VERSION.endswith("-dev"):
            raise RuntimeError("official run needs a tagged CHECKER_VERSION (no -dev suffix)")

    header = {
        "record": "header",
        "run_id": out_path.name.removesuffix(".gz").removesuffix(".jsonl"),
        "model_alias": model_alias,
        "model": model_id,
        "base_url": base_url,
        "k": k,
        "temperature": TEMPERATURE,
        "max_tokens": max_tokens,
        "prompt_file": Path(concepts_path).name,
        "prompt_sha256": prompt_sha,
        "checker_version": CHECKER_VERSION,
        "system_prompt_sha256": system_prompt_sha256(),
        "official": official,
        "started": _now(),
    }
    if out_path.exists():
        existing = runlog.read_header(out_path)
        for key in _PINNED:
            if existing.get(key) != header[key]:
                raise RuntimeError(f"resume mismatch on {key}: log has {existing.get(key)!r}, now {header[key]!r}")
    else:
        runlog.append(out_path, header)

    items = plan_items(load_concepts(concepts_path), k, runlog.done_attempt_ids(out_path), limit)
    stop = threading.Event()
    lock = threading.Lock()
    state: dict[str, Any] = {"written": 0, "infra": 0, "consecutive_infra": 0, "stopped": None}

    def work(item: WorkItem) -> None:
        if stop.is_set():
            return
        prompt = getattr(item.concept.prompts, item.phrasing)
        base = {
            "record": "attempt",
            "attempt_id": item.attempt_id,
            "concept_id": item.concept.concept_id,
            "name": item.concept.name,
            "in_vocab": item.concept.in_vocab,
            "phrasing": item.phrasing,
            "attempt_idx": item.idx,
            "prompt": prompt,
            "model": model_id,
            "prompt_sha256": prompt_sha,
            "checker_version": CHECKER_VERSION,
            "seed": item.idx,
            "ts": _now(),
        }
        try:
            reply = client.complete(build_messages(prompt), [BUILD_PART_TOOL], TEMPERATURE, seed=item.idx)
        except QuotaExhausted as exc:
            stop.set()
            with lock:
                state["stopped"] = state["stopped"] or f"quota exhausted: {exc}"
            return
        except InfraError as exc:
            runlog.append(out_path, {**base, "failure_class": INFRA, "passed": False, "error": str(exc)})
            with lock:
                state["infra"] += 1
                state["consecutive_infra"] += 1
                if state["consecutive_infra"] >= MAX_CONSECUTIVE_INFRA:
                    stop.set()
                    state["stopped"] = state["stopped"] or f"{MAX_CONSECUTIVE_INFRA} consecutive infra errors"
            return
        with lock:
            state["consecutive_infra"] = 0
        parsed = parse_reply(reply["tool_calls"], reply["content"])
        outcome = evaluate_reply(parsed, getattr(item.concept.checks, item.phrasing), item.concept.solids, grade=grade)
        record = {
            **base,
            "response": {
                "content": reply["content"],
                "tool_calls": reply["tool_calls"],
                "finish_reason": reply["finish_reason"],
                "model_returned": reply["model_returned"],
            },
            "usage": reply["usage"],
            "latency_s": reply["latency_s"],
            **outcome,
        }
        runlog.append(out_path, record)
        with lock:
            state["written"] += 1

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, items))
    return RunSummary(out_path, state["written"], state["infra"], state["stopped"])
```

- [ ] **Step 5: Add `run` to the CLI**

In `simready/bench/__main__.py`, add this function above `main`:

```python
def _run(args: argparse.Namespace) -> int:
    from simready.bench.providers import ModelClient, load_providers
    from simready.bench.runner import run_benchmark

    provider = load_providers()[args.model]
    run_id = args.run_id or f"{args.model}-k{args.k}" + (f"-smoke{args.limit}" if args.limit else "")
    summary = run_benchmark(
        client=ModelClient(provider),
        model_alias=args.model,
        model_id=provider.model,
        base_url=provider.base_url,
        k=args.k,
        out_path=RUNS_DIR / f"{run_id}.jsonl",
        limit=args.limit,
        workers=args.workers,
        official=args.official,
        max_tokens=provider.max_tokens,
    )
    print(f"{summary.path}: wrote {summary.written}, infra errors {summary.infra_errors}, "
          f"stopped: {summary.stopped_reason or 'no'}")
    return 0 if summary.stopped_reason is None else 2
```

In `main`, add the parser and the handler:

```python
    r = sub.add_parser("run", help="run the benchmark for one model")
    r.add_argument("--model", required=True)
    r.add_argument("--k", type=int, default=5)
    r.add_argument("--limit", type=int)
    r.add_argument("--run-id")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--official", action="store_true")
```

and `handlers = {"smoke": _smoke, "run": _run}`.

- [ ] **Step 6: Run the tests**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_runner.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add simready/bench/runlog.py simready/bench/runner.py simready/bench/__main__.py tests/test_bench_runner.py
git commit -m "feat(bench): resumable threaded runner with pinned run header and quota stop"
```

---

### Task 8: `regrade` and `replay`

**Files:**
- Create: `simready/bench/replay.py`
- Modify: `simready/bench/__main__.py` (add `regrade`, `replay`)
- Create: `tests/test_bench_replay.py`

**Interfaces:**
- Consumes: `runlog`, `load_concepts`, `file_sha256`, `CHECKER_VERSION`, `ParsedReply`, `evaluate_reply`, `grade_spec`.
- Produces: `regrade(run_path, out_path, concepts_path=CONCEPTS_V1, grade=grade_spec) -> int` (attempts re-graded); `replay(run_path, attempt_id, concepts_path=CONCEPTS_V1, grade=grade_spec) -> tuple[bool, dict, dict]` (match, logged fingerprint, rebuilt fingerprint).

- [ ] **Step 1: Write the failing tests**

`tests/test_bench_replay.py`:

```python
"""regrade re-checks logged specs without API calls; replay verifies fingerprints."""

from __future__ import annotations

import json

import pytest

from simready.bench import runlog
from simready.bench.replay import regrade, replay

SPEC = {"steps": [{"op": "box", "dx": 40, "dy": 30, "dz": 5}]}


def _concepts(tmp_path, prompt="c001 explicit prompt"):
    p = tmp_path / "concepts.jsonl"
    p.write_text(json.dumps({
        "concept_id": "c001", "name": "plate", "in_vocab": True,
        "prompts": {"explicit": prompt, "engineer": "c001 engineer prompt", "intent": "c001 intent prompt"},
        "checks": {ph: [{"type": "bbox_min_dim", "min": 1.0}] for ph in ("explicit", "engineer", "intent")},
        "reference_spec": SPEC,
    }) + "\n", encoding="utf-8")
    return p


def _log(tmp_path, records):
    out = tmp_path / "run.jsonl"
    runlog.append(out, {"record": "header", "model": "m", "checker_version": "0.9", "prompt_sha256": "x"})
    for r in records:
        runlog.append(out, r)
    return out


def _attempt(idx, **over):
    base = {"record": "attempt", "attempt_id": f"c001/explicit/{idx}", "concept_id": "c001",
            "phrasing": "explicit", "attempt_idx": idx, "prompt": "c001 explicit prompt", "in_vocab": True,
            "spec": SPEC, "via": "tool", "n_tool_calls": 1, "passed": False,
            "failure_class": "F6_dimension_miss", "fingerprint": {"volume": 6000.0}}
    base.update(over)
    return base


def grade_pass(spec, checks, solids):
    report = {"partial": 1.0, "passed": True, "failure_class": None}
    return {"stage": "graded", "fingerprint": {"volume": 6000.0}, "report": report}


def test_regrade_updates_specs_and_carries_no_parse(tmp_path):
    run = _log(tmp_path, [_attempt(0), _attempt(1, spec=None, failure_class="F1_no_parse", fingerprint=None)])
    out = tmp_path / "regraded.jsonl"
    n = regrade(run, out, concepts_path=_concepts(tmp_path), grade=grade_pass)
    assert n == 1
    by_id = {a["attempt_id"]: a for a in runlog.attempts(out)}
    assert by_id["c001/explicit/0"]["passed"] is True
    assert by_id["c001/explicit/1"]["failure_class"] == "F1_no_parse"
    assert runlog.read_header(out)["regrade_of"].endswith("run.jsonl")


def test_regrade_refuses_changed_prompt_text(tmp_path):
    run = _log(tmp_path, [_attempt(0)])
    with pytest.raises(ValueError, match="prompt text changed"):
        regrade(run, tmp_path / "o.jsonl", concepts_path=_concepts(tmp_path, prompt="a different prompt"),
                grade=grade_pass)


def test_regrade_refuses_existing_output(tmp_path):
    run = _log(tmp_path, [_attempt(0)])
    with pytest.raises(FileExistsError):
        regrade(run, run, concepts_path=_concepts(tmp_path), grade=grade_pass)


def test_replay_match_and_mismatch(tmp_path):
    run = _log(tmp_path, [_attempt(0), _attempt(1, fingerprint={"volume": 1.0})])
    concepts = _concepts(tmp_path)
    assert replay(run, "c001/explicit/0", concepts_path=concepts, grade=grade_pass)[0] is True
    assert replay(run, "c001/explicit/1", concepts_path=concepts, grade=grade_pass)[0] is False


def test_replay_unbuilt_attempt_is_an_error(tmp_path):
    run = _log(tmp_path, [_attempt(0, spec=None, fingerprint=None, failure_class="F1_no_parse")])
    with pytest.raises(ValueError, match="never built"):
        replay(run, "c001/explicit/0", concepts_path=_concepts(tmp_path), grade=grade_pass)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_replay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'simready.bench.replay'`

- [ ] **Step 3: Write `simready/bench/replay.py`**

```python
"""regrade: re-run the current checker on logged specs (no API calls).
replay: rebuild one attempt and verify its geometric fingerprint.

Logged specs are never edited. regrade writes a new log whose header names
the source run and the new checker version; the report cites that version.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable

from simready.bench import CHECKER_VERSION, runlog
from simready.bench.attempt import ParsedReply, evaluate_reply, grade_spec
from simready.bench.concepts import CONCEPTS_V1, file_sha256, load_concepts


def regrade(
    run_path: str | Path,
    out_path: str | Path,
    concepts_path: str | Path = CONCEPTS_V1,
    grade: Callable[[dict, list, int], dict] = grade_spec,
) -> int:
    out_path = Path(out_path)
    if out_path.exists():
        raise FileExistsError(f"{out_path} exists; regrade never overwrites a log")
    concepts = {c.concept_id: c for c in load_concepts(concepts_path)}
    header = runlog.read_header(run_path)
    runlog.append(out_path, {
        **header,
        "checker_version": CHECKER_VERSION,
        "regrade_of": str(run_path),
        "regrade_prompt_sha256": file_sha256(concepts_path),
        "regraded": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    })
    regraded = 0
    for att in runlog.attempts(run_path):
        record = dict(att)
        if att.get("spec") is not None:
            concept = concepts[att["concept_id"]]
            if getattr(concept.prompts, att["phrasing"]) != att["prompt"]:
                raise ValueError(f"{att['attempt_id']}: prompt text changed since the run; regrade re-checks, never re-asks")
            parsed = ParsedReply(att["spec"], att.get("via"), att.get("n_tool_calls", 0))
            record.update(evaluate_reply(parsed, getattr(concept.checks, att["phrasing"]), concept.solids, grade=grade))
            record["checker_version"] = CHECKER_VERSION
            record["in_vocab"] = concept.in_vocab
            regraded += 1
        runlog.append(out_path, record)
    return regraded


def replay(
    run_path: str | Path,
    attempt_id: str,
    concepts_path: str | Path = CONCEPTS_V1,
    grade: Callable[[dict, list, int], dict] = grade_spec,
) -> tuple[bool, dict, dict | None]:
    by_id = {a["attempt_id"]: a for a in runlog.attempts(run_path)}
    if attempt_id not in by_id:
        raise KeyError(f"{attempt_id} not in {run_path}")
    att = by_id[attempt_id]
    if att.get("fingerprint") is None:
        raise ValueError(f"{attempt_id} never built a shape ({att.get('failure_class')}); nothing to replay")
    concept = {c.concept_id: c for c in load_concepts(concepts_path)}[att["concept_id"]]
    result = grade(att["spec"], getattr(concept.checks, att["phrasing"]), concept.solids)
    rebuilt = result.get("fingerprint")
    return rebuilt == att["fingerprint"], att["fingerprint"], rebuilt
```

- [ ] **Step 4: Add `regrade` and `replay` to the CLI**

In `simready/bench/__main__.py`, add these functions above `main`:

```python
def _regrade(args: argparse.Namespace) -> int:
    from simready.bench import CHECKER_VERSION
    from simready.bench.replay import regrade

    run = Path(args.run)
    stem = run.name.removesuffix(".gz").removesuffix(".jsonl")
    out = Path(args.out) if args.out else run.with_name(f"{stem}.regrade-{CHECKER_VERSION}.jsonl")
    n = regrade(run, out)
    print(f"{out}: re-graded {n} attempts with checker {CHECKER_VERSION}")
    return 0


def _replay(args: argparse.Namespace) -> int:
    from simready.bench.replay import replay

    match, logged, rebuilt = replay(Path(args.run), args.attempt_id)
    print(json.dumps({"match": match, "logged": logged, "rebuilt": rebuilt}, indent=2))
    return 0 if match else 1
```

In `main`:

```python
    g = sub.add_parser("regrade", help="re-check logged specs with the current checker")
    g.add_argument("run")
    g.add_argument("--out")
    p = sub.add_parser("replay", help="rebuild one attempt and verify its fingerprint")
    p.add_argument("run")
    p.add_argument("attempt_id")
```

and `handlers = {"smoke": _smoke, "run": _run, "regrade": _regrade, "replay": _replay}`.

- [ ] **Step 5: Run the tests**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_replay.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add simready/bench/replay.py simready/bench/__main__.py tests/test_bench_replay.py
git commit -m "feat(bench): regrade and replay - re-check logs, verify fingerprints"
```

---

### Task 9: Report (stdlib only) + `report` command

**Files:**
- Create: `simready/bench/report.py`
- Modify: `simready/bench/__main__.py` (add `report`)
- Create: `tests/test_bench_report.py`

**Interfaces:**
- Consumes: `runlog`, `PHRASINGS` (`concepts` imports only pydantic; no OCC, no openai).
- Produces: `load_run(path) -> ModelRun(header, attempts, excluded)`; `headline(run) -> dict(p1, p1_ci, pk, pk_ci, n_concepts, n_prompts)`; `by_phrasing(run) -> dict(p1: {phrasing: float}, gap, gap_ci)`; `failure_distribution(run) -> dict[phrasing, Counter]`; `out_of_vocab(run) -> Counter`; `cost(run) -> dict`; `incomplete_prompts(run) -> int`; `render_markdown(runs: list[ModelRun]) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_bench_report.py`:

```python
"""Report metrics on a synthetic log with hand-computed expected values."""

from __future__ import annotations

import pytest

from simready.bench import runlog
from simready.bench.report import (
    by_phrasing,
    failure_distribution,
    headline,
    incomplete_prompts,
    load_run,
    out_of_vocab,
    render_markdown,
)

# k=2. In-vocab c001: explicit TT, engineer TF, intent FF. c002: explicit TF, engineer FF, intent FF.
OUTCOMES = {
    ("c001", "explicit"): [True, True], ("c001", "engineer"): [True, False], ("c001", "intent"): [False, False],
    ("c002", "explicit"): [True, False], ("c002", "engineer"): [False, False], ("c002", "intent"): [False, False],
}


def _write(tmp_path):
    out = tmp_path / "run.jsonl"
    runlog.append(out, {"record": "header", "model": "m", "model_alias": "fake", "k": 2, "base_url": "http://x",
                        "temperature": 0.7, "prompt_sha256": "a" * 64, "checker_version": "1.0.0",
                        "official": True, "started": "2026-10-10T00:00:00+00:00"})
    for (cid, ph), results in OUTCOMES.items():
        for i, ok in enumerate(results):
            runlog.append(out, {"record": "attempt", "attempt_id": f"{cid}/{ph}/{i}", "concept_id": cid,
                                "phrasing": ph, "in_vocab": True, "passed": ok,
                                "failure_class": None if ok else "F6_dimension_miss",
                                "usage": {"prompt_tokens": 100, "completion_tokens": 50}, "latency_s": 2.0,
                                "check_report": {"n_not_checked": 1}, "ts": "2026-10-10T01:00:00+00:00"})
    for i, cls in enumerate(["F9_out_of_vocab", "F1_no_parse"]):  # out-of-vocab concept: excluded from headline
        runlog.append(out, {"record": "attempt", "attempt_id": f"c003/explicit/{i}", "concept_id": "c003",
                            "phrasing": "explicit", "in_vocab": False, "passed": False, "failure_class": cls,
                            "spec": None, "usage": None, "latency_s": 1.0})
    runlog.append(out, {"record": "attempt", "attempt_id": "c003/engineer/0", "concept_id": "c003",
                        "phrasing": "engineer", "in_vocab": False, "passed": False, "failure_class": "infra_error"})
    return out


def test_headline_pass_at_1_and_k(tmp_path):
    h = headline(load_run(_write(tmp_path)))
    assert h["p1"] == pytest.approx(2 / 6)  # mean of per-prompt p1: (1 + .5 + 0 + .5 + 0 + 0) / 6
    assert h["pk"] == pytest.approx(3 / 6)  # prompts with at least one pass
    assert h["n_concepts"] == 2 and h["n_prompts"] == 6
    assert h["p1_ci"][0] <= h["p1"] <= h["p1_ci"][1]


def test_by_phrasing_and_reasoning_gap(tmp_path):
    b = by_phrasing(load_run(_write(tmp_path)))
    assert b["p1"]["explicit"] == pytest.approx(0.75)
    assert b["p1"]["engineer"] == pytest.approx(0.25)
    assert b["gap"] == pytest.approx(0.5)


def test_failure_distribution_and_out_of_vocab(tmp_path):
    run = load_run(_write(tmp_path))
    assert failure_distribution(run)["engineer"]["F6_dimension_miss"] == 3
    oov = out_of_vocab(run)
    assert oov["used_missing_op (F9)"] == 1 and oov["declined / no spec (F1)"] == 1
    assert run.excluded == 1  # the infra_error line


def test_incomplete_prompts_counts_short_prompts(tmp_path):
    run = load_run(_write(tmp_path))
    assert incomplete_prompts(run) == 1  # c003/explicit has 2 of k=2; c003/engineer has 0 scored of 2


def test_render_markdown_has_all_generated_tables(tmp_path):
    md = render_markdown([load_run(_write(tmp_path))])
    for heading in ("## 1. Setup", "## 2. Headline", "## 3. By phrasing", "## 4. Failure classes",
                    "## 5. Out-of-vocab concepts", "## 6. Cost", "## 8. Known limits (generated counts)"):
        assert heading in md
    assert "not comparable" in md
```

- [ ] **Step 2: Run them to verify they fail**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'simready.bench.report'`

- [ ] **Step 3: Write `simready/bench/report.py`**

```python
"""bench_v1.md tables from run logs. Stdlib (+ pydantic via concepts) only:
no OCC, no network — the README's quick reproduce path.

pass@1 = mean success over a prompt's attempts; pass@k = share of prompts
with at least one pass (n = k, so exact). Headline numbers are over in-vocab
concepts only. 95% CIs bootstrap over CONCEPTS (a concept's 3 x k attempts
are not independent). Mechanical-reasoning gap = pass@1(explicit) -
pass@1(engineer), paired per concept.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from simready.bench import runlog
from simready.bench.concepts import PHRASINGS

N_BOOT = 2000
BOOT_SEED = 20261004
FAILURE_CLASSES = [
    "F1_no_parse", "F2_schema", "F3_reference", "F4_build_error", "F5_invalid_solid",
    "F6_dimension_miss", "F7_feature_miss", "F8_timeout", "F9_out_of_vocab",
]


@dataclass
class ModelRun:
    header: dict
    attempts: list[dict]  # scored attempts only
    excluded: int  # infra_error + checker_error
    excluded_attempts: list[dict] | None = None


def load_run(path: str | Path) -> ModelRun:
    all_attempts = runlog.attempts(path)
    scored = [a for a in all_attempts if a.get("failure_class") not in runlog.EXCLUDED_CLASSES]
    excluded = [a for a in all_attempts if a.get("failure_class") in runlog.EXCLUDED_CLASSES]
    return ModelRun(runlog.read_header(path), scored, len(excluded), excluded)


def _prompts(run: ModelRun, in_vocab: bool = True) -> dict[tuple[str, str], list[bool]]:
    table: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for a in run.attempts:
        if a["in_vocab"] == in_vocab:
            table[(a["concept_id"], a["phrasing"])].append(bool(a["passed"]))
    return table


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _bootstrap(values_by_concept: dict[str, list[float]]) -> tuple[float, float]:
    keys = sorted(values_by_concept)
    if not keys:
        return (float("nan"), float("nan"))
    rng = random.Random(BOOT_SEED)
    stats = []
    for _ in range(N_BOOT):
        sample = [v for k in (rng.choice(keys) for _ in keys) for v in values_by_concept[k]]
        stats.append(_mean(sample))
    stats.sort()
    return stats[int(0.025 * N_BOOT)], stats[int(0.975 * N_BOOT) - 1]


def headline(run: ModelRun) -> dict:
    prompts = _prompts(run)
    p1_by: dict[str, list[float]] = defaultdict(list)
    pk_by: dict[str, list[float]] = defaultdict(list)
    for (cid, _), results in prompts.items():
        p1_by[cid].append(_mean([float(r) for r in results]))
        pk_by[cid].append(1.0 if any(results) else 0.0)
    return {
        "p1": _mean([v for vs in p1_by.values() for v in vs]),
        "p1_ci": _bootstrap(p1_by),
        "pk": _mean([v for vs in pk_by.values() for v in vs]),
        "pk_ci": _bootstrap(pk_by),
        "n_concepts": len(p1_by),
        "n_prompts": len(prompts),
    }


def by_phrasing(run: ModelRun) -> dict:
    prompts = _prompts(run)
    p1: dict[str, dict[str, float]] = defaultdict(dict)
    for (cid, ph), results in prompts.items():
        p1[ph][cid] = _mean([float(r) for r in results])
    paired = {cid: [p1["explicit"][cid] - p1["engineer"][cid]]
              for cid in p1.get("explicit", {}) if cid in p1.get("engineer", {})}
    return {
        "p1": {ph: _mean(list(p1[ph].values())) for ph in PHRASINGS if p1.get(ph)},
        "gap": _mean([d[0] for d in paired.values()]),
        "gap_ci": _bootstrap(paired),
    }


def failure_distribution(run: ModelRun) -> dict[str, Counter]:
    dist: dict[str, Counter] = {ph: Counter() for ph in PHRASINGS}
    for a in run.attempts:
        if a["in_vocab"] and a.get("failure_class"):
            dist[a["phrasing"]][a["failure_class"]] += 1
    return dist


def out_of_vocab(run: ModelRun) -> Counter:
    out: Counter = Counter()
    for a in run.attempts:
        if a["in_vocab"]:
            continue
        cls = a.get("failure_class")
        if cls == "F9_out_of_vocab":
            out["used_missing_op (F9)"] += 1
        elif cls == "F1_no_parse":
            out["declined / no spec (F1)"] += 1
        elif a.get("passed"):
            out["faked: built and passed checks"] += 1
        else:
            out["faked: built or tried, failed"] += 1
    return out


def cost(run: ModelRun) -> dict:
    usage = [a["usage"] for a in run.attempts if a.get("usage")]
    lat = [a["latency_s"] for a in run.attempts if a.get("latency_s") is not None]
    return {
        "calls": len(run.attempts) + run.excluded,
        "prompt_tokens": sum(u.get("prompt_tokens") or 0 for u in usage),
        "completion_tokens": sum(u.get("completion_tokens") or 0 for u in usage),
        "median_latency_s": statistics.median(lat) if lat else float("nan"),
    }


def incomplete_prompts(run: ModelRun) -> int:
    """Prompts with fewer than k scored attempts (pass@k is then not exact)."""
    k = run.header["k"]
    counts: Counter = Counter((a["concept_id"], a["phrasing"]) for a in run.attempts)
    keys = set(counts) | {(a["concept_id"], a["phrasing"]) for a in (run.excluded_attempts or [])}
    return sum(1 for key in keys if counts[key] < k)


def _pct(x: float) -> str:
    return "n/a" if x != x else f"{100 * x:.1f}%"


def _ci(ci: tuple[float, float]) -> str:
    return f"[{_pct(ci[0])}, {_pct(ci[1])}]"


def render_markdown(runs: list[ModelRun]) -> str:
    lines: list[str] = []
    add = lines.append
    add("## 1. Setup\n")
    add("| model | id | base URL | k | temp | prompt sha256 | checker | official | started | incomplete prompts |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for r in runs:
        h = r.header
        add(f"| {h.get('model_alias')} | `{h.get('model')}` | {h.get('base_url')} | {h.get('k')} | "
            f"{h.get('temperature')} | `{h.get('prompt_sha256', '')[:12]}` | {h.get('checker_version')} | "
            f"{h.get('official')} | {h.get('started')} | {incomplete_prompts(r)} |")
    add("\nNumbers here are **not comparable** to `docs/validation/geometry_gen_eval.md` "
        "(different models, prompts and metric).\n")
    add("## 2. Headline (in-vocab prompts, 95% CI bootstrapped over concepts)\n")
    add("| model | pass@1 | 95% CI | pass@k | 95% CI | concepts | prompts |")
    add("|---|---|---|---|---|---|---|")
    for r in runs:
        h = headline(r)
        add(f"| {r.header.get('model_alias')} | {_pct(h['p1'])} | {_ci(h['p1_ci'])} | {_pct(h['pk'])} | "
            f"{_ci(h['pk_ci'])} | {h['n_concepts']} | {h['n_prompts']} |")
    add("\n## 3. By phrasing (pass@1) and mechanical-reasoning gap\n")
    add("| model | explicit | engineer | intent | gap (explicit - engineer) | paired 95% CI |")
    add("|---|---|---|---|---|---|")
    for r in runs:
        b = by_phrasing(r)
        p = b["p1"]
        add(f"| {r.header.get('model_alias')} | {_pct(p.get('explicit', float('nan')))} | "
            f"{_pct(p.get('engineer', float('nan')))} | {_pct(p.get('intent', float('nan')))} | "
            f"{_pct(b['gap'])} | {_ci(b['gap_ci'])} |")
    add("\n## 4. Failure classes (in-vocab, failed attempts)\n")
    add("| model | phrasing | " + " | ".join(FAILURE_CLASSES) + " |")
    add("|---|---|" + "---|" * len(FAILURE_CLASSES))
    for r in runs:
        for ph, counter in failure_distribution(r).items():
            add(f"| {r.header.get('model_alias')} | {ph} | " + " | ".join(str(counter[c]) for c in FAILURE_CLASSES) + " |")
    add("\n## 5. Out-of-vocab concepts (reported separately, never in the headline)\n")
    add("| model | outcome | attempts |")
    add("|---|---|---|")
    for r in runs:
        for outcome, n in sorted(out_of_vocab(r).items()):
            add(f"| {r.header.get('model_alias')} | {outcome} | {n} |")
    add("\n## 6. Cost\n")
    add("| model | calls | prompt tokens | completion tokens | median latency (s) | excluded (infra/checker) |")
    add("|---|---|---|---|---|---|")
    for r in runs:
        c = cost(r)
        add(f"| {r.header.get('model_alias')} | {c['calls']} | {c['prompt_tokens']} | {c['completion_tokens']} | "
            f"{c['median_latency_s']:.2f} | {r.excluded} |")
    add("\n## 8. Known limits (generated counts)\n")
    for r in runs:
        nc = sum((a.get("check_report") or {}).get("n_not_checked", 0) for a in r.attempts)
        add(f"- {r.header.get('model_alias')}: {nc} `not_checked` results across scored attempts.")
    add("")
    return "\n".join(lines)
```

- [ ] **Step 4: Add `report` to the CLI**

In `simready/bench/__main__.py`, add this function above `main`:

```python
def _report(args: argparse.Namespace) -> int:
    from simready.bench.report import load_run, render_markdown

    md = render_markdown([load_run(p) for p in args.runs])
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(md)
    return 0
```

In `main`:

```python
    rp = sub.add_parser("report", help="bench_v1.md tables from run logs (no OCC needed)")
    rp.add_argument("runs", nargs="+")
    rp.add_argument("--out")
```

and `handlers = {"smoke": _smoke, "run": _run, "regrade": _regrade, "replay": _replay, "report": _report}`.

- [ ] **Step 5: Run the tests, including an OCC-free import check**

Run: `C:/mm/sr/python.exe -m pytest tests/test_bench_report.py -v`
Expected: 5 passed

Run (base Python, no OCC): `python -c "import simready.bench.report, sys; print('OCC' in ' '.join(sys.modules))"`
Expected: `False`

- [ ] **Step 6: Commit**

```bash
git add simready/bench/report.py simready/bench/__main__.py tests/test_bench_report.py
git commit -m "feat(bench): report - pass@k, concept bootstrap CIs, reasoning gap, failure tables"
```

---

### Task 10: Smoke runs on both models, fix what they expose

**Files:**
- Possibly modify: `simready/bench/prompts/concepts_v1.jsonl`, `simready/bench/checker.py`, `simready/bench/attempt.py`, `simready/bench/providers.json` (whatever the smoke shows)

- [ ] **Step 1: Full test suite green first**

Run: `C:/mm/sr/python.exe -m pytest -q`
Expected: the previous suite (227) plus all `test_bench_*` pass, 0 failures.

- [ ] **Step 2: Smoke-run 2 concepts × 3 phrasings × k=2 per model**

```bash
C:/mm/sr/python.exe -m simready.bench run --model glm-5.3 --k 2 --limit 12 --run-id smoke-glm
C:/mm/sr/python.exe -m simready.bench run --model deepseek-v4.1-flash --k 2 --limit 12 --run-id smoke-ds
C:/mm/sr/python.exe -m simready.bench report data/bench_runs/smoke-glm.jsonl data/bench_runs/smoke-ds.jsonl
```

Expected: both runs print `stopped: no` and the report renders. `--limit 12` covers c001 and c002, all three phrasings, 2 attempts each.

- [ ] **Step 3: Read every smoke attempt, not just the totals**

For each of the 24 attempts, check: `via`; the parsed spec; the class; and, for F6/F7, the check `detail` lines. Typical findings to fix here: a range that's too tight for a reasonable answer (fix the concept), a reply shape the parser misses (add a parser test first, then fix), `finish_reason: length` (raise `max_tokens`), `checker_error` (fix the checker with a regression test first). Every change gets a test or a concept-file fix, plus a commit.

- [ ] **Step 4: Replay one attempt per model**

```bash
C:/mm/sr/python.exe -m simready.bench replay data/bench_runs/smoke-glm.jsonl c001/explicit/0
```

Expected: `"match": true`, exit 0. Use any attempt that has a fingerprint.

- [ ] **Step 5: Commit the fixes**

```bash
git add -A simready/bench tests
git commit -m "fix(bench): issues found by live smoke runs"
```

Each fix goes in its own commit with a specific message if they're unrelated.

---

### Task 11: Freeze, tag the checker, official runs, publish logs

**Gate:** the user has finished proofreading `concepts_v1.jsonl` (Task 2), and all reference-spec tests pass.

**Files:**
- Create: `simready/bench/prompts/concepts_v1.sha256`
- Modify: `simready/bench/__init__.py` (`CHECKER_VERSION = "1.0.0"`)
- Create: `docs/validation/bench_v1/runs-glm-5.3.jsonl.gz`, `docs/validation/bench_v1/runs-deepseek-v4.1-flash.jsonl.gz`

- [ ] **Step 1: Freeze the prompt file and tag the checker**

```bash
C:/mm/sr/python.exe -c "from simready.bench.concepts import CONCEPTS_V1, CONCEPTS_V1_FROZEN, file_sha256; CONCEPTS_V1_FROZEN.write_text(file_sha256(CONCEPTS_V1) + '\n', encoding='utf-8'); print(CONCEPTS_V1_FROZEN.read_text())"
```

Set `CHECKER_VERSION = "1.0.0"` in `simready/bench/__init__.py`. Run `C:/mm/sr/python.exe -m pytest -q` (expect green).

```bash
git add simready/bench/prompts/concepts_v1.sha256 simready/bench/__init__.py
git commit -m "chore(bench): freeze concepts_v1 and tag checker 1.0.0 for the official run"
git tag bench-checker-1.0.0
```

- [ ] **Step 2: Official runs (resumable; may span more than one day per model)**

```bash
C:/mm/sr/python.exe -m simready.bench run --model glm-5.3 --k 5 --official --run-id official-glm-5.3
C:/mm/sr/python.exe -m simready.bench run --model deepseek-v4.1-flash --k 5 --official --run-id official-deepseek-v4.1-flash
```

Expected: each ends with `stopped: no` after 750 written attempts. If it stops with `quota exhausted`, re-run the same command the next day (resume skips finished attempts). After that, re-run once more to retry any `infra_error`, until the report's `incomplete prompts` column is 0.

- [ ] **Step 3: Publish the logs gzipped**

```bash
C:/mm/sr/python.exe -c "import gzip, shutil, pathlib; d = pathlib.Path('docs/validation/bench_v1'); d.mkdir(parents=True, exist_ok=True); [shutil.copyfileobj(open(f'data/bench_runs/official-{m}.jsonl', 'rb'), gzip.open(d / f'runs-{m}.jsonl.gz', 'wb')) for m in ('glm-5.3', 'deepseek-v4.1-flash')]"
ls -la docs/validation/bench_v1/
```

Expected: two `.jsonl.gz` files of about 1–2 MB each. Check that no key leaked:

```bash
C:/mm/sr/python.exe -c "import gzip, re, pathlib; hits = [p.name for p in pathlib.Path('docs/validation/bench_v1').glob('*.gz') if re.search(r'(sk-|nvapi-|Bearer )', gzip.open(p, 'rt', encoding='utf-8').read())]; print('key-like strings in:', hits)"
```

Expected: `key-like strings in: []`. Also scan for the actual key values, per Rule 3:

```bash
C:/mm/sr/python.exe -c "import gzip, pathlib; from dotenv import dotenv_values; vals = [v for k, v in dotenv_values('.env').items() if 'KEY' in k and v]; blob = ''.join(gzip.open(p, 'rt', encoding='utf-8').read() for p in pathlib.Path('docs/validation/bench_v1').glob('*.gz')); print('key values found:', sum(v in blob for v in vals))"
```

Expected: `key values found: 0`

- [ ] **Step 4: Commit**

```bash
git add docs/validation/bench_v1/
git commit -m "data(bench): official v1 run logs for GLM-5.3 and DeepSeek V4.1 Flash"
```

---

### Task 12: `bench_v1.md`, README section, clean-clone verification

**Files:**
- Create: `docs/validation/bench_v1.md`
- Modify: `README.md` (add "Reproduce the benchmark")

- [ ] **Step 1: Generate the tables**

```bash
C:/mm/sr/python.exe -m simready.bench report docs/validation/bench_v1/runs-glm-5.3.jsonl.gz docs/validation/bench_v1/runs-deepseek-v4.1-flash.jsonl.gz --out data/bench_runs/tables.md
```

- [ ] **Step 2: Write `docs/validation/bench_v1.md` around the generated tables**

Structure:

1. Title, one-paragraph summary of what was measured, and the date.
2. The generated tables 1–6, pasted verbatim from `data/bench_runs/tables.md`.
3. Table 7, hand-written: three annotated failures, picked from the **most frequent** failure classes in table 4. For each, give the attempt id, the prompt, the spec, what the checker reported, and a render. Make the render with the existing PNG renderer after rebuilding the spec. Find the call in `simready/copilot/png_render.py`; save images to `docs/validation/bench_v1/fail-<n>.png`.
4. The generated table 8 counts, plus these fixed limits: no wall-thickness check (v1.1); tolerances are author-chosen; one author and one proofreader; thinking-mode defaults per provider (from Task 6 step 6); the two deviations that affect reading the numbers (refusal allowed in the system prompt; `checker_error` excluded).
5. Honesty line: the report is published as-is; no model was dropped after seeing results; SP3's metric is single-shot pass@1 on held-out prompts (D6).

No number in the text may differ from the generated tables. Copy, never retype.

- [ ] **Step 3: Add the README section**

Add to `README.md`, after the existing validation/results section:

````markdown
## Reproduce the benchmark

Every published number in [`docs/validation/bench_v1.md`](docs/validation/bench_v1.md) can be
rebuilt from the committed run logs in `docs/validation/bench_v1/`. No API keys are needed.

**Quick path (plain Python, no CAD kernel, about a minute):**

```bash
pip install pydantic
python -m simready.bench report docs/validation/bench_v1/runs-glm-5.3.jsonl.gz docs/validation/bench_v1/runs-deepseek-v4.1-flash.jsonl.gz
```

**Full path (re-grade every logged spec with the checker, rebuild any attempt):**

```bash
micromamba env create -f environment.yml   # ~10-15 min, installs pythonocc
micromamba activate simready
python -m simready.bench regrade docs/validation/bench_v1/runs-glm-5.3.jsonl.gz --out regraded-glm.jsonl
python -m simready.bench replay docs/validation/bench_v1/runs-glm-5.3.jsonl.gz <attempt_id>
```

**Run it yourself (needs your own API key):**

```bash
python -m simready.bench run --model glm-5.3 --k 5
```
````

The env name `simready` matches `environment.yml` (`name: simready`, checked 2026-10-04). In the replay line, replace `<attempt_id>` with a real attempt id from the committed logs that has a fingerprint (Rule 4: no unverified examples).

- [ ] **Step 4: Verify both paths on a clean clone**

The README example must run on a fresh clone (spec done-criterion 5). Run it from the scratchpad, after the user has pushed:

```bash
SP="C:/Users/suman/AppData/Local/Temp/claude/C--Users-suman-Desktop-Docs-Job-Projects-Mech-SimReady/3fb58c4d-463b-4adf-a155-8cb9cb78dc5d/scratchpad"
git clone --depth 1 https://github.com/Sumanthreddy-DE/simready "$SP/clean"
cd "$SP/clean"
python -m simready.bench report docs/validation/bench_v1/runs-glm-5.3.jsonl.gz docs/validation/bench_v1/runs-deepseek-v4.1-flash.jsonl.gz > quick.md
C:/mm/sr/python.exe -m simready.bench regrade docs/validation/bench_v1/runs-glm-5.3.jsonl.gz --out "$SP/regraded-glm.jsonl"
C:/mm/sr/python.exe -m simready.bench report "$SP/regraded-glm.jsonl" > "$SP/regraded.md"
```

Expected: the tables in `quick.md` equal those in `bench_v1.md` (diff them). The regraded GLM headline equals the published GLM headline. `replay` on the README's attempt id prints `"match": true`. The quick path used base Python (no OCC).

- [ ] **Step 5: Commit**

```bash
git add docs/validation/bench_v1.md docs/validation/bench_v1/*.png README.md
git commit -m "docs(bench): bench_v1 report and README reproduce section, verified on a clean clone"
```

---

### Task 13: Close SP1

**Files:**
- Modify: `docs/exec-plans/active/2026-09-25-sp1-cad-benchmark-design.md` → `Status: done`, move to `docs/exec-plans/completed/`
- Modify: this plan → `Status: done`, move to `docs/exec-plans/completed/`
- Modify: `BACKLOG.md`, `STATE.md`

- [ ] **Step 1: Check the spec's five done criteria, one by one, against evidence**

1. Frozen hash file exists and the user signed off on proofreading → commit SHA from Task 11.
2. `C:/mm/sr/python.exe -m pytest tests/test_bench_checker.py -v` → every check type has a pass and a fail case.
3. Both official logs are complete (`incomplete prompts` = 0 in table 1).
4. `bench_v1.md` has tables 1–8; logs are committed.
5. Clean-clone outputs match (Task 12 step 4).

- [ ] **Step 2: Update BACKLOG and STATE**

BACKLOG: add `S2 sp3-entry-gate`: run the small-model baseline (first: check newer ~3–4B instruct models with Unsloth GRPO + GGUF support, spec D5 "Open"), then start SP3. Add `S3 bench-v1.1`: 100 concepts + wall-thickness check, before SP3. Move the SP1 item to Done with the closing commit SHAs.
STATE: one-line update under Done; Resume-here → SP3 entry gate. Update the CV line too: the `[SP1]` sentence in the pitch bank is now true.

- [ ] **Step 3: Move both plan files and commit**

```bash
git mv docs/exec-plans/active/2026-09-25-sp1-cad-benchmark-design.md docs/exec-plans/completed/
git mv docs/exec-plans/active/2026-10-04-sp1-bench-implementation.md docs/exec-plans/completed/
git add BACKLOG.md STATE.md docs/exec-plans/completed/
git commit -m "chore(plans): SP1 done - benchmark v1 published"
```

---

## Self-review (done while writing, 2026-10-04)

**Spec coverage:**
- Done 1 (50 × 3, proofread, frozen, reference specs) → Tasks 2, 4, 11.
- Done 2 (unit tests per check type) → Task 4.
- Done 3 (official runs, both API models) → Task 11.
- Done 4 (all §3 tables, logs committed) → Tasks 9, 11, 12.
- Done 5 (clean-clone README) → Task 12.
- D5 model-ID verification → Task 6 step 6. D5 Qwen moved to the SP3 gate → Task 13 BACKLOG. D6 single-shot → runner sends one request per attempt. D7 layout → file map.
- §1 rules 1–7 → Tasks 3–4. §2 runner/log/resume/replay/official → Tasks 7–8, 11. §3 classes, metrics, tables → Tasks 5, 9, 12.

**Placeholders:** the `<VERIFY>` values in `providers.json` are deliberate and test-enforced: they can only be filled from the user's live providers (Rule 4 forbids plausible-looking guesses). The README `<attempt_id>` is replaced in Task 12 step 3 with a real id. The 50 concept lines are Task 2's deliverable, with format, rules, themes and two verified examples given.

**Type consistency:** `grade(spec, checks, solids)` has the same signature in `attempt.grade_spec`, the runner, replay and all fakes. Failure-class strings are defined once in `attempt.py`/`checker.py` and repeated literally in report `FAILURE_CLASSES` and the tests. Record keys (`attempt_id`, `concept_id`, `phrasing`, `in_vocab`, `passed`, `failure_class`, `fingerprint`, `spec`, `via`, `n_tool_calls`, `usage`, `latency_s`, `check_report`) match across runner, replay, report and tests.

**Defects fixed in review:** `incomplete_prompts` first read a header key nothing writes (now uses `ModelRun.excluded_attempts`); run ids with dots (`deepseek-v4.1-flash`) were truncated by `split(".")` (now `removesuffix`); test counts corrected (attempt 9, providers 10).
