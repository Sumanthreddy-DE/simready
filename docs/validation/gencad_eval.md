# GenCAD-Code eval: image → CadQuery (MecAgent technical test)

This is my answer to MecAgent's technical test
([`MecAgent/mecagent-technical-test`](https://github.com/MecAgent/mecagent-technical-test)):
generate CadQuery code from a part image on `CADCODER/GenCAD-Code`, build a baseline, improve
it, and score both with the test's own metrics. I call MecAgent's metric code unchanged.

## Summary

| Model (Qwen2.5-VL-3B-Instruct, 4-bit) | VSR | IoU_best (valid only) | IoU_best (invalid = 0) |
|---|---|---|---|
| Untuned | 0.00 (0/100) | — | 0.000 |
| Untuned, one example in the prompt (one-shot) | 0.01 (1/100) | 0.027 | 0.0003 |
| QLoRA fine-tune (6k examples, 1 epoch, free T4) | **0.88 (88/100)** | 0.256 | 0.225 |
| QLoRA + stop rule R1 (no retraining) | **1.00 (100/100)** | 0.230 | 0.230 |

Eval set: the dataset's own `hundred_subset` (100 of 7,355 test rows). VSR = the program runs
and yields a solid. IoU_best = MecAgent's voxel IoU after alignment, reported over valid
programs only (MecAgent's definition) and with invalid programs counted as 0.

The test notebook (`good_luck.ipynb`) asks five things. Short answers:

1. **Data.** 147,289 image/code training pairs. I trained on 6,000 of them (4 %).
2. **Baseline.** The untuned model answers in JSON, so nothing runs. With one example program
   in the prompt it switches to CadQuery, but copies the example for 99 of 100 images.
3. **Enhancement.** QLoRA fine-tuning lifts VSR to 0.88. All 12 failures were programs that did
   not stop; trimming them to the last complete `solid=` line lifts VSR to 1.00.
4. **Choices and bottlenecks.** A 3B vision-language model in 4-bit fits a free Colab T4.
   The real bottleneck is geometry, not syntax: accuracy falls with the number of sketches.
   The metric itself is a second bottleneck: it compares surface shells and ignores scale.
5. **With more time.** More data and epochs, a second model (Gemma-3-4B), and a reward that
   includes a geometry checker, because IoU misses defects such as self-intersections.

## Setup

| Item | Value |
|---|---|
| Eval set | `hundred_subset` of the test split (100 of 7,355 rows) |
| Prompt | the dataset's own `prompt` column, the same for all rows: "Generate the CADQuery code needed to create the CAD for the provided image. Just the code, no other words." |
| Input | 448×448 render, image first, then the prompt |
| Decoding | greedy, `max_new_tokens` 1825 (1.2 × p95 of reference code length) |
| Post-processing | strip one Markdown code fence (any language tag); nothing else |
| Scoring | each sample in its own process, 120 s timeout |
| Hardware | Colab free tier, T4 |
| Notebook | `notebooks/gencad_baseline.ipynb`, one notebook for all runs (`SHOTS`, `MODEL_TAG`, `ADAPTER` in cell 3) |

## Baselines

**Untuned (0/100).** The model does not write Python. All 100 answers are fenced as
```` ```json ````: 94 are invented JSON with no CadQuery at all (e.g. `{"name": "CADQuery",
"version": "1.0", "commands": [...]}`), and 6 hold CadQuery-like fragments inside the JSON.
I do not extract code from inside JSON strings: that would repair the model's answer, and the
metric runs the answer as given. (A scoring bug was fixed before this number was recorded: the
fence stripper first handled only ```` ```python ````. Re-scored from the saved outputs after
the fix, `c27b18e`; still 0/100.)

A 0 % baseline makes any working model look like a big gain, so I also ran a prompted one.

### Prompted baseline

**One-shot (1/100, 2026-11-15).** Same model, rows, prompt, decoding and scoring. Before each
test image, the chat shows one training example: its image, then its reference program as
the answer. The example is `train` row 87, picked by a fixed rule (among the first 2,000
training rows, the one-sketch program closest to the eval set's median length).

- The model copies the example instead of reading the image. There are only 2 distinct
  outputs over 100 rows. 99 are the example program with its first `)))` cut to `))`, so they
  fail with `'(' was never closed`. The example program itself compiles.
- The one valid row (idx 1446) is a different program, a single extruded circle: IoU 0.027.
- So the fine-tune's gain is not only output format. A prompted model that already writes
  GenCAD-style CadQuery still scores 0.01, because it does not use the image.
- Not tried: two or more examples, or a different example per row.

## Fine-tuned model

Run 2026-10-07 on a T4, ~81 s per example (2 h 15 min for 100 rows).

- **Format is part of the gain.** The tuned model writes Python in GenCAD's own style
  (`cq.Workplane(cq.Plane(...))`, `moveTo/lineTo/close`, `extrude`) instead of JSON. The
  one-shot result above shows that format alone does not explain it.
- **All 12 failures are programs that did not stop.** Each hit `max_new_tokens` mid-line
  (`'(' was never closed`). In 11 of 12 the model wrote more sketches than the reference
  (e.g. 11 vs 2). No failure was a CadQuery API or runtime error.
- **Geometry is the weak part.** Mean IoU over the 88 runnable programs is 0.256, but the
  median is 0.047: 50 of 88 are below 0.1, 22 are at 0.5 or above, 6 at ≥ 0.95. The two IoU = 1.0 parts are
  a plain rectangular plate (idx 400) and a disc (idx 2440).
- **Accuracy falls with part complexity** (sketches in the reference program):

  | Reference sketches | n | VSR | mean IoU | predicted sketch count = reference |
  |---|---|---|---|---|
  | 1 | 57 | 1.00 | 0.312 | 41/57 |
  | 2 | 18 | 0.78 | 0.199 | 6/18 |
  | 3 | 12 | 0.58 | 0.147 | 2/12 |
  | 4–8 | 13 | 0.69 | 0.10 | 4/13 |

## Stop rules

All 12 failures were runaway generations, so I tested stopping rules offline on the saved
outputs (2026-11-12, no new generation). R1 trims a program that does not parse back to its
last complete `solid=` line: VSR 88 → 100/100. The 12 recovered parts are poor (mean IoU
0.038, max 0.080), so IoU with invalid = 0 moves only 0.225 → 0.230. In 22 valid programs the extra
sketches were exact copies unioned onto the same solid: they cost tokens and time, not
geometry. A repetition penalty at decoding time was not tested (needs a GPU).
Full tables and controls: [gencad_stop_rules.md](gencad_stop_rules.md).

## The IoU metric

**It compares surface shells, not volumes.** `best_iou.py` calls `mesh.voxelized(pitch)`
without `.fill()`, so trimesh returns surface voxels only. Check: a 1×1×1 cube at pitch 0.05
gives 2,402 voxels from `voxelized()` and 9,261 after `.fill()`. Two shells overlap only where
the surfaces lie within one voxel of each other, so near-identical solids can score near zero,
while thin plates score high. Example idx 4836: reference tube outer r 0.138 / inner r 0.055 /
length 0.734, prediction 0.182 / 0.079 / 0.75, same construction: shell IoU 0.010, filled 0.588.

I re-scored all 88 runnable programs locally with MecAgent's file unchanged and with a copy
whose only change is `.fill()` on both voxel grids. The local shell scores match the Colab
scores (max difference 4e-4).

| IoU variant (88 runnable) | mean | median | < 0.1 | ≥ 0.5 | ≥ 0.8 | mean over 100 (invalid = 0) |
|---|---|---|---|---|---|---|
| MecAgent metric (surface shells) | 0.256 | 0.047 | 50 | 22 | 10 | 0.225 |
| Same, filled voxels | 0.563 | 0.580 | 4 | 50 | 22 | 0.495 |

The headline stays MecAgent's metric, because that is the task's metric. The filled variant
shows that most low scores come from the metric, not from the parts.

**It ignores scale.** Both variants normalize by radius of gyration, so a plate twice the size
of the reference scores 1.0 (idx 400). Absolute dimensions are not measured.

## Geometry checker on the generated parts

I also ran each generated part through SimReady's own B-rep checker. CadQuery program → STEP →
scaled so the largest bounding-box side is 100 mm (GenCAD parts are normalized to ~1.5 units
and the checker's thresholds are in mm; the 100 mm size is an assumption) → `analyze_file_safe`.
The 88 matching reference parts were scored the same way.

| | Generated (88) | Reference (same 88 rows) |
|---|---|---|
| Mean overall score | 86.9 | 84.9 |
| SimulationReady / ReviewRecommended / NeedsAttention / InvalidInput | 37 / 40 / 10 / 1 | 27 / 48 / 12 / 1 |
| Same status as the reference | 60 / 88 | — |

- **The checker does not measure fidelity.** Generated parts score slightly higher because they
  are simpler than the references.
- **It finds defects the model added.** Flags on a generated part that its reference does not
  have: ThinWalls 6, SelfIntersection 3, SmallFilletsOrHoles 2, ThinSolid 1, SmallFeatures 1;
  plus idx 2097, an invalid solid whose reference is valid.
- **IoU cannot see these.** idx 5699 scores IoU 0.830 (shell) / 0.893 (filled), but the
  generated part self-intersects (NeedsAttention, 47.5); the reference does not. idx 720 (IoU 0.555 / 0.716) also
  self-intersects. Two cases in 88: examples, not a rate.

Four cases with measured geometry and paired renders: [walkthrough examples](gencad_examples.md).

## Next steps

1. **Stopping problem.** Done offline 2026-11-12 (see Stop rules). Untested: a repetition
   penalty at decoding time.
2. **Stronger baseline.** Done 2026-11-15 (see Prompted baseline): 0.01, the model copies the
   example.
3. **Gemma-3-4B:** same notebooks, second model, against its own untuned base.
4. **More data and longer training:** 6k of 147k examples, 1 epoch. Parts with 2+ sketches are
   the gap.
5. **Checker in the reward:** combine IoU with the geometry checker so self-intersecting or
   invalid solids are penalized.

## Training run (Qwen2.5-VL-3B QLoRA)

Notebook `notebooks/gencad_train_qwen.ipynb`. Base `unsloth/Qwen2.5-VL-3B-Instruct-bnb-4bit`,
LoRA r=16 / alpha=16 on language attention + MLP (vision tower frozen). 6,000 training examples:
seeded random subset of the 147,289-row train split, skipping reference programs longer than
1,500 tokens (≈ p95). 1 epoch, 750 steps, batch 8, lr 2e-4, 3 h 35 min on a T4.
Train loss 1.19 (step 10) → 0.33 (step 30) → 0.10–0.18 from step ~200 on; mean 0.177. No
validation loss was logged; the 100-row eval above is the held-out check. Any comparison with
published GenCAD-Code results must account for this small scale.

## Files and how to reproduce

Results in `docs/validation/gencad/` (committed):

| File | Made by | Content |
|---|---|---|
| `gen_qwen25vl3b_qlora.jsonl` | `notebooks/gencad_baseline.ipynb` cell 4 | raw + stripped output per eval row |
| `scores_qwen25vl3b_{base,base_1shot,qlora}.json` | same notebook, cell 5 | MecAgent metric per row (valid, iou, err) |
| `oneshot_example.json` | same notebook, cell 3 | one-shot example: train index and SHA-256 of the program |
| `steps/*.step` | same notebook, cell 5 | 88 generated solids, original GenCAD scale |
| `per_row_analysis.json` | `scripts/gencad_analyse.py` | sketch counts, lengths, features per row |
| `iou_shell_vs_filled.json` | `scripts/gencad_iou_filled.py` | MecAgent IoU vs filled-voxel IoU per row |
| `checker_{generated,reference}.jsonl` | `scripts/gencad_checker_bridge.py` | checker status, score, findings per part |
| `stop_rules/` | `scripts/gencad_stop_rules.py` | per-rule scores and `summary.json` |

Not committed: the untuned and one-shot raw generations (the one-shot file is 99 copies of a
training program; GenCAD-Code declares no license, so no dataset programs or images are in git)
and the QLoRA adapter (~130 MB, on Google Drive at `MyDrive/gencad/qwen_lora_adapter`).

Order: `gencad_reference.py` (sr env) → `gencad_analyse.py` → `gencad_iou_filled.py` and
`gencad_export_reference_steps.py` (a venv with cadquery + trimesh) → `gencad_checker_bridge.py
generated|reference` (sr env). Caches go to `data/gencad/` (gitignored).

## Running on free Colab (practical notes)

- **Each Google profile has its own Drive.** An adapter trained in one profile is invisible to a
  notebook in another (`Can't find 'adapter_config.json'`). Decide which profile runs the eval
  before training, or copy `MyDrive/gencad/qwen_lora_adapter/` across (check that
  `adapter_config.json` sits directly inside, not in a nested folder).
- **The free tier's daily GPU limit hit after ~3.5 h** (the training run), so the eval ran in a
  second profile. Generation and training resume from Drive after a disconnect.
- **Estimate eval time from the reference program length, not from the baseline run.** The
  untuned base answers with short JSON (100 rows in 34 min); the tuned model writes ~470-token
  programs at ~81 s per row (2 h 15 min). Runaway rows that hit `max_new_tokens` take 4–6 min each.
