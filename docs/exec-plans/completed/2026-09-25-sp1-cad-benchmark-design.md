# SP1: Checker-scored text-to-CAD benchmark + harness (design)

**Status:** done
**Last verified:** 2026-11-18
**Stage:** complete — `bench_v1.md` and official logs published (`4420e2b`..`44cf98a`).

**Context:** First of three sub-projects (SP1 benchmark + harness → SP2 generation vocabulary v2 →
SP3 post-training with checker reward). Informed by `earthtojake/text-to-cad` (MIT: validity
checks, repair-loop failure taxonomy) and `Adam-CAD/CADAM` (GPL-3: nothing copied; prompt style
only). Neither repo scores its output; this benchmark is the piece they lack.

## Goal

Measure single-shot text-to-CAD generation with code-checkable constraints, so that "is model A
better than B" and (in SP3) "did training help" have defensible numbers. Deliverables: 50-concept
prompt file, checker, runner with replayable logs, `bench_v1.md` report for Gemini-4-Argon and GPT-6.1
Sol (D5, changed 2026-11-17). The small-model baseline is run at the start of SP3 (D5).

## Done when

1. `concepts_v1.jsonl` has 50 concepts × 3 phrasings, proofread by the user, and its hash is frozen.
   Every in-vocab concept carries a hand-built `reference_spec` that builds and passes all of its
   own checks (§1 rule 7).
2. Every check type has unit tests on hand-built STEP parts (known pass and known fail per type).
3. Official runs are complete for Gemini-4-Argon and GPT-6.1 Sol (D5). The small-model baseline run is
   **not** an SP1 criterion: it is SP3's first task and SP3's entry gate (decided 2026-10-04).
4. `bench_v1.md` has all §3 tables; official logs committed per D7.
5. The README "Reproduce the benchmark" commands have been run on a clean clone and give the
   published numbers.

## Locked decisions

### D1. Generation target: extend the typed DSL (decided 2026-09-23)

SP1 benchmarks the current 4-op DSL (`box`, `cyl`, `fuse`, `cut`); SP2 extends it. Free-form
build123d code generation ("Option C") is deferred until SP1 ships, then run as a measured
DSL-vs-code comparison on the same benchmark.

**Why:** keeps ADR 0001 (no LLM code execution, validate before build, failures become
validator rules). A small grammar gives clean failure classes and is learnable by a 3B model in
SP3. Option C later turns "DSL vs code" from opinion into data.

### D2. Prompt authorship: assistant writes, user proofreads (decided 2026-09-25)

**Why:** fastest route; the user's mechanical-engineering judgement catches unrealistic parts and
tolerances, which is the part no automated check covers. Templated prompts rejected: SP3 training
prompts are templated, so a templated test set would leak into training.

### D3. Each concept is phrased three ways, not an 80/20 explicit/realistic split (decided 2026-09-25)

Every part concept appears as:

1. **Explicit:** every dimension stated. Tests geometry execution.
2. **Engineer-style:** function + standards ("NEMA 17 mount, 5 mm plate"). Tests mechanical reasoning.
3. **Intent-only:** ("something to hold a small stepper on a wall"). Tests handling of ambiguity;
   only validity + implied constraints graded.

**Why not the earlier 80% explicit / 20% realistic proposal:** the user pointed out that engineers
do not request parts with every dimension spelled out, so an 80%-explicit benchmark mostly tests
instruction following. The key realisation: realistic requests are underspecified in *numbers*,
not in *constraints*. Constraints come from standards and engineering logic (ISO 273 clearance
holes, NEMA hole patterns, bearing seat bores, minimum walls, envelopes) and are graded as
**ranges**. What is genuinely free (overall shape, rib placement) is marked `not_checked`, never
silently passed.

**Why keep the explicit phrasing at all:** as a control. When a model fails the engineer-style
prompt, the explicit twin of the same part tells us whether it lacked the mechanical knowledge or
could not build the geometry.

**Headline metric this enables:** *mechanical-reasoning gap* = pass rate (explicit) − pass rate
(engineer-style), on the same parts. Paired, so it needs fewer samples than independent sets.

