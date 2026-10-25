# STATE — SimReady

<!-- Machine-maintained by save-session Step 6b. Hand-edit 2026-07-19 authorized by user (triage session). -->

Status: active
Last touched: 2026-10-25

## What
MecAgent ML/AI Founding Engineer portfolio project: AI-assisted FEA pre-processing. LLM copilot over B-rep analysis pipeline + BRepSAGE (3-head GraphSAGE) defect classifier + geometry-generation DSL (`build_part` tool). **APPLICATION SENT 2026-10-05 (user confirmed).** Open follow-up work = the `apply-*` items in BACKLOG S1/S2, GenCAD VLM track first. History: `v0.4.0-apply` (2026-05) was prep only, not a send. Strategy doc: docs/strategy/mecagent-gap-and-drift-2026-05-26.md; wave plan: BACKLOG.md "Triage 2026-07-19".

## Done
- Full pipeline + copilot, 202 tests green in sr env
- Real-CAD OOD eval on 12 McMaster STEPs → docs/validation/real_eval.md (quantified the OOD gap)
- geometry-gen-mvp v1: typed Pydantic DSL + trusted executor (ADR 0001) + build_part tool
- Honest README rewrite + self-demo artifacts
- **Wave-1 hygiene (2026-07-19, `1d5a80a..`):** truth sweep (build_part now in system prompt), render→png_render rename, repo-root path anchoring, committed seed RAG index (lookup_standard live on clones), CI (spec-fast + micromamba full job), BACKLOG never-applied correction
- **geometry-gen v2 (2026-07-19):** live-LLM E_grammar eval, dual-model on NIM — GLM 5.2 **5/5**, Llama-3.3-70B **3/5** (dropped-boolean failure mode). Kimi K2.6 blocked by NIM account 404 (S3). docs/validation/geometry_gen_eval.md
- **OCC-hang guard (2026-07-19):** diagnosed (BOPAlgo on B-spline flanges; thread watchdogs GIL-inert) + fixed (freeform precheck + `analyze_file_safe` killable child at all entry points). Real-eval coverage 7/12 → 11/12, 0 errors. docs/validation/occ_hang_diagnosis.md
- **defect-head augmentation attempt (2026-07-19):** combined-v2 retrain (2272 graphs w/ fillet/chamfer randomization) — val 0.686 harder-val, fixtures refinement 0.853/0.895, but **real-CAD FP still 11/11**. Honest negative; synthetic-augmentation lever exhausted. Item stays Open w/ findings.
- **gen v2.1 (2026-07-19, wave 3):** orphan-step Pydantic rule + rule stated in `build_part` tool description + `parallel_tool_calls=False` (NIM Llama template 500s on multi-tool_call history) — Llama leg **3/5 → 5/5** clean re-run. Attribution honest: description fixed emissions, validator = backstop. geometry_gen_eval.md v2.1. Committed `8304c1b` (2026-07-20; had sat uncommitted). Suite 227 sr.
- **Wave-3 decisions + apply package (2026-07-20, `d88ec31..d94cc25`):** APPLY = GO (README wave-2/3 refresh + apply narrative doc); gmsh deferred to interview prep; ADRs 0002-0004 (adr-backlog closed); QLoRA notebook live-debugged (4 fix commits) + GGUF/llama-server eval recipe.
- **2026-09-23..27 repositioning session (`9ece3e8..b51f6af`):** QLoRA adapter recovered (byte-identical to checkpoint-180), loss 0.697→0.107 / val 0.150 recorded; README + finetune_results truth fixes; plan files closed out to `completed/`; JDs saved local-only (`docs/jobs/`, gitignored — public repo); studied text-to-cad (MIT) + CADAM (GPL-3), neither scores output; SP1 design spec D1–D7 + §1–§3 written.
- **2026-10-05..07 GenCAD track (branch `gencad`, `6ae290e..ea4bdf3`):** Qwen2.5-VL-3B on MecAgent's GenCAD-Code test, dataset `hundred_subset`: untuned VSR 0/100 (answers in JSON) → QLoRA (6k ex, 1 epoch, free T4) VSR 0.88, IoU_best 0.256 (MecAgent surface-voxel metric) / 0.563 filled; all 12 failures runaway generations; checker bridge on 88 generated + 88 reference parts (model-introduced: 1 invalid solid, 3 self-intersections). Record `docs/validation/gencad_eval.md`, results `docs/validation/gencad/`, scripts `scripts/gencad_*.py`.
- **2026-10-05:** application sent; follow-up commitments filed as BACKLOG `apply-*` items (`11fb5e1`, `3822d3b`), GenCAD promoted to S1 ahead of SP1.
- **2026-10-04..05 session:** SP1 spec reviewed (`c99ace2`) + 13-task plan (`e49abd5`), Tasks 1–2 (`84e7820`, `45a43f5`); gen eval v2.2 on Vultr — GLM 5.3 5/5, DeepSeek V4.1 Flash 5/5, Llama retired on NIM (`b3f7cc4`, `b30e212`, `b9ec82e`); D Labs excluded (corrupts tool calls); copilot default → Vultr glm-5.3.
- **2026-10-13 README + branch sync:** README on `main` rewritten (`58fe9b5`): Direction section (checker as metric, later reward), GenCAD results, roadmap Done/Now/Next(SP1-SP3)/Later. `main` merged into `sp1-bench` (`8ec3613`, `cfbbda4`), `gencad` fast-forwarded; state files identical on all branches. Closed `apply-readme-on-main`, `apply-readme-cv-alignment`, `branch-state-divergence`, `gencad-results-duplicate` (local download archived).
- **2026-10-24/25 audit remediation integrated (`f1b6e31`, `1433900`):** CLI failure reporting is truthful; 14 GenCAD/local files preserved with matching destination hashes and sources retained. README setup/demo/results remediated; committed UI fixtures work without local caches; deterministic build→analyze verified in browser and clean checkout. Current combined-v2 fixture inference reproduced .853/.920/.895. Strengthened generation gate passed 5/5 on Vultr GLM 5.3 (175.06 s), with mechanics and exact final-artifact analysis. Full suite 255 passed / 5 deselected. No archive moves or worktree retirement.
- **2026-10-25 defect-head real-clean experiment (`experiment/defect-real-clean`, `f39fe93`):** strict inspection admitted only 2/12 real parts. One-fit/one-holdout defect-head-only candidate left holdout FP 1/1 and collapsed synthetic self_intersection to 0/104; candidate rejected and production checkpoint unchanged. Reviewed code + negative report `docs/validation/defect_head_real_clean_v1.md`; full suite 404 passed / 7 skipped. Backlog item stays open pending a larger independently verified real-CAD dataset.

