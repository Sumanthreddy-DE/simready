# GenCAD-Code eval: image → CadQuery (MecAgent technical test)

Task: MecAgent's public technical test (`github.com/MecAgent/mecagent-technical-test`):
generate CadQuery code from an image on `CADCODER/GenCAD-Code`, report a baseline and an
enhanced model. Metrics are MecAgent's own code (`metrics/best_iou.py`), cloned and called
unchanged.

## Setup

| Item | Value |
|---|---|
| Eval set | the dataset's `hundred_subset` of the test split (100 of 7,355 rows) |
| Prompt | the dataset's own `prompt` column (one prompt for all rows): "Generate the CADQuery code needed to create the CAD for the provided image. Just the code, no other words." |
| Input | 448×448 render, image first, then the prompt |
| Decoding | greedy, `max_new_tokens` 1825 (1.2 × p95 of reference code length) |
| Post-processing | strip one Markdown code fence (any language tag); nothing else |
| Scoring | each sample in its own process, 120 s timeout. VSR = program runs and yields a CadQuery solid. IoU_best = MecAgent's voxel IoU after principal-axis alignment |
| Hardware | Colab free tier, T4 |
| Notebook | `notebooks/gencad_baseline.ipynb` (same notebook for base and tuned; `MODEL_TAG` / `ADAPTER` in cell 3) |

IoU is reported two ways: over valid programs only (MecAgent's `evaluate_codes` definition) and
with invalid programs counted as 0.

## Results

| Model | VSR | IoU_best (valid only) | IoU_best (invalid = 0) |
|---|---|---|---|
| Qwen2.5-VL-3B-Instruct, untuned (4-bit) | 0.00 (0/100) | — | 0.000 |
| Qwen2.5-VL-3B + QLoRA (6k examples, 1 epoch) | pending | pending | pending |

## Baseline: why 0/100

The untuned model does not write Python. All 100 answers are fenced as ```` ```json ````:
94 are invented JSON with no CadQuery at all (e.g. `{"name": "CADQuery", "version": "1.0",
"commands": [...]}`); 6 contain CadQuery-like fragments inside the JSON. None executes. We do not
extract code from inside JSON strings: that would repair the model's answer, and the metric runs
the answer as given.

Caveat for reading the comparison: a 0 % baseline makes any working model look like a large
gain. A stronger baseline (same untuned model, prompt with one example program) is planned
if time allows.

A scoring bug was found and fixed before this number was recorded: the fence stripper first
handled only ```` ```python ````, so ```` ```json ```` fences stayed in. Re-scored from the
saved raw outputs after the fix (`c27b18e`); the result stayed 0/100.

## Training run (Qwen2.5-VL-3B QLoRA)

Notebook `notebooks/gencad_train_qwen.ipynb`. Base `unsloth/Qwen2.5-VL-3B-Instruct-bnb-4bit`,
LoRA r=16 / alpha=16 on language attention + MLP (vision tower frozen). 6,000 training examples:
seeded random subset of the 147,289-row train split, skipping reference programs longer than
1,500 tokens (≈ p95). 1 epoch, 750 steps, batch 8, lr 2e-4, 3 h 35 min on a T4.
Train loss 1.19 (step 10) → 0.33 (step 30) → 0.10–0.18 from step ~200 on; mean 0.177. No
validation loss was logged; the 100-row eval above is the held-out check.
