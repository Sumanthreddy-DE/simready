# SimReady Backlog

Living list of open issues, deferred work, and known caveats. Updated each session.

---

## Triage 2026-07-19 — wave plan (current strategic context)

**Application to MecAgent NEVER sent** (`v0.4.0-apply` = prep tag; older lines below/in
Archived claiming otherwise are corrected). New goal: make the project substantial,
then apply. Repo was idle 2026-05-31 → 2026-07-18; this triage restarts it.

**Wave 1 — hygiene (DONE 2026-07-19, see Done this session):** truth sweep (3-head /
4-tool docstrings + `build_part` in system prompt + README scope/counts),
`render.py`→`png_render.py` rename, repo-root path anchoring (gen output + RAG index),
committed seed RAG index (`lookup_standard` now live on fresh clones), CI
(spec-fast job + micromamba full job), this truth pass.

**Wave 2 — substance (next sessions, in order):**
1. ~~`geometry-gen-mvp` v2~~ **DONE 2026-07-19** — dual-model E_grammar eval on NIM:
   GLM 5.2 5/5, Llama-70B 3/5 (Kimi K2.6 blocked by NIM account 404 → S3; all
   "options" keys turned out to be NIM catalog models under one `nvapi-` key, not
   separate providers). See Done this session + `docs/validation/geometry_gen_eval.md`.
2. `analyze-file-occ-hang-per-check` (S2) — demo killer; per-check precheck +
   subprocess isolation at UI entry points.
3. `defect-head-real-cad-augmentation` (S2) — hardest, highest ML value.

**Wave 3 — user-gated / decisions:**
- `finish-or-relabel-finetune` — DECIDED 2026-07-19: RUN one Colab QLoRA collaboratively
  (user + assistant), then stop investing regardless of result.
- `real-eval-set-grow` (S3) — user downloads 20–30 STEPs.
- `gmsh-calibration` (S2) — do-or-drop decision still open.
- NIM key: rotated (user confirmed 2026-07-19).
- [x] **S3 · ci-full-suite-promote** — CLOSED same day. First run: env resolved on
  linux-64, 190 passed / 2 failed / 4 skipped in 14.6 s. Both failures were
  `tests/test_copilot_ui.py` demo-step tests asserting on gitignored local data
  (`data/parametric_degraded/`, `tests/data/grabcad/`) — now skip-if-absent.
  `continue-on-error` dropped. *Opened + closed 2026-07-19.*

---

## Strategic Context (wk-3, updated 2026-05-19 — HISTORICAL, superseded by Triage 2026-07-19 above)

**Three critical demo credibility gaps (from contrarian review, end of wk-2):**
1. `lookup_standard` returns `no_index` always — third copilot tool is dead in every live demo. Fix: populate RAG corpus.
2. BRepSAGE real-CAD recall is ~0.23. UI gives no warning. Engineers get silently unreliable ML scores on real parts (>200 faces). Fix: ML confidence banner.
3. Text-only fix suggestions are useless to engineers in NX/SolidWorks. Fix: auto-heal + return STEP download.
4. `check_self_intersection` silently skips above 150 faces — most important check is invisible on production geometry. Fix: surface skip warning explicitly.

**Gaps vs JD (MecAgent ML/AI Founding Engineer):**

| JD Requirement | SimReady State | Gap |
|---|---|---|
| Geometry generation | Not built | Hard gap — analysis only |
| Tool orchestration | 3 tools, multi-turn | Thin — LLM is mostly a prose wrapper |
| GNN / embeddings | BRepSAGE trained, real-CAD recall 0.23 | Recall gap on non-parametric geometry |
| Model fine-tune pipeline | Not done yet | Clear JD requirement, wk-3 task |
| Production ML + CAD APIs | pythonocc + Streamlit demo | No deployment, no mesher hook |
| Bridge AI + real workflows | Upload → chat → colored PNG | No healed STEP output, no mesher integration |

