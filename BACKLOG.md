# SimReady Backlog

Living list of open issues, deferred work, and known caveats. Updated each session.

---

## Strategic Context (wk-3, updated 2026-05-19)

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
- Last swept: **2026-05-31** (geometry-gen-mvp v1 shipped: typed DSL + trusted executor + `build_part` agent tool + 31 new tests (198/198 sr green); ADR 0001 captures DSL-over-codegen choice; v2 E_grammar runner + v3 CLI/Streamlit remain Open under the S1 stamp; full plan `docs/exec-plans/geometry-gen-mvp.md`). Prior sweep 2026-05-28 (real-CAD OOD eval shipped: closed `real-cad-eval-set` S2 — 12 McMaster STEPs probed, 7/7 false-positive on defect head, ml_agg diverges from rule_mean; `eval_real_cad.py` gained face-count precheck + spawn-subprocess hard timeout after first run hung 12h on a 58-face flange. Opened S2 `analyze-file-occ-hang-per-check`, `defect-head-real-cad-augmentation`, S3 `real-eval-set-grow`. Full record: `docs/validation/real_eval.md`). Prior sweep 2026-05-27 (honest README rewrite + self-demo wrap: closed `readme-polish`, `brepnet-naming-fix`; opened `env-example-secret-leak` S2, `grabcad-doc-stale` S3. Prior same-session retrain closed `break-circular-label`, `degraded-to-200-retrain`, `commit-tracked-weights`). Prior sweep 2026-05-26 (hiring-manager repo review → drift diagnosis + re-prioritization; opened S1 `geometry-gen-mvp` and S2 `break-circular-label` / `degraded-to-200-retrain` / `commit-tracked-weights` / `real-cad-eval-set` / `finish-or-relabel-finetune`, S3 `brepnet-naming-fix`; downgraded `grabcad-scrape-blocked`. Full record: `docs/strategy/mecagent-gap-and-drift-2026-05-26.md`). Prior sweep 2026-05-24 (wk-3 runs to completion, eval pacing flags, apply-status reconcile).

---

## Open — S1 (blocker / broken demo)

- [ ] **S1 · geometry-gen-mvp** *(v1 SHIPPED 2026-05-31 — see Done; v2 + v3 remaining)* — JD bullet #1. Approach locked as a JSON DSL → trusted `build_shape(spec)` (ADR `0001-geometry-gen-dsl-over-codegen.md`), not codegen-with-sandbox. **v1 (this session): `simready/gen/{spec,build}.py` + `build_part` tool in `simready/copilot/tools.py` + 31 tests.** v2 remaining: `tests/data/gen_prompts.jsonl` (5 E_grammar prompts) + `tests/test_gen_e2e.py` live-LLM runner (mark `live_llm`, skipped in CI). v3 remaining: `scripts/simready_gen.py` CLI + Streamlit gen panel. Plan: `docs/exec-plans/geometry-gen-mvp.md`. *Opened 2026-05-26. See `docs/strategy/mecagent-gap-and-drift-2026-05-26.md` rank 5.*

---

## Open — S2 (UX gap, polish, deferred decisions)

