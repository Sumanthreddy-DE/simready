# SP1: Checker-scored text-to-CAD benchmark + harness (design)

**Status:** active
**Last verified:** 2026-09-25
**Stage:** design complete, awaiting user review of this spec. Next: implementation plan.

**Context:** First of three sub-projects (SP1 benchmark + harness → SP2 generation vocabulary v2 →
SP3 post-training with checker reward). Informed by `earthtojake/text-to-cad` (MIT: validity
checks, repair-loop failure taxonomy) and `Adam-CAD/CADAM` (GPL-3: nothing copied; prompt style
only). Neither repo scores its output; this benchmark is the piece they lack.

## Goal

Measure single-shot text-to-CAD generation with code-checkable constraints, so that "is model A
better than B" and (in SP3) "did training help" have defensible numbers. Deliverables: 50-concept
prompt file, checker, runner with replayable logs, `bench_v1.md` report for GLM-5.3, DeepSeek V4.1
Flash and Qwen2.5-3B base.

## Done when

1. `concepts_v1.jsonl` has 50 concepts × 3 phrasings, proofread by the user, and its hash is frozen.
2. Every check type has unit tests on hand-built STEP parts (known pass and known fail per type).
3. Official runs are complete for GLM-5.3 and DeepSeek V4.1 Flash (Qwen follows once installed; SP1
   may close with Qwen pending only if the install is the blocker, recorded in BACKLOG).
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
**Why grow to 100:** ±14 pp → ±10 pp confidence per phrasing, and more held-out concepts for the
SP3 eval. v1 results decide *which* concepts to add (e.g. harder parts rather than more plates).
**Constraint:** concept IDs are stable and the prompt file is append-only, so v1.1 is an
extension, not a rewrite. v1.1 lands before SP3 starts.

### D5. Models and attempts (decided 2026-09-25)

- **Reference models (API, user's keys, ~2,000 requests/day each):** GLM-5.3 (full, not Flash)
  and DeepSeek V4.1 Flash. They are graded only, never trained: they set the ceiling that gives
  the SP3 result a scale.
- **Baseline:** Qwen2.5-3B-Instruct base (GGUF via local llama-server), run *after* the two API
  models. Not on disk as of 2026-09-25; the user installs llama-server and downloads the GGUF when
  the API runs finish (assistant supplies the commands). This is the before-number for SP3.
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
6. ~10 of 50 concepts need fillet/chamfer/true revolve → `in_vocab: false`, reported
   **separately** (the SP2 gap), never mixed into the main pass rate. Tubes, spacers and flanges
   (stacked cylinders + cuts) count as in-vocab.

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
| `python -m simready.bench replay <run> <attempt_id>` | rebuild one attempt, verify STEP hash | no |
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