**Wk-3 priority order (decided 2026-05-19):**
1. Fix broken demo (S1 RAG corpus + S2 self-intersection warning + S2 ML confidence banner) — ~2.5 days
2. Heal + return STEP (S2) — closes biggest ME frustration, demonstrates OCC depth — ~2 days
3. Fine-tune pipeline (exec plan days 15-17) — clear JD requirement — remaining days
4. Param-CAD generation — wk-4 stretch only (risky, deferred)

---

**Severity rubric**
- **S1** — blocker / data loss / broken demo. Fix before next ship.
- **S2** — UX gap, missing polish recruiters will notice, deferred decision.
- **S3** — tech debt, deprecations, low-impact polish, dead code.

**Conventions**
- New issue → append to correct severity section.
- Mention by short slug in commit body (e.g. "Closes: multi-turn-history").
- On close → move to **Done this session** with commit SHA.
- End of session → user sweeps **Done** → **Archived** (one-line compress).
- Last swept: **2026-07-19** (wave-1 hygiene batch: truth sweep + png_render rename + path anchoring + seed RAG index + CI + never-applied correction; wave 2/3 plan added under Triage section; suite 202/202 sr). Prior sweep 2026-05-31 (geometry-gen-mvp v1 shipped: typed DSL + trusted executor + `build_part` agent tool + 31 new tests (198/198 sr green); ADR 0001 captures DSL-over-codegen choice; v2 E_grammar runner + v3 CLI/Streamlit remain Open under the S1 stamp; full plan `docs/exec-plans/geometry-gen-mvp.md`). Prior sweep 2026-05-28 (real-CAD OOD eval shipped: closed `real-cad-eval-set` S2 — 12 McMaster STEPs probed, 7/7 false-positive on defect head, ml_agg diverges from rule_mean; `eval_real_cad.py` gained face-count precheck + spawn-subprocess hard timeout after first run hung 12h on a 58-face flange. Opened S2 `analyze-file-occ-hang-per-check`, `defect-head-real-cad-augmentation`, S3 `real-eval-set-grow`. Full record: `docs/validation/real_eval.md`). Prior sweep 2026-05-27 (honest README rewrite + self-demo wrap: closed `readme-polish`, `brepnet-naming-fix`; opened `env-example-secret-leak` S2, `grabcad-doc-stale` S3. Prior same-session retrain closed `break-circular-label`, `degraded-to-200-retrain`, `commit-tracked-weights`). Prior sweep 2026-05-26 (hiring-manager repo review → drift diagnosis + re-prioritization; opened S1 `geometry-gen-mvp` and S2 `break-circular-label` / `degraded-to-200-retrain` / `commit-tracked-weights` / `real-cad-eval-set` / `finish-or-relabel-finetune`, S3 `brepnet-naming-fix`; downgraded `grabcad-scrape-blocked`. Full record: `docs/strategy/mecagent-gap-and-drift-2026-05-26.md`). Prior sweep 2026-05-24 (wk-3 runs to completion, eval pacing flags, apply-status reconcile).

---

## Open — S1 (blocker / broken demo)

- [ ] **S1 · geometry-gen-mvp** *(v1 + v2 SHIPPED — v3 CLI remaining)* — JD bullet #1. Approach locked as a JSON DSL → trusted `build_shape(spec)` (ADR `0001-geometry-gen-dsl-over-codegen.md`), not codegen-with-sandbox. **v1 (2026-05-31): `simready/gen/{spec,build}.py` + `build_part` tool + 31 tests.** **v2 (2026-07-19): live-LLM E_grammar eval, dual-model — GLM 5.2 5/5, Llama-3.3-70B 3/5; `docs/validation/geometry_gen_eval.md`.** v3 remaining: `scripts/simready_gen.py` CLI + Streamlit gen panel. Plan: `docs/exec-plans/geometry-gen-mvp.md`. *Opened 2026-05-26. See `docs/strategy/mecagent-gap-and-drift-2026-05-26.md` rank 5.*

---

## Open — S2 (UX gap, polish, deferred decisions)

