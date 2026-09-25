# SP1: Checker-scored text-to-CAD benchmark + harness (design)

**Status:** active
**Last verified:** 2026-09-25
**Stage:** design in progress (brainstorming). Decisions below are locked; open questions at the end.

**Context:** First of three sub-projects (SP1 benchmark + harness → SP2 generation vocabulary v2 →
SP3 post-training with checker reward). Informed by `earthtojake/text-to-cad` (MIT: validity
checks, repair-loop failure taxonomy) and `Adam-CAD/CADAM` (GPL-3: nothing copied; prompt style
only). Neither repo scores its output; this benchmark is the piece they lack.

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

## Open questions (to decide next)

- Constraint schema and tolerance conventions.
- Where the code lives (new package directory needs explicit approval).
- How concepts needing ops outside the 4-op DSL (revolve, fillet) are tagged and reported.
