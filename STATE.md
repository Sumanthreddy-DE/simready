# STATE — SimReady

<!-- Machine-maintained by save-session Step 6b. Hand-edit 2026-07-19 authorized by user (triage session). -->

Status: active
Last touched: 2026-07-19

## What
MecAgent ML/AI Founding Engineer portfolio project: AI-assisted FEA pre-processing. LLM copilot over B-rep analysis pipeline + BRepSAGE (3-head GraphSAGE) defect classifier + geometry-generation DSL (`build_part` tool). **Application NEVER sent** (`v0.4.0-apply` was prep only — corrected 2026-07-19); apply AFTER project substantial. Strategy doc: docs/strategy/mecagent-gap-and-drift-2026-05-26.md; wave plan: BACKLOG.md "Triage 2026-07-19".

## Done
- Full pipeline + copilot, 202 tests green in sr env
- Real-CAD OOD eval on 12 McMaster STEPs → docs/validation/real_eval.md (quantified the OOD gap)
- geometry-gen-mvp v1: typed Pydantic DSL + trusted executor (ADR 0001) + build_part tool
- Honest README rewrite + self-demo artifacts
- **Wave-1 hygiene (2026-07-19, `1d5a80a..`):** truth sweep (build_part now in system prompt), render→png_render rename, repo-root path anchoring, committed seed RAG index (lookup_standard live on clones), CI (spec-fast + micromamba full job), BACKLOG never-applied correction
- **geometry-gen v2 (2026-07-19):** live-LLM E_grammar eval, dual-model on NIM — GLM 5.2 **5/5**, Llama-3.3-70B **3/5** (dropped-boolean failure mode). Kimi K2.6 blocked by NIM account 404 (S3). docs/validation/geometry_gen_eval.md
- **OCC-hang guard (2026-07-19):** diagnosed (BOPAlgo on B-spline flanges; thread watchdogs GIL-inert) + fixed (freeform precheck + `analyze_file_safe` killable child at all entry points). Real-eval coverage 7/12 → 11/12, 0 errors. docs/validation/occ_hang_diagnosis.md
- **defect-head augmentation attempt (2026-07-19):** combined-v2 retrain (2272 graphs w/ fillet/chamfer randomization) — val 0.686 harder-val, fixtures refinement 0.853/0.895, but **real-CAD FP still 11/11**. Honest negative; synthetic-augmentation lever exhausted. Item stays Open w/ findings.

## Doing
- Wave 2 items 1-3 all touched; item 3 concluded as honest negative (real-CAD data or grammar extension = remaining levers, both user-gated-ish)

## Pipeline
- gen v2.1: orphan-step Pydantic rule (S2, cheap — would have caught both Llama failures); re-probe kimi-k2.6 on NIM (S3)
- defect head next levers (item Open): hand-labelled real-CAD positives / clean real negatives in training / grammar extension to revolved surfaces; self_int class needs interference feature
- Wave 3 (user-gated): one collaborative Colab QLoRA run (DECIDED: run once then stop); grow real_eval set 20-30 STEPs; gmsh-calibration do-or-drop
- gen v3 (CLI + Streamlit gen panel) deferred until v2 proves the loop
- CI proven 2026-07-19: full-suite ran 190/192 on linux first try; 2 local-data tests now skip-if-absent; continue-on-error dropped (ci-full-suite-promote CLOSED)

## Resume here
Wave 2 complete + pushed + CI green (2026-07-19, `b62fc9e..2e04391`). Paste **Stream D** from docs/session-prompts.md (wave 3: orphan-step rule quick win → Colab QLoRA once → real-eval growth → gmsh do-or-drop → **THE APPLY DECISION**). Main event is E: decide go/no-go on MecAgent application with wave-2 evidence in hand.

## Landmines
- Memory + old BACKLOG claimed "applied to MecAgent 2026-05-18" — FALSE, never applied (corrected 2026-07-19; memory + BACKLOG fixed)
- OCC C++ hangs are immune to Python thread timeouts — only multiprocessing Process.terminate() kills (12 h lost on a 58-face flange)
- Defect head fires >0.95 confidence on clean real CAD — do NOT trust ML scores on real parts until augmentation done
- tests/data/real_eval/ is gitignored (IP/size) — don't try to commit it
- torch_geometric is NOT in requirements.txt/environment.yml (Windows wheel gotcha) — CI installs it pip-side; sr env has it manually