- [ ] **S2 · gen-spec-orphan-step-rule** — v2.1 follow-up from the E_grammar eval: both Llama gate failures were specs whose non-final step is never referenced downstream (primitives emitted, final `fuse`/`cut` omitted → build silently returns the lone last primitive, `occ_valid: true`). `PartSpec._check_refs` validates ref indices only. Add a Pydantic rule rejecting orphan non-final steps so the bad spec bounces back to the LLM with an actionable error inside the agent loop. Cheap, directly raises gate pass rate. *Opened 2026-07-19. See `docs/validation/geometry_gen_eval.md` §2.*
- [ ] **S2 · defect-head-real-cad-augmentation** — non-circular defect head fired on 7/7 presumed-clean real McMaster parts (median confidence > 0.95) despite 0.756 source-grouped val acc. Synthetic-only positives (`open_shell`/`sliver_face`/`self_intersection` from `generate_degraded_steps.py`) do not cover real-CAD feature distributions (NURBS density, manufactured fillets/chamfers/drafts, knurls, tight aspect ratios). Need either a small hand-labelled real-CAD positive set or a domain-randomization step in the degradation generator that varies NURBS-density / fillet-radius / draft-angle instead of fixed-magnitude geometry hacks. Without this, the held-out FP-rate (currently 100 %) is the ceiling. *Opened 2026-05-28. See `docs/validation/real_eval.md` §1.*
- [ ] **S2 · finish-or-relabel-finetune** *(user runs Colab)* — notebook never ran (0 executed cells); table columns empty. Either run the QLoRA notebook once to fill the table (upload train/val.jsonl to Drive, T4, Run All) OR relabel everything "pipeline, not result" and stop investing. *Opened 2026-05-26. Rank 3.*
- [ ] **S2 · grabcad-scrape-blocked** *(DOWNGRADED 2026-05-26)* — `download_grabcad_samples.py` is a manual stub w/ anti-bot walls. **No longer blocks day-9 recall** — recall fix is self-unblockable via the degraded generator (see `break-circular-label` + `degraded-to-200-retrain`). GrabCAD/SimJEB STEPs now only needed for `real-cad-eval-set` (held-out eval, not training). *Opened 2026-05-14 (wk-1 Q2).*
- [ ] **S2 · gmsh-calibration** *(user task)* — Run 10-15 STEPs from `tests/data/` through Gmsh at 2mm target: `gmsh part.step -3 -clmax 2 -o part.msh`. Record pass/fail + worst element quality. Correlate with SimReady score. Even rough correlation makes every score claim on the resume defensible. Requires: download Gmsh from https://gmsh.info (~100 MB, free). *Opened 2026-05-19.*

---

## Open — S3 (tech debt, deprecations, low-impact polish)

- [ ] **S3 · real-eval-set-grow** — n=7 (post-skip / post-timeout) is too small for a defensible held-out metric. Add 20–30 more real STEPs that survive the analyze guard (avoid dense flange / bearing NURBS for now, or wait for `analyze-file-occ-hang-per-check`). Use defect-head FP-rate as the primary held-out metric, not "accuracy" (no labels). *Opened 2026-05-28. See `docs/validation/real_eval.md` §4.*
- [ ] **S3 · base-vs-env-marker-split** — Two-Python-env reality (base 3.12 vs `C:\mm\sr` 3.10) keeps confusing tests. Add `pytest -m base` vs `pytest -m occ` marker split + a Makefile/PS shortcut. Less acute now that env is verified working, but the gotcha remains. *Opened 2026-05-14 (wk-1 Q5).*
- [ ] **S3 · kimi-k26-nim-404** — `moonshotai/kimi-k2.6` listed in the account's NIM `/v1/models` catalog but every invoke (incl. plain no-tools completion, 3 retries) returns `404 Function '23d4f03a-…' not found for account` — NVIDIA-side serverless provisioning gap. GLM 5.2 substituted for the v2 eval second leg (user-approved); MiniMax M3 + DeepSeek V4-flash verified invocable as further options. Re-probe k2.6 later; if it wakes, re-run `tests/test_gen_e2e.py` for a third leg. NOTE: KIMI_API_KEY in `.env` is an `nvapi-` key (build.nvidia.com), not a Moonshot key — Moonshot-direct base_url is not an option with current keys. *Opened 2026-07-19.*
- [ ] **S3 · gen-eval-latency** — E_grammar prompts ran 40–143 s wall (plan budget ~60 s; 8/10 first runs over). Build path is fine; the analyze path does demo-grade work per eval call (in-process BRepSAGE + PNG render + STEP heal + first-call torch/embedder loads). Levers: persistent build worker (v1 plan risk note), `render_image=False` slim mode for eval callers, subprocess isolation from `analyze-file-occ-hang-per-check`. *Opened 2026-07-19. See `geometry_gen_eval.md` §3.*
- [ ] **S3 · adr-backlog** — Write 2–3 ADRs under `docs/adr/` for Path C decisions that will be hard to reconstruct in 6 months: (1) OpenAI-compatible SDK over Anthropic-native (why `base_url` swap matters), (2) RAG-lite JSON + cosine over a vector DB (corpus size assumption), (3) multi-turn loop pattern w/ `AgentResponse.messages` round-trip. Useful for the interview narrative. *Opened 2026-05-17.*