### D4. Size: v1 = 50 concepts × 3 = 150 prompts; v1.1 = 100 concepts (decided 2026-09-25)

**Why 50 first:** the first run always exposes bad checks, wrong tolerances and ambiguous prompts,
and those are cheaper to fix across 150 prompts than 300. User proofreading (~2–3 h vs ~5–6 h)
is the bottleneck, and a long review before any result invites stalling. Runtime ~5 h vs ~10 h
at k=5 × 3 models. Pairing already reduces variance.
**Why grow to 100:** roughly ±15–16 pp → ±11 pp confidence per phrasing on the in-vocab subset
(~40 of 50 concepts in v1; the earlier ±14 pp → ±10 pp figure assumed all concepts count), and
more held-out concepts for the SP3 eval. v1 results decide *which* concepts to add (e.g. harder parts rather than more plates).
**Constraint:** concept IDs are stable and the prompt file is append-only, so v1.1 is an
extension, not a rewrite. v1.1 lands before SP3 starts.

### D5. Models and attempts (decided 2026-09-25)

- **Reference models (API, user's key):** Gemini-4-Argon and GPT-6.1 Sol, both on D Labs
  (`https://api.dlabkeys.com/v1`, one shared key). They are graded only, never trained: they set
  the ceiling that gives the SP3 result a scale. Ranking strong models against each other is not
  a goal of v1.
- **Changed 2026-11-17 (user decision); was GLM-5.3 and DeepSeek V4.1 Flash on Vultr.** Reasons:
  D Labs stopped injecting a `reason` key into tool-call arguments (provider fix, 2026-11-17;
  re-checked with the 12-call repro and 36 bench attempts, 0 affected), and it avoids a Vultr top-up
  (the GLM-5.3 official run was estimated at about $11 there; D Labs prices not recorded). Headroom check the same day,
  k=1 over all 150 prompts: pass@1 on in-vocab prompts Gemini 94.6% [90.1, 98.2], GPT 95.5%
  [91.9, 99.1]; the two are not separable, which is accepted because the pair only marks the
  ceiling. Known caveats: both models share one provider and one daily quota (not measured);
  intent-phrasing passes lean on weak checks (see `sp1-concepts-proofread`). DeepSeek V4.1 Flash
  on D Labs was not chosen: it used about 2.5x fewer completion tokens than on Vultr and 3 of 12
  replies were unparseable (spec sent as a string with arithmetic inside).
- **Model IDs:** the exact API ids, base URLs and tool-calling support of both reference models are
  verified with a live list-models / one-call smoke test before the prompt file is frozen; the
  verified ids go into the report setup table.
- **Baseline:** Qwen2.5-3B-Instruct base (GGUF via local llama-server) is the working choice, run
  *after* the two API models as SP3's first task (not an SP1 criterion, decided 2026-10-04).
  **Open (user, 2026-10-04):** before SP3 locks, check newer ~3–4B instruct models with Unsloth GRPO
  + GGUF support and propose one; Qwen2.5-3B is kept only if nothing newer fits (continuity with
  the existing QLoRA notebook is the argument for it). Not on disk as of 2026-09-25; the user
  installs llama-server and downloads the GGUF when the API runs finish (assistant supplies the
  commands). This is the before-number for SP3.
- **k = 5 attempts per prompt:** reports pass@1 (reliability) and pass@5 (capability). The gap
  on Qwen-3B predicts whether SP3's RL can help (RL raises pass@1 toward pass@k; it rarely
  creates capability where pass@k is ~0).
- **Budget:** 150 prompts × 5 = 750 calls per model per single-shot run, under one day per model.
  Raw outputs are logged, so re-grading after a checker fix costs no API calls.
- **Llama-3.3-70B dropped.** Report must state that earlier numbers
  (`docs/validation/geometry_gen_eval.md`: GLM 5.2 / Llama-3.3-70B, 5 prompts) come from a
  different setup (different models, prompts and metric) and must not be compared to benchmark
  numbers.

