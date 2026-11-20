# SP2 — Generation vocabulary v2: design

**Status:** active
**Last verified:** 2026-11-20
**Backlog:** S2 `sp2-vocab-v2` (absorbs `sp1-repair-mode`); feeds S2 `sp3-entry-gate`
**Plan:** `docs/exec-plans/active/2026-11-20-sp2-vocab-v2-plan.md`
**Builds on:** `docs/exec-plans/completed/2026-09-25-sp1-cad-benchmark-design.md` (D1, D6, rule 6),
`docs/validation/bench_v1.md`, ADR 0001

## Context

SP1 (`bench_v1`) measured the 4-op DSL (`box`, `cyl`, `fuse`, `cut`, at most 16 steps) on 50
concepts × 3 phrasings with the OCCT range checker (`CHECKER_VERSION = 1.0.0`). The reference pair
reached 96.2% / 95.5% pass@1 on the 37 in-vocab concepts; the 13 out-of-vocab concepts were mostly
declined (179/195 and 184/195 attempts). Their `cd5d693` logs regrade with 0 differences under the
tagged checker `1e70789` (2026-11-20).

SP2 answers three questions, each with a number fixed before any run:

1. **Vocabulary:** does a larger DSL let models build the parts v1 could not, without losing what
   v1 already did?
2. **DSL vs code:** on the same prompts, does the typed DSL beat free-form build123d code, per
   model, including a small open model?
3. **Repair:** how much does feeding the model its own measured geometry back (up to 2 retries)
   add on top of single-shot?

## Decisions (approved by the user 2026-11-20, in brainstorming)

### E1. Held-out concept set `concepts_v2` (decided: option A)

15 new concepts `c051`–`c065` in `simready/bench/prompts/concepts_v2.jsonl`, written before any
DSL v2 code, picked by category (4 standard parts, 4 plates/brackets, 4 turned parts, 3
housings/blocks), graded by the unchanged checker 1.0.0 with v1 check types only. Source and
controls: `scripts/bench_concepts_v2.py` (OCCT positive control per phrasing, named negative
controls, volume ranges from tolerance-corner rebuilds, DSL v1 reference specs for the 4 v1
in-vocab concepts). Draft committed `ea978a1`.

- The user proofreads the file (flagged ranges: DIN 562, ISO 2341, the 1602 LCD pattern; confirm
  ISO 4762, K7, DIN 471), then `concepts_v2.sha256` is frozen **before Task 2 of the plan starts**.
  An official run refuses an unfrozen or changed file, as SP1 does.
- **Honest limit:** the set was written after the op list below was proposed, so it is held out
  from op *design*, not written blind. With the general `prism` op every one of its 11 v1-OOV
  concepts is expressible in DSL v2. It therefore measures whether models *use* the new ops on
  parts the ops were not designed around, and carries the DSL-vs-code comparison; it does not
  test whether the vocabulary is sufficient. The report says this in its method section.
- The 13 v1 out-of-vocab concepts are the **design set**: reported, but labelled as the concepts
  the ops were designed from.

### E2. DSL v2 op set (approved)

Versioned, never edited in place: `simready/gen/spec.py` (v1) stays byte-identical so SP1 logs,
regrade and replay keep their meaning; v2 lives in `simready/gen/spec_v2.py` and
`simready/gen/build_v2.py`. Every v1 spec is a valid v2 spec that builds the same shape.