- [ ] **S2 · analyze-file-occ-hang-per-check** — `analyze_file` hung on 4/12 industrial parts at 58–578 faces during the real-CAD eval (both flanges, 1 ball-bearing-w/-flange, 1 T-slot bracket). Pre-existing `check_self_intersection` face-count guard + 30 s thread watchdog covers one check; the hang is in a different one (suspect: per-face curvature / sharp-edge / open-shell). Python thread timeouts do not stop the underlying OCC C++ (`lessons_pythonocc-gotchas.md`), so the Streamlit UI / copilot can also freeze on a real STEP upload. Identify the offending check, add a face-count / topology-density precheck per check, and prefer subprocess isolation at the UI entry points. The `eval_real_cad.py` 60 s spawn-subprocess `terminate()` is a script-level workaround, not a fix. *Opened 2026-05-28. See `docs/validation/real_eval.md` §3.*
- [ ] **S2 · defect-head-real-cad-augmentation** — non-circular defect head fired on 7/7 presumed-clean real McMaster parts (median confidence > 0.95) despite 0.756 source-grouped val acc. Synthetic-only positives (`open_shell`/`sliver_face`/`self_intersection` from `generate_degraded_steps.py`) do not cover real-CAD feature distributions (NURBS density, manufactured fillets/chamfers/drafts, knurls, tight aspect ratios). Need either a small hand-labelled real-CAD positive set or a domain-randomization step in the degradation generator that varies NURBS-density / fillet-radius / draft-angle instead of fixed-magnitude geometry hacks. Without this, the held-out FP-rate (currently 100 %) is the ceiling. *Opened 2026-05-28. See `docs/validation/real_eval.md` §1.*
- [ ] **S2 · finish-or-relabel-finetune** *(user runs Colab)* — notebook never ran (0 executed cells); table columns empty. Either run the QLoRA notebook once to fill the table (upload train/val.jsonl to Drive, T4, Run All) OR relabel everything "pipeline, not result" and stop investing. *Opened 2026-05-26. Rank 3.*
- [ ] **S2 · grabcad-scrape-blocked** *(DOWNGRADED 2026-05-26)* — `download_grabcad_samples.py` is a manual stub w/ anti-bot walls. **No longer blocks day-9 recall** — recall fix is self-unblockable via the degraded generator (see `break-circular-label` + `degraded-to-200-retrain`). GrabCAD/SimJEB STEPs now only needed for `real-cad-eval-set` (held-out eval, not training). *Opened 2026-05-14 (wk-1 Q2).*
- [ ] **S2 · gmsh-calibration** *(user task)* — Run 10-15 STEPs from `tests/data/` through Gmsh at 2mm target: `gmsh part.step -3 -clmax 2 -o part.msh`. Record pass/fail + worst element quality. Correlate with SimReady score. Even rough correlation makes every score claim on the resume defensible. Requires: download Gmsh from https://gmsh.info (~100 MB, free). *Opened 2026-05-19.*

---

## Open — S3 (tech debt, deprecations, low-impact polish)

- [ ] **S3 · real-eval-set-grow** — n=7 (post-skip / post-timeout) is too small for a defensible held-out metric. Add 20–30 more real STEPs that survive the analyze guard (avoid dense flange / bearing NURBS for now, or wait for `analyze-file-occ-hang-per-check`). Use defect-head FP-rate as the primary held-out metric, not "accuracy" (no labels). *Opened 2026-05-28. See `docs/validation/real_eval.md` §4.*
- [ ] **S3 · base-vs-env-marker-split** — Two-Python-env reality (base 3.12 vs `C:\mm\sr` 3.10) keeps confusing tests. Add `pytest -m base` vs `pytest -m occ` marker split + a Makefile/PS shortcut. Less acute now that env is verified working, but the gotcha remains. *Opened 2026-05-14 (wk-1 Q5).*
- [ ] **S3 · adr-backlog** — Write 2–3 ADRs under `docs/adr/` for Path C decisions that will be hard to reconstruct in 6 months: (1) OpenAI-compatible SDK over Anthropic-native (why `base_url` swap matters), (2) RAG-lite JSON + cosine over a vector DB (corpus size assumption), (3) multi-turn loop pattern w/ `AgentResponse.messages` round-trip. Useful for the interview narrative. *Opened 2026-05-17.*

---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session (2026-05-31)

- **geometry-gen-mvp v1** (S1, commit-1 of 3) — closed the JD-bullet-#1 gap with a typed DSL + trusted executor instead of codegen-with-sandbox (ADR `docs/adr/0001-geometry-gen-dsl-over-codegen.md`). Shipped: `simready/gen/spec.py` (Pydantic `PartSpec`/`BoxOp`/`CylOp`/`FuseOp`/`CutOp`, schema + cross-step ref validation), `simready/gen/build.py` (in-process `build_shape(spec)` + spawn-subprocess `build_part(...)` w/ `Process.terminate()` after `--build-timeout` default 15 s — same hang-protection pattern as `scripts/eval_real_cad.py`, motivated by the OCC C++ lesson), and the `build_part` tool wired into `simready/copilot/tools.py` (schema + dispatch). Defect head wired as advisory not gate (per `real_eval.md` §1 it FPs at 100 % on real CAD). **31 new tests** (17 spec + 11 build + 3 copilot-tools); full suite **198/198 sr green**. Plan: `docs/exec-plans/geometry-gen-mvp.md`. v2 (E_grammar live runner) + v3 (CLI + Streamlit panel) remain Open under the S1 stamp. *(SHA: this session's commit — see `git log`.)*

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

