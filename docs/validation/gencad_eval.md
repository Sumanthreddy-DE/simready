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
| Qwen2.5-VL-3B + QLoRA (6k examples, 1 epoch) | **0.88 (88/100)** | 0.256 | 0.225 |

Run 2026-10-07, T4, ~81 s per example on average (2 h 15 min for 100; resumed once after a
disconnect at 37/100).

## Tuned model: reading the numbers

- **VSR 0 → 0.88 is mostly format.** The tuned model writes Python in GenCAD's own style
  (`cq.Workplane(cq.Plane(...))`, `moveTo/lineTo/close`, `extrude`) instead of JSON.
- **Geometry is the weak part.** Mean IoU_best over the 88 runnable programs is 0.256. The two
  IoU = 1.0 examples are a single rectangular plate (idx 400) and a single disc (idx 2440), the
  simplest parts in the set. IoU distribution by part complexity: not yet analysed.
- **Failures (12): all 12 are truncated programs** (`'(' was never closed`): the output hit
  `max_new_tokens` = 1825 mid-line. In 11 of 12 the model wrote more sketches than the reference
  (e.g. 11 vs 2, 10 vs 3): it does not stop, rather than writing invalid CadQuery. No failure
  was a CadQuery API or runtime error.
- **IoU is bimodal; the mean hides it.** Over the 88 runnable programs: median 0.047, mean
  0.256. 50 of 88 are below 0.1; 22 are at 0.5 or above, 6 at ≥ 0.95.
- **Accuracy falls with part complexity** (reference sketch count; VSR over all rows, IoU over
  runnable rows):

  | Reference sketches | n | VSR | mean IoU | predicted sketch count = reference |
  |---|---|---|---|---|
  | 1 | 57 | 1.00 | 0.312 | 41/57 |
  | 2 | 18 | 0.78 | 0.199 | 6/18 |
  | 3 | 12 | 0.58 | 0.147 | 2/12 |
  | 4–8 | 13 | 0.69 | 0.10 | 4/13 |

- **MecAgent's IoU compares surface shells, not volumes (verified 2026-10-07).**
  `best_iou.py` calls `mesh.voxelized(pitch)` without `.fill()`; trimesh then returns surface
  voxels only. Check: a 1×1×1 cube at pitch 0.05 gives 2,402 voxels from `voxelized()` and
  9,261 after `.fill()`. Two shells overlap only where the surfaces coincide within one voxel,
  so near-identical solid parts score near zero, while thin plates (shell ≈ solid) score high.
  Example idx 4836: reference tube outer r 0.138 / inner r 0.055 / length 0.734, prediction
  0.182 / 0.079 / 0.75, same construction: shell IoU 0.010, filled IoU 0.588.

  Re-scored all 88 runnable programs locally with MecAgent's file unchanged, plus a copy whose
  only change is `.fill()` on both voxel grids (cadquery 2.8.0, trimesh, Windows). The local
  shell scores reproduce the Colab scores (max abs. difference 4e-4 over 88; mean and median
  identical).

  | IoU variant (88 runnable) | mean | median | < 0.1 | ≥ 0.5 | ≥ 0.8 | mean over 100 (invalid = 0) |
  |---|---|---|---|---|---|---|
  | MecAgent metric (surface shells) | 0.256 | 0.047 | 50 | 22 | 10 | 0.225 |
  | Same, filled voxels | 0.563 | 0.580 | 4 | 50 | 22 | 0.495 |

  Both are reported. The headline stays MecAgent's own metric, because that is the task's
  stated metric; the filled variant shows that most low scores are a property of the metric,
  not of the parts. Both variants are scale-invariant (radius-of-gyration normalization), so
  neither measures absolute dimensions.
- **Scale-invariance:** the metric normalizes by radius of gyration, so a plate twice the size
  of the reference scores 1.0 (idx 400). Absolute dimensions are not measured.
- **Scale of the run:** 6k of 147k training examples (4 %), 1 epoch, programs over 1,500
  tokens excluded from training. Any comparison with published GenCAD-Code results must say so.

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
