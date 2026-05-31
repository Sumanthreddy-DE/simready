# Geometry-Gen MVP — Plan

**Status:** scoping locked 2026-05-28 (Brainstorm A) → build in progress.
**Owning backlog item:** `S1 · geometry-gen-mvp` (BACKLOG.md).
**Strategy context:** rank 5 of `docs/strategy/mecagent-gap-and-drift-2026-05-26.md` — closes the JD's first bullet ("geometry generation"), currently zero coverage.

The MecAgent JD's headline ask is generation, not analysis. SimReady is analysis-only today. This MVP adds a constrained generate → validate → refine loop so the LLM can emit small parts on demand and the existing pipeline + BRepSAGE judge them.

## Locked decisions

| # | Decision | Choice | Why |
|---|---|---|---|
| 1 | Exec model | **A** — JSON DSL → trusted `build_shape(spec)`. No LLM code ever exec'd. | Grammar is tiny (2 primitives + 2 booleans + translate); codegen-with-sandbox adds attack surface without adding capability. Maps onto the existing structured tool-call architecture in `simready/copilot/agent.py`. |
| 2 | Refine-loop semantics | **R1** — separate tools, LLM-driven multi-turn loop. `build_part` and `analyze_geometry` are independent tools; the LLM decides whether to refine after reading analyze. | Reuses the existing `agent.py` multi-turn loop; zero new control flow; bounded by `max_turns`. |
| 3 | DSL surface (v1) | **G1** — `box`, `cyl` (axis fixed `+Z`), `fuse`, `cut`. Integer step-index refs. Matches `scripts/generate_parametric_steps.py` exactly. | Same vocab the model was trained on. Smallest viable schema. |
| 4 | Ship gate | **E_grammar** — 5 hand-written natural-language prompts, one per `generate_parametric_steps.py` category (`normal_box`, `thin_plate`, `l_bracket`, `bracket_with_hole`, `small_feature_box`). Each must round-trip to a schema-valid + OCC-valid STEP whose face count falls in a hand-checked range (`[6,6]` for single-box archetypes, `[10,14]` for L-bracket fuse, `[6,10]` for a box-minus-through-cyl — exact face counts were sanity-checked against `tests/test_gen_build.py`). | Maps the ship gate onto the model's training distribution. Defensible interview claim. |
| 5 | Module layout | **T1** — new `simready/gen/{spec,build}.py` + `build_part` tool in `simready/copilot/tools.py` + `scripts/simready_gen.py` CLI. | Clean separation; matches existing `simready/copilot/` layout. |

### Unilateral build-side decisions (not separately approved; flag if wrong)

- **`build_part` runs in a spawn subprocess by default** (`multiprocessing.spawn` + `Process.terminate()` after `--build-timeout`, default `15 s`). Same hang-protection pattern as `scripts/eval_real_cad.py`. The OCC primitives (`BRepAlgoAPI_Cut`, `BRepPrimAPI_MakeBox`) can deadlock on degenerate inputs (zero-overlap cut, coplanar fuse) and Python thread timeouts do not kill C++ (per `lessons_pythonocc-gotchas.md`).
- **`build_part` returns** `{step_path, schema_valid, occ_valid, faces, bbox_mm}` — small, deterministic, no `analyze_geometry` piggyback. The LLM is system-prompted to call `analyze_geometry` next.
- **Defect head is advisory, never a stop gate.** Per `docs/validation/real_eval.md` §1 the head false-positives at 100 % on clean industrial CAD; making it a hard gate would force the LLM to refine forever. The gating signal is `occ_valid` + `analyze_geometry` Critical/Major counts.

## File map

```
docs/
  exec-plans/geometry-gen-mvp.md     (this file)
  adr/0001-geometry-gen-dsl-over-codegen.md
simready/
  gen/
    __init__.py
    spec.py     # Pydantic: PartSpec, BoxOp, CylOp, FuseOp, CutOp
    build.py    # build_shape(spec) -> TopoDS_Shape; build_part_subprocess(spec_dict, timeout) -> dict
  copilot/
    tools.py    # +build_part tool (schema + resolver); +_DISPATCH entry
scripts/
  simready_gen.py     # CLI: prompt -> LLM -> spec -> STEP (follow-up commit)
tests/
  test_gen_spec.py    # Pydantic schema contracts
  test_gen_build.py   # executor: spec -> shape -> STEP -> face count
  test_copilot_tools.py     # +build_part wiring smoke
  data/gen_prompts.jsonl    # E_grammar 5-prompt eval set (follow-up commit)
  test_gen_e2e.py           # E_grammar runner (LLM-dependent; follow-up commit)
```

## DSL — v1 schema