### D6. Single-shot only; repair mode deferred (decided 2026-09-25)

SP1 measures single-shot generation only: one answer per attempt, graded as-is.
**SP3's metric is fixed now: single-shot pass@1 on held-out prompts, before vs after training.**
No other number may be substituted after the results are in.

**Why repair mode (validator/checker error → model retries) is not in SP1:** raised by the user.
It answers a different question (how much the feedback loop helps), which is a harness talking
point, not an SP3 input. Building it now enlarges SP1 without serving SP3.
**Why deferring is free:** every failed attempt is logged with its error, so a later repair run
starts from the stored failures; the single-shot run is never repeated. Tracked in BACKLOG.

### D7. Layout (approved by user 2026-09-25)

| What | Where | Tracked |
|---|---|---|
| Checker, runner, report code | `simready/bench/` (new subpackage) | yes |
| Prompts + constraints | `simready/bench/prompts/concepts_v1.jsonl` | yes |
| Working run output (STEPs, scratch) | `data/bench_runs/` | no (gitignored, like `data/gen_eval/`) |
| Report + headline numbers | `docs/validation/bench_v1.md` | yes |
| Replay logs of the official run | `docs/validation/bench_v1/runs-<model>.jsonl.gz` (~1–2 MB) | yes |

**Why commit the official logs:** "every attempt is replayable" is only checkable if the logs
are public; a reviewer can re-grade the run themselves.

### D8. Tool schema stays prose; every validation bound is stated (decided 2026-11-17)

`build_part`'s `spec` parameter stays `"type": "object"` with the grammar in prose. It is not
replaced by a typed JSON schema generated from `PartSpec.model_json_schema()`.

**Why:**
- **No error to fix.** About 300 headroom attempts by the two reference models had 0 `F2_schema`.
  The failures that raised the question came from DeepSeek V4.1 Flash on D Labs, which is not a
  reference model, and its replies were not valid JSON, which a schema fixes only where the
  provider enforces it while decoding.
- **It would make the number depend on the server.** Some servers (llama-server is believed to,
  unverified) compile a tool's JSON schema into a decoding grammar. The SP3 baseline would then
  have its schema errors blocked by the server while the API models are graded on what they
  write, and the before-number and the ceiling would measure different things.
- **Schema errors are a signal for SP3.** They are what a small model gets wrong first; RL can
  learn from them only if they are graded.

**Rule kept from this:** the description states every bound `PartSpec` enforces (step cap,
dimension, radius and placement limits), generated from the `simready/gen/spec.py` constants, so
no model is graded on a rule it was never told. A new bound in `PartSpec` goes into the
description in the same change. Revisit if a reference model's official run shows `F2_schema`
above a few percent.

## Design §1: Concept format and checker (approved 2026-09-25)

One JSONL line per concept: `concept_id`, `name`, `in_vocab`, `prompts{explicit, engineer,
intent}`, `checks{explicit, engineer, intent}` (list per phrasing), `sources` (standards the
ranges come from, e.g. "NEMA 17 pattern 31.0 mm; ISO 273 M3 clearance 3.2–3.6").

Checker rules:
1. **Validity gate first** (after text-to-cad): BRep valid, closed shell, positive volume,
   expected solid count (default 1). Gate fail ⇒ attempt fails, no further checks. Blocks
   empty-shell-with-right-envelope cheats.
2. **Placement-invariant:** extents compared sorted (`bbox_sorted`); hole patterns compared by
   pairwise centre distances. Orientation checked only when the prompt states it.
3. **Tolerances:** explicit ±0.1 mm on stated numbers; engineer = the standard's own range;
   intent = wide ranges + `any_of` alternatives.
4. Each check returns `pass` / `fail` / `not_checked`. Attempt passes iff gate passes and all
   checks pass. Partial score (fraction passed) is logged for analysis and the SP3 reward.
5. v1 check types: `bbox_sorted`, `bbox_min_dim`, `volume`, `hole_set` (count, diameter,
   through/blind, pattern), `bore` (diameter + min depth), `boss`, `solid_count`. Minimum wall
   thickness deferred to v1.1: `not_checked` beats an untrusted check.
