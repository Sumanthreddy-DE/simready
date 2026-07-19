# Geometry-Gen v2 — Live-LLM E_grammar Eval

**Date:** 2026-07-19
**Harness:** `tests/test_gen_e2e.py` over `tests/data/gen_prompts.jsonl` (5 hand-written prompts, one per `generate_parametric_steps.py` archetype). Full `CopilotAgent` loop, all four tools, `max_turns=6`, default system prompt (unchanged — `build_part` workflow rule shipped in wave 1, `1d5a80a`).
**Ship gate (per prompt):** LLM makes a successful `build_part` call → final STEP exists on disk **+** `occ_valid` **+** face count inside the prompt's `expect.faces` range. Defect-head output is advisory only (per `real_eval.md` §1 — 100 % FP on real CAD; it never gates).
**Endpoint:** both legs ran against NVIDIA NIM (`https://integrate.api.nvidia.com/v1`), model swapped via `OPENAI_MODEL` env only, zero code changes. Raw per-prompt records: `data/gen_eval/*.jsonl` (gitignored; this doc is canonical).

**Planned second leg was Kimi K2.6 — it could not run.** `moonshotai/kimi-k2.6` appears in the account's `/v1/models` catalog but every invocation (plain completion, no tools, 3 retries) returns `404 "Function '23d4f03a-…': Not found for account …"` — a NIM-side serverless-provisioning gap for this account, not a client bug. The Moonshot-direct endpoints were never an option (the available key is an `nvapi-` key from build.nvidia.com). GLM 5.2 (`z-ai/glm-5.2`) was substituted with user approval; MiniMax M3 and DeepSeek V4-flash also probed as invocable fallbacks.

## Results

Pass = ✅, fail = ❌. `turns` = agent loop iterations (LLM round-trips); every run made exactly 1 `build_part` + 1 `analyze_geometry` call.

### Leg 1 — `meta/llama-3.3-70b-instruct` (NIM) — **3/5**

| Prompt | Turns | Final spec (steps) | occ_valid | Faces (expect) | Wall s | Gate |
|---|--:|---|---|---|--:|---|
| normal_box | 3 | `box(60,40,30)` | ✅ | 6 ([6,6]) | 95.6 | ✅ |
| thin_plate | 3 | `box(100,80,0.5)` | ✅ | 6 ([6,6]) | 39.8 | ✅ |
| l_bracket | 3 | `box(60,60,10)`, `box(10,60,50,at[0,-30,10])` — **no `fuse`** | ✅ | 6 ([10,18]) | 80.7 | ❌ |
| bracket_with_hole | 4 | `box(80,60,10)`, `cyl(5,10,at[40,30,0])`, `cut(0,1)` | ✅ | 7 ([6,10]) | 113.6 | ✅ |
| small_feature_box | 5 | `box(60,60,30)`, `cyl(0.5,30,at[30,30,0])` — **no `cut`** | ✅ | 3 ([6,10]) | 142.9 | ❌ |

Repeatability probe (the 2 failures re-run once): `l_bracket` **failed again** with the identical omit-`fuse` spec (systematic, 0/2); `small_feature_box` **passed** on retry with the full 3-step spec, 7 faces (stochastic, 1/2). Best-of-two: 4/5.

### Leg 2 — `z-ai/glm-5.2` (NIM) — **5/5**

| Prompt | Turns | Final spec (steps) | occ_valid | Faces (expect) | Wall s | Gate |
|---|--:|---|---|---|--:|---|
| normal_box | 4 | `box(60,40,30)` | ✅ | 6 ([6,6]) | 74.4 | ✅ |
| thin_plate | 4 | `box(100,80,0.5)` | ✅ | 6 ([6,6]) | 113.6 | ✅ |
| l_bracket | 4 | `box(60,60,10)`, `box(60,10,50,at[0,0,10])`, `fuse(0,1)` | ✅ | 11 ([10,18]) | 101.2 | ✅ |
| bracket_with_hole | 4 | `box(80,60,10)`, `cyl(5,10,at[40,30,0])`, `cut(0,1)` | ✅ | 7 ([6,10]) | 87.4 | ✅ |
| small_feature_box | 4 | `box(60,60,30)`, `cyl(0.5,30,at[30,30,0])`, `cut(0,1)` | ✅ | 7 ([6,10]) | 81.1 | ✅ |