```python
# Pseudocode; canonical in simready/gen/spec.py.
class BoxOp(BaseModel):
    op: Literal["box"]
    dx: PositiveFloat   # mm, (0, 1000]
    dy: PositiveFloat
    dz: PositiveFloat
    at: tuple[float, float, float] = (0.0, 0.0, 0.0)  # mm

class CylOp(BaseModel):
    op: Literal["cyl"]
    r:  PositiveFloat   # mm, (0, 500]
    h:  PositiveFloat   # mm, (0, 1000]
    at: tuple[float, float, float] = (0.0, 0.0, 0.0)

class FuseOp(BaseModel):
    op: Literal["fuse"]
    a:  NonNegativeInt  # 0-based index into prior steps
    b:  NonNegativeInt

class CutOp(BaseModel):
    op: Literal["cut"]
    a:  NonNegativeInt
    b:  NonNegativeInt

Op = Annotated[BoxOp | CylOp | FuseOp | CutOp, Field(discriminator="op")]

class PartSpec(BaseModel):
    steps: list[Op]  # len 1..16

    # Cross-field validation:
    # - every fuse/cut ref index must be < its position
    # - last step must produce a solid (not be a primitive ref'd by nothing later)
```

Bounding-box clamp on dims keeps generated parts inside the parametric distribution the model was trained on (20–100 mm typical).

## Test plan

### `tests/test_gen_spec.py` (no OCC needed)

- accepts minimal valid spec
- rejects: empty `steps`, `steps` > 16, negative dims, zero dims, ref out of range, ref >= own index, unknown `op`, extra fields
- accepts: each of the 4 op types in isolation
- rejects: dims above range cap

### `tests/test_gen_build.py` (sr env, OCC needed)

- `build_shape(box-only spec)` → shape with 6 faces
- `build_shape(box + cyl + cut)` → shape with 10-14 faces (matches `bracket_with_hole`)
- `build_part_subprocess(...)` returns `{step_path, schema_valid, occ_valid, faces, bbox_mm}` for a happy spec
- `build_part_subprocess(...)` returns `{error: build_timeout}` when a degenerate spec hangs (synthetic: cut(box, far-away cyl) — should not actually hang but exercises the path)
- STEP file is written under a tempdir and round-trips through `validate_step_file`

### `tests/test_copilot_tools.py` (smoke)

- `dispatch_tool("build_part", {"spec": {...minimal box spec...}})` returns a dict with `step_path`, `occ_valid: True`, `faces: 6`
- the new schema is in `TOOL_SCHEMAS` and the LLM-facing description names DSL ops verbatim

### `tests/test_gen_e2e.py` (LLM-dependent — follow-up commit)

- `tests/data/gen_prompts.jsonl` carries the 5 E_grammar prompts.
- Per prompt: run the agent with `build_part` + `analyze_geometry` tools, assert the final STEP is OCC-valid and has face count in the prompt's `expect.faces` range.
- Mark `pytest.mark.live_llm` so CI skips it; runner reads `OPENAI_BASE_URL` + `OPENAI_API_KEY` from env.

## Out of v1 (deferred)

- Fillets, chamfers, drafts, lofts, sweeps, NURBS — the contrarian warning explicitly says "constrained, not open-ended B-rep generation."
- Multi-solid assemblies.
- Rotation axis on cyl (G2) — add only if the 5 E_grammar prompts demand it.
- Named refs (G3) — only if the LLM's index-ref error rate is high.
- Parametric variables / conditionals / loops — the LLM does parameterization in its head.
- Streamlit UI panel for generation. Add after the agent loop ships.
- A `view-as-code` toggle that pretty-prints the executed spec as pythonOCC source — interview optics, not a v1 requirement.

## Ship sequence

1. **Commit 1 (this commit):** plan + ADR + `spec.py` + `build.py` + the three test files (`test_gen_spec.py`, `test_gen_build.py`, `test_copilot_tools.py` additions). All tests pass under sr env. No LLM dependency.
2. **Commit 2 (follow-up):** `tests/data/gen_prompts.jsonl` + `tests/test_gen_e2e.py` + the live-LLM smoke run. User runs against NIM, captures pass/fail per prompt.
3. **Commit 3 (follow-up):** `scripts/simready_gen.py` CLI + a Streamlit panel showing the generation loop.

## Risks (honest)

- **The LLM may emit specs that round-trip but produce parts the user didn't ask for** (e.g. an L-bracket with the upright on the wrong side). E_grammar's face-count gate catches gross topology errors but not orientation/placement errors. Mitigation: human-eye the 5 E_grammar outputs once before claiming "the loop works."
- **The training data was synthetic parametric** (`generate_parametric_steps.py`). The defect head is OOD on real CAD (per `real_eval.md`) — when `build_part` produces something close to the training distribution, the defect head should at least not over-fire as badly as on real industrial parts. If it does over-fire even on generated parts, that is its own diagnostic finding (the head is fragile, period) — capture it in the e2e run results.
- **Subprocess overhead** (~5–10 s spawn on Windows) means each build adds latency. Acceptable for a demo; if interview-day responsiveness matters, swap to a persistent worker subprocess later.