6. **In-vocab** means buildable in the current DSL as it actually is (`simready/gen/spec.py`):
   axis-aligned boxes, cylinders along **+Z only** (no rotation op), `fuse`/`cut`, and **at most 16
   steps**. So fillets/chamfers/true revolves are out, and so are holes on two non-parallel faces
   (L-bracket with holes in both legs, cross-drilled shaft) and parts that need >16 steps (e.g. a
   6-hole bolt-circle flange is ~17). Out-of-vocab concepts get `in_vocab: false` and are reported
   **separately** (the SP2 gap), never mixed into the main pass rate. Expect more than ~10 of 50
   to land here; the count is whatever the reference specs show. Tubes, spacers and simple flanges
   (stacked cylinders + cuts within 16 steps) count as in-vocab.
7. **Reference spec (added 2026-10-04):** every in-vocab concept carries a hand-built
   `reference_spec` per phrasing family; the test suite builds it and asserts it passes every
   check of the explicit and engineer phrasings. This proves the concept is buildable and gives
   each check a known-good positive control, so an unsatisfiable check is caught before any API
   call.

## Design §2: Runner and replay log (approved 2026-09-25)

Pipeline per attempt: model API → parse → Pydantic validate → build STEP → checker → log line.
Validate/build/check run in a killable subprocess with a 60 s timeout.

- Same system prompt for all models: the `build_part` DSL schema + rules from the product's tool
  description, versioned by hash.
- Accepts a tool call **or** JSON in text; logs which (`via: tool|text`), so provider
  tool-calling differences show up separately.
- Temperature 0.7, fixed max tokens, seed where supported; all params logged.
- Checker only, not the full analysis pipeline (40–420 s/part) ⇒ runs take hours, not days.
- 4 workers per model; configurable requests/min per provider; 429 ⇒ exponential backoff; clean
  stop when the daily quota is exhausted.
- Resume: (model, prompt, attempt_idx) already logged ⇒ skipped. `--limit N` for smoke tests.
- Log line: run id, model, params, prompt-file hash, checker version, concept, phrasing,
  attempt idx, raw response, token usage, latency, parsed spec, schema errors, build error, STEP
  fingerprint, gate + every check result, partial score, pass, failure class. **API keys never logged**
  (base URL only).
- STEP files are not stored: the executor is deterministic, so `replay` rebuilds from the logged
  spec and verifies a **geometric fingerprint** (volume, surface area, bbox, face/edge counts,
  rounded), **not** the STEP file hash. STEP headers carry a timestamp, so byte hashes differ on
  every rebuild.
- **Official run:** uses the frozen prompt-file hash and a tagged checker version, both in the log
  header. A checker fix after the run goes through `regrade` and bumps the report version; logged
  specs are never edited.

### Commands (must appear in the README, "Reproduce the benchmark"; requested by user 2026-09-25)

| Command | What it does | Needs API keys? |
|---|---|---|
| `python -m simready.bench run --model <id> --k 5 [--limit N]` | run the benchmark | yes |
| `python -m simready.bench regrade <run>` | re-run the current checker on logged specs | no |
| `python -m simready.bench replay <run> <attempt_id>` | rebuild one attempt, verify its geometric fingerprint | no |
| `python -m simready.bench report <runs...>` | produce the `bench_v1.md` tables | no |

**README requirement:** a recruiter with no API keys can reproduce every published number from
the committed official logs (D7). Two paths, both stated in the README with exact commands:
- **Quick path:** `report` only. Plain Python, no OCC; reads logged results; about a minute.
- **Full path:** set up the OCC conda env (~10–15 min), then `regrade` (re-grades every logged spec
  with the checker) and `replay` (rebuilds any attempt and verifies its fingerprint).
Both paths are verified by running them on a clean clone before the section ships.

## Design §3: Failure classes and report (approved 2026-09-25)

One **primary** failure class per failed attempt (first failing stage); all check results are
still logged.

