# Defect Head — Real-CAD Clean-Negative Experiment v1

**Date:** 2026-10-25  
**Experiment:** `real_clean_v1`  
**Outcome:** **Negative — no held-out improvement and substantial synthetic-defect regression.**  
**Production checkpoint:** unchanged.

## Scope and claim

This was one bounded A/B experiment: fine-tune only the graph-level defect head with a verified real-CAD clean negative while retaining synthetic examples. It was not a full multi-task retrain and does not establish real-CAD generalization.

Only **2 of 12** local real STEPs passed all three class-specific inspections. The experiment therefore has **one real fitting part and one real final-holdout part**. A 1/1 holdout result is a directional diagnostic, not a statistically meaningful estimate. No hyperparameter or split changes were made after viewing the holdout result.

## Data inspection and split

The inspection required explicit completed evidence. A missing finding alone was not treated as proof of absence. Open topology checks include boundary and non-manifold edges; self-intersection skips/timeouts remain unknown; the `sliver_face` evidence is specific to the trained thin-sibling-solid class (`check_thin_solid`), not a general certificate against every possible sliver face.

| Role | Part | Family | Faces | Open | Sliver class | Self-intersection |
|---|---|---|---:|---|---|---|
| Real fit | `7192K47_Ultra-Corrosion-Resistant Mounted 316 Stainless Steel Ball Bearing` | `mcmaster_7192K47` | 95 | absent | absent | absent |
| Final holdout | `33125T73_Wraparound 90 Degree Strut Channel Bracket` | `mcmaster_33125T73` | 34 | absent | absent | absent |

The remaining 10 parts were excluded: 9 had inconclusive self-intersection evidence and `9734K17_Flange-Mounted Linear Bearing Housing` had self-intersection present. They were not silently removed from the denominator discussion or repurposed as training data.

Inspection evidence: `data/real_clean_v1/inspection.json` (ignored). Reviewed split: `data/real_clean_v1/manifest.json` (ignored). Prepared graphs and byte-level provenance: `data/real_clean_v1/dataset/` (ignored).

## Fixed training configuration

- Baseline: `weights/brepnet.pt`, SHA-256 `c225cca00f7a7b9a56c9ede0f04dabb3c0a20890800590d7519482cc0e03c61e`
- Candidate: `weights/experiments/real_clean_v1/candidate.pt`, SHA-256 `3a4e37e7dbb93dee40d104ff09e5cc650068809b6d7b0b8ca278c801220786c2`
- Encoder, refinement head, and complexity head frozen; only defect-head parameters optimized
- Synthetic dataset: `data/labels_combined_v2`, source-grouped split, 471 validation graphs
- Real fit graphs mixed with synthetic fit graphs; no real holdout data read during training
- 10 epochs, learning rate `1e-4`, batch size 16, seed `20260513`, real sampling mass 0.25
- Candidate and evidence stored separately under `weights/experiments/real_clean_v1/`; production weights were not replaced

The worktree contained uncommitted experiment code, so `config.json` records the Git revision plus dirty-tree status, per-source hashes/status, and tracked-diff hash. It does not claim that the base commit alone reproduces the code.

## Primary result — untouched real holdout

The final evaluation ran once after checkpoint and dataset hash verification.

| Model | Holdout part prediction | Confidence | Clean false-positive rate |
|---|---|---:|---:|
| Baseline | `open_shell` | 0.999998 | 1/1 = 1.00 |
| Candidate | `open_shell` | 0.999162 | 1/1 = 1.00 |

**There was no held-out improvement.** Both models confidently classified the verified-clean bracket as `open_shell`.

## Synthetic regression gate

Identical 471 source-grouped synthetic validation graphs were used for both models.

| Metric | Baseline | Candidate |
|---|---:|---:|
| Four-class defect accuracy | 0.686 | 0.643 |
| Clean per-class accuracy | 0.679 | 0.994 |
| `open_shell` per-class accuracy | 0.856 | 0.404 |
| `sliver_face` per-class accuracy | 1.000 | 0.990 |
| `self_intersection` per-class accuracy | 0.212 | **0.000** |

The candidate's higher synthetic clean accuracy came with severe damage to defect classes. `self_intersection` collapsed to **0/104 correct**, and `open_shell` fell to **42/104 correct**. This is a clean-preference tradeoff, not a successful defect-detector improvement. It also reinforces the existing finding that `self_intersection` needs a better interference signal, not merely more clean negatives.

## Non-held-out fit diagnostic

On the real fitting bearing, baseline predicted `open_shell` with confidence 0.850; candidate predicted `open_shell` with confidence 0.523 and increased clean probability from 0.020 to 0.370. This part was used in fitting, so this change is **not** a generalization result and is not reported as a clean false-positive metric.

## Conclusion and next decision

The one-real-negative, defect-head-only fine-tune **did not improve the untouched real holdout and materially regressed synthetic defect recognition**. Do not promote the candidate checkpoint.

The useful outcome is a bounded negative result plus reusable, hash-pinned experiment infrastructure. The next meaningful attempt needs a larger, independently verified real-CAD dataset with both clean and defective examples and enough source families for a nontrivial holdout. Repeating this same one-part strategy with tuned hyperparameters would risk overfitting and is not justified by this evidence.

Raw run records: `weights/experiments/real_clean_v1/{config,history,synthetic_split,evaluation}.json` (ignored). No existing README or prior real-CAD validation tables were edited.