---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session (2026-07-19)

- **analyze-file-occ-hang-per-check** (S2) — diagnosed + fixed. Per-stage spawn probes (`scripts/diagnose_occ_hang.py`) found the ONLY true hang: `check_self_intersection` BOPAlgo on the two 58-face B-spline flanges (under the 150-face limit; the in-check 30 s thread watchdog provably never fires — pythonocc holds the GIL, so ALL thread timeouts are inert during OCC C++). The other 2 "hangs" were eval 60 s-budget artifacts (cold torch import + 14 s load), not OCC. Fixes: freeform-face precheck (`SELF_INTERSECTION_FREEFORM_LIMIT=0`; flanges 90 s hang → 0.001 s skip) + `analyze_file_safe` killable-child wrapper (`python -m simready.pipeline_worker`; plain subprocess because mp.spawn re-runs `__main__` and breaks under Streamlit) wired into copilot tool + both Streamlit UIs + CLI. All 4 former kill parts complete in ≤ 12 s; regression `tests/test_real_eval_regression.py` (skip-if-absent). Suite 215/215 sr + 5 live deselected. Full record: `docs/validation/occ_hang_diagnosis.md`. *(SHAs `c7b20cf`, `27cd1e7`, `e63fb83`)*
- **geometry-gen-v2** (S1 part) — live-LLM E_grammar runner shipped: `tests/data/gen_prompts.jsonl` (5 archetype prompts w/ face ranges) + `tests/test_gen_e2e.py` (full CopilotAgent loop, `live_llm` mark + env-gated module skip, API key via `OPENAI_API_KEY_VAR` indirection, per-prompt records to gitignored `data/gen_eval/`). Two legs on NIM: **GLM 5.2 5/5**, **Llama-3.3-70B 3/5** (dropped-boolean failure mode; l_bracket systematic 0/2, small_feature_box stochastic 1/2). Kimi K2.6 blocked by NIM account 404 → S3 `kimi-k26-nim-404`; opened S2 `gen-spec-orphan-step-rule` + S3 `gen-eval-latency`. Full record: `docs/validation/geometry_gen_eval.md`. *(SHA: this commit)*
- **wave1-truth-sweep** — 3-head `model.py` docstring, 4-tool `tools.py` docstring, `build_part` added to `DEFAULT_SYSTEM_PROMPT` (tool list + CREATE workflow rule — the prompt never mentioned the shipped tool), README scope paragraph rewritten (gen v1 exists, live-LLM eval pending), test count 167→198. *(SHA `1d5a80a`)*
- **wave1-png-render-rename** — `simready/copilot/render.py` → `png_render.py` (+ test file), import sites updated; kills the `render`/`renderer` module-name collision. *(SHA `70b489d`)*
- **wave1-path-anchoring** — `resolve_output_dir()` in `simready/gen/build.py` + `rag.DEFAULT_INDEX_PATH` anchored to repo root via `_REPO_ROOT`; generated parts + RAG lookups no longer depend on `Path.cwd()`. +2 tests. *(SHA `f7309a6`)*
- **wave1-seed-rag-index** — committed `data/fea_docs_index_seed.json` (20 chunks, 0.18 MB, from `901851.pdf`); `get_default_index()` falls back to it when the full 24 MB local index is absent (explicit path/env never falls back). Fresh clones now get a live `lookup_standard` instead of `no_index`. Smoke: `ok`, 3 hits. +2 tests. *(SHA `1962c95`)*
- **wave1-ci** — `.github/workflows/ci.yml`: `spec-fast` (pip pydantic+pytest, `tests/test_gen_spec.py`) + `full-suite` (micromamba `environment.yml` + pip deps + `torch_geometric`, `-m "not live_llm"`, `continue-on-error` until proven on linux). `live_llm` marker registered in `pytest.ini`. Suite locally 202/202 sr green. *(SHA `29589a7`)*
- **wave1-truth-pass** — this BACKLOG restructure: never-applied correction, wave plan section, 2026-05-31 block compressed to Archived; STATE.md refreshed. *(SHA: this commit)*