## Doing
- **GenCAD walkthrough package** (BACKLOG `apply-call-walkthrough`): results table, IoU finding and fresh-clone demo evidence done; next session: examples idx 400 (IoU 1.0 plate), one truncation failure, idx 5699 (good IoU + self-intersection), idx 4836 (tube shell-vs-filled IoU).
- **GenCAD follow-ups:** `gencad-stop-problem` (all 12 failures are runaway generations), `gencad-strong-baseline` (one-shot prompt), Gemma-3-4B (`apply-gencad-vlm-track`).
- **SP1 checker-scored text-to-CAD benchmark** — paused behind GenCAD (`sp1-resume`, branch `sp1-bench`).
- QLoRA chat-SFT gold-set eval (GGUF + llama-server), then close. Low priority.

## Pipeline
- re-probe kimi-k2.6 on NIM (S3)
- defect head next levers (item Open): larger independently verified real-CAD clean + defective dataset with enough source families for a nontrivial holdout; self_int class needs interference feature. One-real-negative attempt exhausted 2026-10-25; do not tune that one-part mixture.
- Wave 3 (user-gated): one collaborative Colab QLoRA run (DECIDED: run once then stop); grow real_eval set 20-30 STEPs; gmsh-calibration do-or-drop
- gen v3 (CLI + Streamlit gen panel) deferred until v2 proves the loop
- ~~CI proven 2026-07-19: full-suite ran 190/192 on linux first try; 2 local-data tests now skip-if-absent; continue-on-error dropped (ci-full-suite-promote CLOSED)~~

## Resume here
Launch and edit in `Mech/SimReady`, branch `main`. Audit remediation is integrated at `f1b6e31` and `1433900`; plan `docs/exec-plans/active/2026-10-24-audit-remediation.md` is done except separately gated archive/worktree decisions. Next: GenCAD walkthrough examples listed under Doing, then `gencad-stop-problem` → `gencad-strong-baseline` → Gemma. `sp1-bench` remains paused at Task 2 review; original GenCAD worktree/assets remain. Defect experiment is preserved locally on `experiment/defect-real-clean` in `Mech/SimReady-real-clean` with ignored data/candidate artifacts; integrate only on explicit request, not automatically. Fresh environment-manager provisioning, full training rebuild, fresh GenCAD inference and additional hosted-model gate runs remain unverified. Do not commit or push without user approval.