| Op | Fields | Notes |
|---|---|---|
| `box` | `dx, dy, dz, at` | unchanged |
| `cyl` | `r, h, at, axis="z"` | `axis` ∈ `x`, `y`, `z`; extrudes along +axis from `at` |
| `cone` | `r1, r2, h, at, axis="z"` | `r1` at `at`, `r2` at `at + h·axis`; each ≥ 0, not both 0, `r1 ≠ r2` |
| `sphere` | `r, at` | `at` = centre |
| `prism` | `points, h, at, axis="z"` | closed polygon of 3–12 `[u, v]` points, extruded `h` along +axis from `at`; plane mapping `z: (x, y)`, `x: (y, z)`, `y: (x, z)` |
| `regular_prism` | `sides, across_flats, h, at, axis="z"` | 3–12 sides, centred on `at`, one flat parallel to `u` |
| `polar` | `of, count, center, axis="z"` | union of `count` copies of step `of`, rotated by 360°/count about the axis through `center`; copy 0 = original |
| `grid` | `of, nx, ny, dx, dy` | union of `nx × ny` copies of step `of`, translated by `i·dx` along X and `j·dy` along Y |
| `fillet` | `a, r, edges` | rounds the selected edges of step `a` |
| `chamfer` | `a, d, edges` | equal-distance chamfer of the selected edges of step `a` |
| `fuse`, `cut` | `a, b` | unchanged |

- `edges` selector (CadQuery style, chosen because models have seen it): `"all"`; `">x"`, `">y"`,
  `">z"` = edges whose midpoint is at the maximum of that coordinate (±1e-6 mm); `"<x"`, `"<y"`,
  `"<z"` = minimum; `"|x"`, `"|y"`, `"|z"` = straight edges parallel to that axis.
- `polar` and `grid` count as references to `of` for the orphan rule (`a ≠ b` and prior-step rules
  apply to `of` too). `pattern` in the brainstorm is split into these two ops so each has a flat
  schema.
- Step cap stays **16**; with `polar`/`grid` the longest v2 concept (c056) needs 9 steps, and a
  larger cap would hide whether models use the patterns.
- A fillet/chamfer the kernel cannot build is `F4_build_error`, like any build failure.
- Stays out of vocab: `c045` threaded rod, `c046` involute gear.
- **Positive control:** every concept expressible in v2 (all 65 except c045, c046) gets a
  hand-built v2 reference spec in `simready/bench/prompts/reference_specs_v2.json`; a test builds
  each and asserts it passes its explicit and engineer checks. This file, not the concept files,
  defines v2 in-vocab, so the frozen concept files are never edited.
- The copilot product keeps DSL v1 (`BUILD_PART_TOOL_SCHEMA`) until SP2 results are published;
  switching it is a separate decision.

### E3. Models (decided: option A)

The D Labs reference pair (`gpt-6.1-sol`, `gemini-4-argon`, unchanged provider entries) plus one
small open model (~3–4B instruct) served locally by `llama-server`. The small model is chosen by
the `sp3-entry-gate` survey (Unsloth GRPO + GGUF support, spec D5 "Open"), so its DSL v1 run on
`concepts_v1` **is** the SP3 entry-gate baseline. Installing `llama-server` and downloading
weights is a separate approval at execution time.

### E4. Free-form build123d arm (decided: option A, ADR 0005)

- The model answers with one fenced Python block that builds a build123d solid and assigns it to
  `part`. No tool call. Same concepts, phrasings, `k`, temperature and checker.
- The code runs in its own process from a **dedicated venv** `~/.venvs/simready-b123d`
  (build123d needs `cadquery-ocp-novtk>=8.0,<8.1`, which conflicts with the bench extra's
  `cadquery-ocp==8.0.1.1.0`). The child gets an empty temp directory as cwd, an environment with
  no API keys (only `PATH`, `HOME`=temp dir, `PYTHONNOUSERSITE=1`), `python -I`, rlimits (CPU
  60 s, address space 4 GiB, file size 64 MiB, no core), a 90 s wall-clock kill, and writes
  exactly one file `part.step`.
- Before execution an AST gate allows only `import build123d` / `from build123d import …` and
  `import math` / `from math import …`; it rejects `open`, `exec`, `eval`, `compile`,
  `__import__`, `globals`, `locals`, `vars`, `getattr`, `setattr`, `delattr`, `input`,
  `breakpoint`, any name or attribute starting with `_`, and `async`/`await`.
