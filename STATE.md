# STATE — SimReady

<!-- Machine-maintained by save-session Step 6b. Hand-edit 2026-07-19 authorized by user (triage session). -->

Status: active
Last touched: 2026-10-05

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
- **2026-10-05:** application sent; follow-up commitments filed as BACKLOG `apply-*` items (`11fb5e1`, `3822d3b`), GenCAD promoted to S1 ahead of SP1.

## Doing
- **GenCAD VLM track (BACKLOG `apply-gencad-vlm-track`, S1)** — image→CadQuery on `CADCODER/GenCAD-Code`, Qwen2.5-VL-3B then Gemma-3-4B, each vs untuned base, VSR + best IoU + SimReady checker (`apply-gencad-checker-bridge`). First model due 2026-10-11. Branch not decided yet (`sp1-bench` vs fresh off `main`).
- **Gen eval on GLM 5.3 + DeepSeek V4.1 Flash** (`apply-gen-eval-glm53-deepseek`, S1), then walkthrough package for week of 2026-10-12 (`apply-call-walkthrough`).
- **SP1 checker-scored text-to-CAD benchmark** — paused behind GenCAD (decided 2026-10-05); design complete, awaiting user review: `docs/exec-plans/active/2026-09-25-sp1-cad-benchmark-design.md` (D1–D7, §1–§3). Then SP2 (DSL v2) → SP3 (GRPO, checker reward).
- QLoRA chat-SFT: adapter recovered to `weights/qlora/` (gitignored), loss recorded in `docs/finetune_results.md`; one gold-set eval (GGUF + llama-server), then close. Low priority vs SP1.

## Pipeline
- re-probe kimi-k2.6 on NIM (S3)
- defect head next levers (item Open): hand-labelled real-CAD positives / clean real negatives in training / grammar extension to revolved surfaces; self_int class needs interference feature
- Wave 3 (user-gated): one collaborative Colab QLoRA run (DECIDED: run once then stop); grow real_eval set 20-30 STEPs; gmsh-calibration do-or-drop
- gen v3 (CLI + Streamlit gen panel) deferred until v2 proves the loop
- CI proven 2026-07-19: full-suite ran 190/192 on linux first try; 2 local-data tests now skip-if-absent; continue-on-error dropped (ci-full-suite-promote CLOSED)

## Resume here
1) Decide GenCAD branch (`sp1-bench` or fresh off `main`, cherry-pick `11fb5e1` + `3822d3b`). 2) Colab: install cadquery + Unsloth, load GenCAD-Code, held-out split, score untuned Qwen2.5-VL-3B on VSR + IoU (baseline), then QLoRA. 3) GLM 5.3 / DeepSeek V4.1 Flash gen eval. 4) SP1 resumes after.  Session: `sessions/2026-10-05-mecagent-sent-session.tmp`.

## Landmines
- Memory + old BACKLOG claimed "applied to MecAgent 2026-05-18" — FALSE, never applied (corrected 2026-07-19; memory + BACKLOG fixed)
- OCC C++ hangs are immune to Python thread timeouts — only multiprocessing Process.terminate() kills (12 h lost on a 58-face flange)
- Defect head fires >0.95 confidence on clean real CAD — do NOT trust ML scores on real parts until augmentation done
- tests/data/real_eval/ is gitignored (IP/size) — don't try to commit it
- torch_geometric is NOT in requirements.txt/environment.yml (Windows wheel gotcha) — CI installs it pip-side; sr env has it manually