---

## Done this session (2026-05-28)

- **real-cad-eval-set** (S2) — 12 real McMaster STEPs (brackets / flanges / bearings / housings) placed in `tests/data/real_eval/`. `scripts/eval_real_cad.py` hardened: cheap `count_shapes(shape, TopAbs_FACE)` precheck, `--max-faces 800` skip-list, smallest-first sort, and a spawn-subprocess + `.terminate()` hard timeout per part (`--analyze-timeout 60`) — required because the first run hung 12 h on a 58-face cast flange (OCC C++ in `analyze_file`; Python thread timeouts cannot kill it). Held-out result: 7/12 analyzed, 1 skipped (854 f), 4 timeout-killed (flange / bearing NURBS pathology); **7/7 analyzed parts false-positive on the defect head** (median conf > 0.95); `rule_face_mean = 0.0` on every part but `ml_aggregate ∈ [0.30, 0.59]` — quantifies the OOD gap previously inferred from the leaky synthetic val. Full interpretation: `docs/validation/real_eval.md`. *(SHA: `849449a`)*

## Done this session (2026-05-26 → 27)

- **env-example-secret-leak** (S2) — replaced live `nvapi-` key in `.env.example:6` with `<your-api-key>` placeholder (regex rewrite, secret never echoed). **NOTE: key remains in git history → user must rotate it on the NVIDIA dashboard; this commit does not rewrite history.** *(SHA: `90b90cb`)*
- **evaluate-py-defect-metric** (S2) — `scripts/evaluate.py` now passes `batch=batch.batch` (graph-level defect head pools per graph) and reports defect accuracy + per-class acc when the dataset has `graph_label` (guarded for label-less sets). Parity with `train.py`. Smoke: combined 1100-set `defect_acc=0.739` (clean 0.84 / open_shell 0.565 / sliver 1.0 / self_int 0.40). *(SHA: `90b90cb`)*
- **grabcad-doc-stale** (S3) — refreshed `docs/validation/grabcad.md` to the 3-head leakage-free checkpoint (`a29e150`): banner + model-dependent cells (Overall 37.5/36.6/61.0, ML agg 0.37-0.45, latency) from `weights/metrics.json`; rule/geometry cells unchanged; honest recall framing (0.487 leakage-free vs leaky 0.870); dropped Combined-mean column. *(SHA: `90b90cb`)*