- The parent (bench venv) reads `part.step` and grades it with `grade_shape` — the same checker.
- **Honest limit (stated in ADR 0005):** network access is not blocked at OS level. Unprivileged
  user namespaces are disabled on the VPS (`kernel.apparmor_restrict_unprivileged_userns = 1`;
  `unshare -rn` fails), and bwrap/docker are not installed. Acceptable because the code comes
  from the benchmarked models, not from users; the arm is benchmark-only and never wired into
  the copilot.
- Failure-class mapping for the code arm: no fenced block → `F1_no_parse`; AST gate rejection →
  `F2_schema`; exception, missing `part`, or no solid written → `F4_build_error`; wall-clock kill
  → `F8_timeout`; then the checker's `F5`/`F6`/`F7`. `F3` and `F9` do not apply.
- Creating the venv and installing build123d is a separate approval at execution time.

### E5. Repair pass (decided: option A)

- Feedback = failure class + what was **measured on the model's own part**: bbox extents, volume,
  solid count, gate reason, every cylindrical feature (diameter, hole or boss, through or blind,
  length), or the schema/build error text. **Never** the target ranges, check list, or check
  detail strings (they contain the ranges). A test asserts no range bound of the attempt's checks
  appears in the feedback.
- Up to 2 retries per failed scored attempt, continuing the same conversation (original reply,
  then the feedback as the tool result or user turn). Excluded attempts are never repaired.
- Reported as **pass@1 after repair**, next to single-shot pass@1, never merged into it (SP1 D6).
  Repair logs are separate files whose header names `repair_of`.
- Runs first on SP1's logged failures (`cd5d693`, no new single-shot calls), then on the SP2 DSL v2
  and build123d runs.

## Run matrix (all `k = 5`, temperature 0.7, official, frozen files)

| Arm | concepts_v1 (150 prompts) | concepts_v2 (45 prompts) |
|---|---|---|
| DSL v1 | reference pair: SP1 logs reused; small model: new (= SP3 entry gate) | all three models |
| DSL v2 | all three models | all three models |
| build123d | all three models | all three models |

Plus repair runs on every failed scored attempt of the SP1 logs and of the DSL v2 and build123d
runs.

## Pre-registered results (fixed now; nothing substituted after the runs)

Per model, pass@1 with 95% bootstrap CI over concepts (SP1 method), and for comparisons the paired
difference with a paired bootstrap CI over concepts:

1. **Regression:** DSL v2 − DSL v1 on the 37 v1 in-vocab concepts.
2. **Vocabulary:** DSL v2 pass@1 on the design set (11 of the 13 v1-OOV, i.e. without c045/c046)
   and on the held-out set (`concepts_v2`, all 15); DSL v1 on the same sets for the before value.
3. **DSL vs code:** DSL v2 − build123d on the 63 concepts in DSL v2 vocabulary; build123d alone on
   c045/c046 reported separately.
4. **Repair:** pass@1 after repair − single-shot pass@1, per arm, on the same attempts.
5. Failure-class tables per arm; cost table (tokens, latency, calls).

Published in `docs/validation/bench_v2.md` regardless of outcome. SP3's metric (single-shot pass@1
on held-out prompts, D6) is unchanged.

## Out of scope

New check types or a checker version bump (checks are v1 types only); changing `concepts_v1`;
switching the copilot to DSL v2; GRPO (SP3); thread and gear ops.

## Risks

- **Ceiling:** the reference pair may sit near 96% on every arm; the small model carries the
  DSL-vs-code signal.
- **Small-model runtime on CPU is unmeasured:** the plan's smoke step measures seconds per call
  before the full matrix is launched; if the matrix would take more than ~48 h (threshold proposed
  by the assistant, not measured) the user decides
  whether to reduce `k` for the small model (reported if so).
- **Selector semantics:** CadQuery-like strings are a convention, not CadQuery; the tool
  description defines them exactly.
