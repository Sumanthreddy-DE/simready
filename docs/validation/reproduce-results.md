# Reproduce SimReady results

**Last verified:** 2026-10-24  
**Platform for local verification:** Windows, Python 3.10.20, torch 2.12.0+cpu, PyG 2.7.0, pythonocc-core 7.9

This file separates four kinds of evidence: fresh inference, committed run records, saved-output arithmetic, and live-provider evaluation. They are not interchangeable.

## 1. Environment and deterministic demos

Follow `README.md` Quickstart. `environment.yml` supplies pythonOCC and CPU PyTorch;
`requirements.txt` supplies PyG, Pydantic, copilot/UI/RAG dependencies and pytest.

From the repository root in the activated environment:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "import OCC, torch_geometric, pydantic, streamlit; print('setup OK')"
python -m simready.cli analyze tests/data/smoke_box.step
python -m simready.gen.build
```

The last command builds the README bracket-with-hole spec and prints the generated path and
OCC summary. Analyze the returned `data/gen_parts/*.step` path as shown in the README.

## 2. BRepSAGE fixture inference — verified fresh on 2026-10-24

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/evaluate.py data/labels_fixtures_v2 weights/brepnet.pt --output evaluation-fixtures.json
```

Expected summary:

```text
samples=27  faces=3612  acc=0.853  precision=0.920  recall=0.895  f1=0.908  complexity_mse=0.0344  complexity_mae=0.1454  defect_acc=0.148
```

Inputs: local `data/labels_fixtures_v2/` and tracked `weights/brepnet.pt`.
The output should correspond to tracked `weights/eval_fixtures.json`. Fixture defect accuracy
is not a useful quality metric because these deliberately broken fixtures lack complete tags.

This proves the committed checkpoint reproduces the committed fixture inference numbers. It
does not prove training-data provenance, label correctness, or fresh training reproducibility.

## 3. Combined-v2 training record and reconstruction

Canonical record: `weights/metrics.json` and `weights/brepnet_meta.json`.

- Dataset: `data/labels_combined_v2/`, 2,272 graphs: 500 parametric + 600 degraded +
  293 fillet/chamfer-featured + 879 featured-degraded.
- Split: source-grouped 80/20; 1,801 train / 471 validation; seed `20260513` (script default).
- Model: 2-layer GraphSAGE, 32 hidden, three heads; 30 epochs; batch 8; Adam lr 1e-3.
- Recorded runtime: 56.18 s CPU; final validation refinement .825/.929/.609 and defect .686.

Exact training command used to reconstruct the experiment:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/train.py data/labels_combined_v2 weights-rebuilt --epochs 30 --batch-size 8 --lr 0.001 --hidden-dim 32 --num-layers 2 --seed 20260513
```

**Not executed in this remediation.** A rebuilt checkpoint must be written to a separate output
directory and compared by evaluation, never used to overwrite the shipped checkpoint before
comparison. Dataset generation is a longer pipeline; existing generation scripts are:

```powershell
python scripts/generate_parametric_steps.py --help
python scripts/generate_degraded_steps.py --help
python scripts/generate_features.py --help
python scripts/auto_label.py --help
```

The current docs do not yet establish a single end-to-end byte-identical dataset rebuild recipe;
that remains an explicit evidence gap rather than a claim of full reproducibility.

## 4. Geometry generation gates

Historical hosted-model 5/5 results in `docs/validation/geometry_gen_eval.md` used the artifact
gate: STEP exists, OCC-valid, face count in range. They are retained as historical evidence.

The strengthened opt-in harness at `tests/test_gen_e2e.py` additionally records and enforces:

- declared box dimensions and centered through-hole diameter/full thickness;
- successful `analyze_geometry` result for the exact final STEP;
- the agent's analyze call used that same final path.

Deterministic checks live at `tests/test_gen_verify.py` and run without an LLM:

```powershell
python -m pytest tests/test_gen_verify.py -q
```

A fresh hosted-model claim requires explicitly opting in with provider credentials:

```powershell
$env:OPENAI_BASE_URL = "https://api.vultrinference.com/v1"
$env:OPENAI_MODEL = "glm-5.3"
$env:OPENAI_API_KEY_VAR = "VULTR_API_KEY"  # resolves the key from environment/.env without printing it
python -m pytest tests/test_gen_e2e.py -m live_llm -v
```

**Verified fresh on 2026-10-24:** Vultr `glm-5.3`, **5 passed in 175.06 s**, one run per prompt.
All mechanical errors empty, final analysis successful, final path matched. Compact tracked
record: `generation_gate_2026-10-24.json`; raw per-prompt records go to
`data/gen_eval/<model>.jsonl` (ignored). Verdict prose was not gated.

## 5. GenCAD saved-output analysis and inference

Canonical evaluation detail: `docs/validation/gencad_eval.md`.
Tracked saved outputs: `docs/validation/gencad/`.
Local cache paths/provenance: `docs/impl/workspace-artifacts.md`.

Prepare caches and run local analyses:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python scripts/gencad_reference.py
python scripts/gencad_analyse.py
```

`gencad_reference.py` downloads `CADCODER/GenCAD-Code` test parquet if absent and writes the
100-row reference cache. `gencad_analyse.py` reads tracked generations/scores plus that cache.

The IoU-filled and checker-bridge steps require additional environments and generated reference
STEPs; follow the exact script order in `docs/validation/gencad_eval.md`. MecAgent metric source
is cached at `data/gencad/mecagent_metrics/best_iou.py`.

Model inference is a separate Colab workflow (`notebooks/gencad_baseline.ipynb` and
`notebooks/gencad_train_qwen.ipynb`). The Qwen adapter is not tracked in Git; its canonical local
path is `weights/gencad_qwen25vl3b_qlora/` and its original Drive location is
`MyDrive/gencad/qwen_lora_adapter`. A fresh inference result must identify the adapter/base
model, dataset subset, decoding settings and metric source; arithmetic over saved scores alone
does not verify model execution.

## 6. Claims still requiring fresh evidence

- Full fresh-clone provisioning on a clean machine (browser chat/build/analyze passed in the
  provisioned canonical workspace on 2026-10-24; a separate clean-clone check remains).
- Additional hosted models under the strengthened generation gate (GLM 5.3 passed 5/5).
- End-to-end training dataset reconstruction and a rebuilt-checkpoint comparison.
- Fresh GenCAD inference from the retrieved adapter, not just saved-output arithmetic.
- Real-CAD and copilot gold-set numbers not rerun in this remediation.
