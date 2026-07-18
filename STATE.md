# STATE — SimReady

<!-- Machine-maintained by save-session Step 6b. Do not hand-edit. -->

Status: active
Last touched: 2026-05-31

## What
MecAgent ML/AI Founding Engineer portfolio project: AI-assisted FEA pre-processing. LLM copilot over B-rep analysis pipeline + BRepSAGE (3-head GraphSAGE) defect classifier + geometry-generation DSL (`build_part` tool). Strategy doc: docs/strategy/mecagent-gap-and-drift-2026-05-26.md.

## Done
- Full pipeline + copilot, 198 tests green in sr env
- Real-CAD OOD eval on 12 McMaster STEPs → docs/validation/real_eval.md (quantified the OOD gap)
- geometry-gen-mvp v1: typed Pydantic DSL + trusted executor (ADR 0001) + build_part tool, 31 new tests
- Honest README rewrite + self-demo artifacts; all pushed to origin (verified 0 0)

## Doing
- Nothing mid-flight — Stream A kickoff prompt ready in docs/session-prompts.md

## Pipeline
- gen v2: live-LLM E_grammar eval (tests/test_gen_e2e.py, ~90 s against NIM Llama-70B)
- gen v3: CLI + Streamlit gen panel
- S2: analyze-file OCC-hang per-check guard; defect-head real-CAD augmentation
- S3: grow real_eval set 20-30 STEPs
- User-gated: Colab T4 QLoRA finetune run; Gmsh install + calibration

## Resume here
Paste Stream A prompt from docs/session-prompts.md → build tests/data/gen_prompts.jsonl + tests/test_gen_e2e.py → write docs/validation/geometry_gen_eval.md.

## Landmines
- OCC C++ hangs are immune to Python thread timeouts — only multiprocessing Process.terminate() kills (12 h lost on a 58-face flange)
- Defect head fires >0.95 confidence on clean real CAD — do NOT trust ML scores on real parts until augmentation done
- tests/data/real_eval/ is gitignored (IP/size) — don't try to commit it
- BACKLOG.md has misfiled Done entries under stale 05-26→27 header (cosmetic, lesson #10)
