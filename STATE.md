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

## Doing
- Wave 2 next: gen v2 live-LLM E_grammar runner (docs/session-prompts.md Stream A) with NIM Llama-70B primary + Kimi K2.6 second backend (user adds KIMI_API_KEY to .env; GLM 5.2 + MiniMax M3 keys also available)

## Pipeline
- Wave 2: gen v2 live-LLM eval → analyze-file OCC-hang per-check guard → defect-head real-CAD augmentation
- Wave 3 (user-gated): one collaborative Colab QLoRA run (DECIDED: run once then stop); grow real_eval set 20-30 STEPs; gmsh-calibration do-or-drop
- gen v3 (CLI + Streamlit gen panel) deferred until v2 proves the loop
- CI proven 2026-07-19: full-suite ran 190/192 on linux first try; 2 local-data tests now skip-if-absent; continue-on-error dropped (ci-full-suite-promote CLOSED)

## Resume here
Push c57709c if unpushed (verify 0 0), then paste Stream C prompt from docs/session-prompts.md (gen v2 dual-provider; Stream A superseded). Confirm exact Kimi K2.6 model id with user before the Kimi leg.

## Landmines
- Memory + old BACKLOG claimed "applied to MecAgent 2026-05-18" — FALSE, never applied (corrected 2026-07-19; memory + BACKLOG fixed)
- OCC C++ hangs are immune to Python thread timeouts — only multiprocessing Process.terminate() kills (12 h lost on a 58-face flange)
- Defect head fires >0.95 confidence on clean real CAD — do NOT trust ML scores on real parts until augmentation done
- tests/data/real_eval/ is gitignored (IP/size) — don't try to commit it
- torch_geometric is NOT in requirements.txt/environment.yml (Windows wheel gotcha) — CI installs it pip-side; sr env has it manually