- **2026-05-21 · wk-3 days 15-19 scaffolding** — `4e74ff0` (7 files / 1670 ins): `synth_tool_traces.py`, `prep_finetune_dataset.py`, `finetune_copilot.ipynb` (Colab T4 QLoRA on Qwen2.5-3B), `eval_finetune.py` (6 metrics), `finetune_results.md` template, gitignore `data/fine_tune/`. `trace-format-rot` closed by design. `project_api-key-todo` memory opened. 160/160 tests, no prod-code changes.
- **2026-05-19→20 · contrarian-review demo fixes** — `71ccacf` + `dd45eef`. Closed the 4 demo-credibility gaps: `fea-rag-corpus-empty` (rag.py API-rename + OpenBLAS-crash fixes, index rebuilt), `heal-return-step` (auto ShapeFix/ShapeUpgrade → healed-STEP download), `ml-confidence-banner` (unreliable-score banner when `face_count>200`), `self-intersection-skip-warning` (explicit "skipped N faces" finding above 150).

- **2026-05-18 · apply-timeline-tight** — Application sent to MecAgent at `v0.4.0-apply` (`34a93e7`). Item obsolete.
- **2026-05-13 · Phase 2A bug-fix sweep** (5 items) — see commits `b689b71`..`ec4f33a`. SelfIntersection false-positive, face index 0/1 mismatch, ML weights-loaded lying, GrabCAD manifold hang guard, rule_face_count rename.
- **2026-05-14 · Path C wk-1 ship** (6 days of work) — see commits `7212e52`..`d8fcc1f`. Copilot stack, 3 tools, RAG-lite, multi-turn loop, terminal UI, degraded-STEP generator.
- **2026-05-16 · Wk-1 Q1/Q6/Q8 resolved** — light real-LLM smoke (`563ab6c`) validated LLM loop end-to-end on NIM Llama. No tool_choice gotcha. Slim summary respected. Day-10 sub-decisions D1=b, D2=a, D3=mock-then-smoke locked.
- **2026-05-17 · Path C wk-2 day 10 ship** (4 items) — `056a746`..`69539ef`. Streamlit chat UI + dropdown dedupe, sidebar score badge, multi-turn history via `AgentResponse.messages` round-trip, Verdict-with-score format. Real-LLM smoke gained a turn-2 follow-up (10/10 NIM checks).
- **2026-05-17 · Path C wk-2 day 11 ship** (7 items) — `636d140`..`c3df6c0`. Static colored-face PNG via OCC tess + PIL painter's-algo (replaces deferred pyvista; matplotlib also broken in sr OCC env on Win); `check_thin_solid` detector + drop broken `zero_length_edge` synth; STEP file uploader + 5MB warn; typed `_classify_agent_exception` chips (RateLimit/Timeout/ConnError/Auth/BadRequest); `[synth]`/`[real]` dropdown grouping; per-session JSON persist under `data/copilot_sessions/`. 160/160 tests in sr env (+15 from session start).
- **2026-05-17 · Memory + archive cleanup sweep** — see commits `32fd451..5a917d4`. Phase 1/2/3 plans + designs + brainstorming + deep-research + stale memory + old `~/.claude/session-data/` .tmp files moved into `Archive/{phase-1,phase-2,phase-3,brainstorming,memory,sessions}/` (move-only, never deleted). Added `CONTEXT.md` (FEA/BRep/copilot domain glossary + avoid-terms + example dialogue) and `SESSION-END.md` (7-step manual end-of-session checklist). Memory dir refreshed: `project_simready.md` rewritten to current Path-C-wk2-day11 state, `project_simready-roadmap.md` collapsed to pointer-only (real plan lives at `docs/exec-plans/path-c-4week.md`), `project_open-questions-wk2.md` moved to `Archive/memory/`. Global `~/.claude/CLAUDE.md` extended w/ BACKLOG/SESSION-END/Archive harness rules, memory-vs-repo duplication rule, /save-session-path gotcha, and two-trigger new-project harness check (session-start + memory-folder creation). `~/.claude/templates/new-project/` seeded w/ BACKLOG.md + SESSION-END.md + Archive/README.md so `new-project-init.sh` scaffolds them. Opened: `adr-backlog` (S3, write 2-3 ADRs for Path C decisions, defer wk-3).
