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

## SimReady checker on the generated parts (checker bridge)

CadQuery program → STEP (Colab, cell 5) → scale so the largest bounding-box side is 100 mm →
`analyze_file_safe`. Scaling is needed because GenCAD parts are normalized to ~1.5 units and
the checker's thresholds are in mm; unscaled, every part fails ThinWalls/SmallFeatures. The
100 mm size is an assumption, not the parts' real size. The 88 matching reference parts were
scored the same way as the comparison.

| | Generated (88) | Reference (same 88 rows) |
|---|---|---|
| Mean overall score | 86.9 | 84.9 |
| SimulationReady / ReviewRecommended / NeedsAttention / InvalidInput | 37 / 40 / 10 / 1 | 27 / 48 / 12 / 1 |
| Same status as the reference | 60 / 88 | — |

- **The checker does not measure fidelity.** Generated parts score slightly higher because they
  are simpler than the references (fewer sketches, so fewer ShortEdges/SmallFeatures flags).
- **Its value is the defects the model introduced.** Flags on a generated part that its
  reference does not have: ThinWalls 6, SelfIntersection 3, SmallFilletsOrHoles 2,
  ThinSolid 1, SmallFeatures 1; plus idx 2097, an invalid solid (OCC BRepCheck fails) whose
  reference is valid.
- **IoU cannot see these.** idx 5699: IoU 0.830 (shell) / 0.893 (filled), but the generated
  part self-intersects (NeedsAttention, 47.5); the reference does not. idx 720: IoU 0.555 /
  0.716, also self-intersecting. Two cases out of 88: an example, not a rate.

## Files and how to reproduce

Results in `docs/validation/gencad/` (committed):

| File | Made by | Content |
|---|---|---|
| `gen_qwen25vl3b_qlora.jsonl` | `notebooks/gencad_baseline.ipynb` cell 4 | raw + stripped output per eval row |
| `scores_qwen25vl3b_{base,qlora}.json` | same notebook, cell 5 | MecAgent metric per row (valid, iou, err) |
| `steps/*.step` | same notebook, cell 5 | 88 generated solids, original GenCAD scale |
| `per_row_analysis.json` | `scripts/gencad_analyse.py` | sketch counts, lengths, features per row |
| `iou_shell_vs_filled.json` | `scripts/gencad_iou_filled.py` | MecAgent IoU vs filled-voxel IoU per row |
| `checker_{generated,reference}.jsonl` | `scripts/gencad_checker_bridge.py` | checker status, score, findings per part |

The baseline's raw generations stayed on Colab Drive (all 100 are JSON, see above); its scores
file is here. The QLoRA adapter (~130 MB) is on Google Drive (`MyDrive/gencad/qwen_lora_adapter`),
not in git.

Order: `gencad_reference.py` (sr env) → `gencad_analyse.py` → `gencad_iou_filled.py` and
`gencad_export_reference_steps.py` (a venv with cadquery + trimesh) → `gencad_checker_bridge.py
generated|reference` (sr env). Caches go to `data/gencad/` (gitignored).

## Running on free Colab (practical notes)

- **Each Google profile has its own Drive.** An adapter trained in one profile is invisible to a
  notebook in another (`Can't find 'adapter_config.json'`). Decide which profile runs the eval
  before training, or copy `MyDrive/gencad/qwen_lora_adapter/` across (Drive download → folder
  upload; check `adapter_config.json` sits directly inside, not in a nested folder).
- **The free tier's daily GPU limit hit after ~3.5 h** (the training run). The eval then had to run
  in a second profile. Generation and training resume from Drive after a disconnect.
- **Estimate eval time from the reference program length, not from the baseline run.** The
  untuned base answers with short JSON (100 rows in 34 min); the tuned model writes ~470-token
  programs at ~81 s per row on a T4 with the 4-bit LoRA (2 h 15 min). Runaway rows that hit
  `max_new_tokens` take 4–6 min each.

## Next steps (from this evidence)

1. **Stopping problem:** all 12 failures are runaway generations. Try a stop rule or repetition
   penalty at inference (no retraining) and re-score; expected to lift VSR toward the
   single-sketch rate.
2. **Stronger baseline:** untuned model with one example program in the prompt, so the
   0 → 0.88 comparison is not against a model that answers in JSON.
3. **Gemma-3-4B:** same notebooks, second model.
4. **More data / longer training:** 6k of 147k examples, 1 epoch; accuracy on 2+ sketch parts
   is the gap.

## Training run (Qwen2.5-VL-3B QLoRA)

Notebook `notebooks/gencad_train_qwen.ipynb`. Base `unsloth/Qwen2.5-VL-3B-Instruct-bnb-4bit`,
LoRA r=16 / alpha=16 on language attention + MLP (vision tower frozen). 6,000 training examples:
seeded random subset of the 147,289-row train split, skipping reference programs longer than
1,500 tokens (≈ p95). 1 epoch, 750 steps, batch 8, lr 2e-4, 3 h 35 min on a T4.
Train loss 1.19 (step 10) → 0.33 (step 30) → 0.10–0.18 from step ~200 on; mean 0.177. No
validation loss was logged; the 100-row eval above is the held-out check.