## Interpretation

### 1. The generate → analyze loop works end-to-end — and the model matters

This is the first time a live model has driven the full v1 machinery: natural-language prompt → `build_part` tool call with a schema-valid `PartSpec` → subprocess-isolated OCC build → STEP on disk → self-initiated `analyze_geometry` on the returned path → verdict citing real tool numbers. Both models followed the system-prompt workflow rule (build first, then analyze) in **every single run** — 12/12 runs made exactly one build call and one analyze call, no prompting beyond the shipped default. Dimension extraction was flawless across both models: every spec carried the exact mm values from the prompt, and GLM's L-bracket spec reproduced the `gen_l_bracket` archetype construction (base + upright at `[0,0,10]` + fuse) almost verbatim. GLM 5.2 passed the locked gate 5/5; Llama-3.3-70B passed 3/5. The eval swaps models with two env vars and no code — which was the point of the OpenAI-compat architecture — but honesty requires noting both legs hit the *same* NIM endpoint: this is **model-swap** evidence, not cross-provider-endpoint evidence. The intended cross-provider leg (Kimi K2.6) is blocked by an NVIDIA-side account provisioning gap (persistent 404 on an account-listed model), recorded above.

### 2. The dominant failure mode is a dropped boolean, and it fails *silently green*

Both Llama failures have the same shape: the model emits the correct primitives, then **omits the final `fuse`/`cut` step**. Under the DSL's last-step-is-the-part semantics, the build then returns just the lone second primitive — `occ_valid: true`, STEP written, no error anywhere — and only the face-count gate exposes that the part is wrong (6 faces of a bare box instead of an L-bracket; 3 faces of a bare 1 mm pin instead of a drilled block). The refine loop did not save it: Llama saw `faces: 6` in the analyze result and wrote a confident verdict about the wrong part; on the small_feature_box first run it gave up claiming "the provided functions are insufficient", and on its *passing* bracket_with_hole run it still hallucinated that "analyze_geometry and suggest_fixes returned errors" after both succeeded. l_bracket omission was systematic (2/2 identical specs); small_feature_box was stochastic (passed on retry). The cheap structural fix is a **spec-level orphan-step rule**: `PartSpec` currently validates ref indices only (`simready/gen/spec.py::_check_refs`), so a spec where a non-final step is never referenced downstream validates cleanly. Rejecting orphan steps at the Pydantic boundary would have bounced both bad specs back to the LLM with an actionable error inside the same agent loop — a v2.1 follow-up, deliberately not implemented in this session.

### 3. Latency is 40–143 s per prompt — over the 60 s regression line on 8 of 10 gate runs

The exec plan budgeted ~60 s wall per prompt and flagged anything above as a regression: 8/10 first-run prompts exceeded it (Llama mean ≈ 95 s, GLM mean ≈ 92 s; range 39.8–142.9 s). The stack-up per prompt is: 2–4 NIM round-trips against a long system prompt, a spawn-subprocess OCC build (~5–10 s, by design per the hang-protection decision), and — the biggest avoidable chunk — a full in-process `analyze_file` with BRepSAGE inference, PNG render, and best-effort STEP heal on a 6-face box, including first-call torch + sentence-transformers model loads inside the test process. None of this is new regression in the build path; it is the analyze path doing demo-grade work in an eval loop. Fixes, in leverage order: a persistent build worker (already noted in the v1 plan risks), a `render_image=False` / slim mode for eval callers of `analyze_geometry`, and the open `analyze-file-occ-hang-per-check` S2 item whose subprocess isolation would also amortize model loads. Flagged here per the plan; not gated on.