| Class | Stage | Example |
|---|---|---|
| F1 `no_parse` | answer | no tool call and no parseable JSON |
| F2 `schema` | validation | negative dimension, unknown field |
| F3 `reference` | validation | boolean refers to a later step; orphan step |
| F4 `build_error` | kernel | OCC raises during build |
| F5 `invalid_solid` | gate | open shell, negative volume, wrong solid count |
| F6 `dimension_miss` | checks | envelope, bore or boss out of range |
| F7 `feature_miss` | checks | hole count, diameter or pattern wrong |
| F8 `timeout` | subprocess | build/check over 60 s |
| F9 `out_of_vocab` | answer | uses an op the DSL lacks (e.g. `fillet`) |

**F9 precedence:** the DSL forbids unknown fields and discriminates on `op`, so `{"op": "fillet"}`
would otherwise fail schema validation and be classed F2. The runner therefore checks every
step's `op` name against the known set **before** Pydantic validation; any unknown op ⇒ F9.

**`infra_error`** (API failure after retries: 5xx, network) is excluded from scoring and retried on
resume. A provider outage must never count as a model failure.

**Metrics:** pass@1 = mean success over all attempts of a prompt; pass@5 = share of prompts with at
least one passing attempt (n = k = 5, so exact). Mechanical-reasoning gap = pass@1 (explicit) −
pass@1 (engineer), per model, on in-vocab concepts.

**`bench_v1.md` tables:**
1. Setup: exact model ids, run dates, params, prompt-file hash, checker version; note that numbers
   are not comparable to `geometry_gen_eval.md` (D5).
2. Headline: pass@1 and pass@5 per model on in-vocab prompts, 95% CI by bootstrap **over
   concepts** (the 15 attempts per concept are not independent).
3. By phrasing: explicit / engineer / intent pass@1 per model + mechanical-reasoning gap with a
   paired bootstrap CI.
4. Failure-class distribution per model × phrasing.
5. Out-of-vocab concepts, separately: admits it can't (F9) vs fakes the feature.
6. Cost: tokens, median latency, calls.
7. Three annotated failures with renders, picked from the **most frequent** failure classes.
8. Known limits: count of `not_checked`, no wall-thickness check, author-chosen tolerances,
   single author + single proofreader.

**Honesty rules:** the report is published whatever the numbers are; models are not dropped after
seeing results; SP3's metric stays the one fixed in D6.

### Implementation deviations (plan 2026-10-04, reported per Rule 2)

1. `solid_count` is the gate's `Concept.solids` parameter, not a separate check type (it would grade the gate twice).
2. The checker grades the in-memory shape; no STEP is written per attempt (STEPs are not stored; replay uses the fingerprint).
3. New excluded class `checker_error`: a crash in our checker is excluded from scoring like `infra_error` and fixed via `regrade`.
4. The system prompt allows a refusal ("say so instead of calling the tool"), which gives table 5 its "admits it can't" path.
5. Benchmark `sorted_extents` uses `brepbndlib.AddOptimal(shape, box, False, False)` to exclude OCC's 1e-7 mm per-side gap: nominal dimensions must pass engineer ranges capped at nominal. Shared `shape_bounding_box` retains its gap; bounding boxes use `CornerMin`/`CornerMax` for OCP 8 compatibility.
6. A pythonocc-first `simready.occ_compat` shim also supports pip-installed OCP, because pythonocc-core has no usable PyPI release. Build, shared geometry, benchmark geometry and the validator import block use it; callers retain pythonocc spelling while OCP static methods, curve length and indexed shape-map types are adapted centrally. Other OCC importers remain outside this compatibility scope.
7. Continuous range checks in `checker.py` (`BBoxSorted`, `VolumeCheck`, `HoleSet`/`Bore`/`Boss` diameters, and pairwise hole-pattern distances) apply the same `_EPS = 1e-6` mm slack already used on `BBoxMinDim`/`depth_min`/`height_min`, because OCCT `AddOptimal` on perpendicular-cylinder B-spline seams returns `10.0000002` mm (`2e-7` mm numerical noise) on exact 10 mm geometry (`9c84dee`). Integer hole/boss counts remain exact.
