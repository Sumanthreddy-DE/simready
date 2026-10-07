# STATE — SimReady

<!-- Machine-maintained by save-session Step 6b. Hand-edit 2026-07-19 authorized by user (triage session). -->

Status: active
Last touched: 2026-10-07

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

## Doing
- **GenCAD walkthrough package** (BACKLOG `apply-call-walkthrough`, week of 2026-10-12): results table + 3-4 examples + surface-vs-filled IoU finding, from `docs/validation/gencad_eval.md`. Work in worktree `Mech/SimReady-gencad`, branch `gencad`.
- **GenCAD follow-ups:** `gencad-stop-problem` (all 12 failures are runaway generations), `gencad-strong-baseline` (one-shot prompt), Gemma-3-4B (`apply-gencad-vlm-track`).
- **SP1 checker-scored text-to-CAD benchmark** — paused behind GenCAD (`sp1-resume`, branch `sp1-bench`).
- QLoRA chat-SFT gold-set eval (GGUF + llama-server), then close. Low priority.

## Pipeline
- re-probe kimi-k2.6 on NIM (S3)
- defect head next levers (item Open): hand-labelled real-CAD positives / clean real negatives in training / grammar extension to revolved surfaces; self_int class needs interference feature
- Wave 3 (user-gated): one collaborative Colab QLoRA run (DECIDED: run once then stop); grow real_eval set 20-30 STEPs; gmsh-calibration do-or-drop
- gen v3 (CLI + Streamlit gen panel) deferred until v2 proves the loop
- CI proven 2026-07-19: full-suite ran 190/192 on linux first try; 2 local-data tests now skip-if-absent; continue-on-error dropped (ci-full-suite-promote CLOSED)

## Resume here
Launch Claude from `Mech/SimReady` (Citadel memory resolves there; the worktree path resolves to the projects-root router), then edit files in the worktree `Mech/SimReady-gencad` (branch `gencad`): build the MecAgent walkthrough package — results table (base vs tuned: VSR, MecAgent IoU, filled IoU, checker), examples (IoU-1.0 plate, a truncation failure, idx 5699 self-intersecting with good IoU, tube idx 4836), the IoU finding. Then `gencad-stop-problem` → `gencad-strong-baseline` → Gemma. Session: `sessions/2026-10-07-gencad-qwen-results-session.tmp`.