- **break-circular-label** (S2) — added a non-circular graph-level **defect-classification head** trained on injected `defect_tags` (not the rule layer). `auto_label.py` now reads `.tags.json` → `graph_label`; `model.py` gains `defect_head` (global-mean-pool → 4-class); `dataset.py` loads `graph_label`; `train.py` adds CE loss + per-class defect accuracy. Wired into `brepnet.py` inference (`predicted_defect`/`defect_confidence`/`defect_probs`). *(SHA: `a29e150`)*
- **degraded-to-200-retrain** (S2) — generated 600 degraded (200 each: open_shell/sliver_face/self_intersection), labeled 1100 combined, retrained on a **source-grouped (leakage-free) split**. Headline non-circular metric: **defect acc 0.756** (n_val=205); per-class clean 0.87 / sliver 1.0 / open_shell 0.571 / self_int 0.371. Old circular head on the honest split drops to acc 0.848 / recall 0.487 (was 0.975/0.870 on the leaky random split). Results: `docs/validation/defect_classifier.md`. *(SHA: `a29e150`)*
- **commit-tracked-weights** (S2) — `.gitignore` now tracks `weights/metrics.json` + `eval_fixtures.json` (+ existing brepnet.pt/meta negations); wrote slim honest `weights/metrics.json`; committed the checkpoint so a cloner gets a model + numbers. *(SHA: `a29e150`)*
- **167/167 tests green** (sr env; +7 in `tests/test_defect_head.py`). No regressions across the touched files.
- **readme-polish** (S2) + **brepnet-naming-fix** (S3) — full honest README rewrite for the recruiter lens: leads with capabilities (agent / GNN / eval discipline), 3-head model described accurately, **BRepSAGE/GraphSAGE naming fixed** (no more "BRepNet"), circular-refinement vs non-circular-defect caveat surfaced, Results tables w/ provenance + leakage-free-split framing, Mermaid arch diagram, scope=analysis-only, latency, test count 160→**167**. Changed every claim the code didn't support. *(SHA: this session's docs commit — see `git log`.)*
- **self-demo / repo-not-empty** — refreshed `weights/eval_fixtures.json` against the new 3-head checkpoint (acc 0.725 / recall 0.692, up from 0.23); `docs/sample_output/smoke_box.{json,html}` (checkpoint-backed CLI bundle, zero-setup proof); `docs/img/streamlit-analysis.png` + reproducible `scripts/ui_screenshots.py` (Playwright driver). Closes the "weights + metrics gitignored → clone is empty" gap (strategy doc pointer #1). *(SHA: docs commit.)*

## Done (2026-05-24)

- **trace-gen-restart** (S2) — resumed 1368 → **1455 traces** (8B, NIM; 45 lost to 429s, resume-safe, exit 0). Ample for 3B QLoRA.
- **gold-eval-incomplete** (S2) — full **70B gold baseline n=50, errors=0** (`tool_call_exact 0.760`, `partial 0.920`, `tool_order 0.780`, `format 0.780`, `theme 0.678`). Added `--request-delay`/`--max-retries`/`--initial-backoff` to `eval_finetune.py` to survive NIM 429s; purged 3 stale partial gold blocks from `finetune_results.md`, filled the summary table's Llama-70B column.
- **brepbndlib-deprecation** (S3) — `brepbndlib_Add` → `brepbndlib.Add` static in `scripts/generate_degraded_steps.py`; verified no DeprecationWarning under `-W error`.
- **chore** — `logs/` added to `.gitignore`; refreshed `path-c-4week.md` (wk-3 run ticks, day-15/18-run-1 done) and `project_simready.md` memory; **reconciled apply status** — confirmed applied 2026-05-18 (`v0.4.0-apply`), corrected a mid-session mis-conclusion that it hadn't been sent.
- *(SHA: this session's commit — see `git log`.)*

---

## Archived (older sweeps, compressed)

- **2026-05-31 · geometry-gen-mvp v1** — `fa581f0`. Typed Pydantic DSL (`simready/gen/spec.py`) + trusted executor w/ spawn-subprocess hang protection (`simready/gen/build.py`) + `build_part` tool in `simready/copilot/tools.py`; ADR 0001 locks DSL-over-codegen; defect head advisory-only; 31 new tests, 198/198 sr. v2 (live-LLM E_grammar) + v3 (CLI/Streamlit) remain Open under the S1 stamp.

- **2026-05-21 · wk-3 days 15-19 scaffolding** — `4e74ff0` (7 files / 1670 ins): `synth_tool_traces.py`, `prep_finetune_dataset.py`, `finetune_copilot.ipynb` (Colab T4 QLoRA on Qwen2.5-3B), `eval_finetune.py` (6 metrics), `finetune_results.md` template, gitignore `data/fine_tune/`. `trace-format-rot` closed by design. `project_api-key-todo` memory opened. 160/160 tests, no prod-code changes.
- **2026-05-19→20 · contrarian-review demo fixes** — `71ccacf` + `dd45eef`. Closed the 4 demo-credibility gaps: `fea-rag-corpus-empty` (rag.py API-rename + OpenBLAS-crash fixes, index rebuilt), `heal-return-step` (auto ShapeFix/ShapeUpgrade → healed-STEP download), `ml-confidence-banner` (unreliable-score banner when `face_count>200`), `self-intersection-skip-warning` (explicit "skipped N faces" finding above 150).

- **2026-05-18 · apply-timeline-tight** — CORRECTED 2026-07-19: application was NEVER sent; `v0.4.0-apply` (`34a93e7`) tagged the prep snapshot only. (The 2026-05-24 "reconciliation" that concluded it was sent is also wrong.) Apply deferred until project substantial — user decision 2026-07-19.
- **2026-05-13 · Phase 2A bug-fix sweep** (5 items) — see commits `b689b71`..`ec4f33a`. SelfIntersection false-positive, face index 0/1 mismatch, ML weights-loaded lying, GrabCAD manifold hang guard, rule_face_count rename.
- **2026-05-14 · Path C wk-1 ship** (6 days of work) — see commits `7212e52`..`d8fcc1f`. Copilot stack, 3 tools, RAG-lite, multi-turn loop, terminal UI, degraded-STEP generator.
- **2026-05-16 · Wk-1 Q1/Q6/Q8 resolved** — light real-LLM smoke (`563ab6c`) validated LLM loop end-to-end on NIM Llama. No tool_choice gotcha. Slim summary respected. Day-10 sub-decisions D1=b, D2=a, D3=mock-then-smoke locked.
- **2026-05-17 · Path C wk-2 day 10 ship** (4 items) — `056a746`..`69539ef`. Streamlit chat UI + dropdown dedupe, sidebar score badge, multi-turn history via `AgentResponse.messages` round-trip, Verdict-with-score format. Real-LLM smoke gained a turn-2 follow-up (10/10 NIM checks).
- **2026-05-17 · Path C wk-2 day 11 ship** (7 items) — `636d140`..`c3df6c0`. Static colored-face PNG via OCC tess + PIL painter's-algo (replaces deferred pyvista; matplotlib also broken in sr OCC env on Win); `check_thin_solid` detector + drop broken `zero_length_edge` synth; STEP file uploader + 5MB warn; typed `_classify_agent_exception` chips (RateLimit/Timeout/ConnError/Auth/BadRequest); `[synth]`/`[real]` dropdown grouping; per-session JSON persist under `data/copilot_sessions/`. 160/160 tests in sr env (+15 from session start).
- **2026-05-17 · Memory + archive cleanup sweep** — see commits `32fd451..5a917d4`. Phase 1/2/3 plans + designs + brainstorming + deep-research + stale memory + old `~/.claude/session-data/` .tmp files moved into `Archive/{phase-1,phase-2,phase-3,brainstorming,memory,sessions}/` (move-only, never deleted). Added `CONTEXT.md` (FEA/BRep/copilot domain glossary + avoid-terms + example dialogue) and `SESSION-END.md` (7-step manual end-of-session checklist). Memory dir refreshed: `project_simready.md` rewritten to current Path-C-wk2-day11 state, `project_simready-roadmap.md` collapsed to pointer-only (real plan lives at `docs/exec-plans/path-c-4week.md`), `project_open-questions-wk2.md` moved to `Archive/memory/`. Global `~/.claude/CLAUDE.md` extended w/ BACKLOG/SESSION-END/Archive harness rules, memory-vs-repo duplication rule, /save-session-path gotcha, and two-trigger new-project harness check (session-start + memory-folder creation). `~/.claude/templates/new-project/` seeded w/ BACKLOG.md + SESSION-END.md + Archive/README.md so `new-project-init.sh` scaffolds them. Opened: `adr-backlog` (S3, write 2-3 ADRs for Path C decisions, defer wk-3).
