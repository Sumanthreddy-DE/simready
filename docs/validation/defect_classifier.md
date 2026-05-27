# BRepSAGE Defect Classifier — Honest Results

**Date:** 2026-05-26
**Model:** `BRepSAGE-multitask` (2-layer GraphSAGE encoder over B-Rep face-adjacency graphs, hidden_dim=32, 3 heads). Checkpoint + numbers tracked at `weights/brepnet.pt` + `weights/metrics.json`.
**Why this doc exists:** the original per-face "refinement" head was trained on `rule_per_face > 0.5` — a deterministic function of the same OCC features the GNN ingests, so its 97.5%/100% numbers were circular *and* measured on a leaky random split. This run adds a **non-circular** graph-level head and reports it on a **leakage-free** split.

## What changed

1. **New head — graph-level defect classification.** Global-mean-pool the face embeddings → classify the part as one of `{clean, open_shell, sliver_face, self_intersection}`. The label is the **injected ground-truth defect tag** from `scripts/generate_degraded_steps.py` (`.tags.json`), *not* the rule layer. Non-circular by construction.
2. **Dataset.** 500 clean parametric + 600 degraded (200 each defect class) = 1100 graphs, labeled by `scripts/auto_label.py` (now reads the tag sidecars).
3. **Leakage-free split.** `split_train_val_by_source` keeps every variant of a base part on one side, so a degraded variant and its clean parent never straddle train/val. Without this, the model memorizes part geometry and the held-out number is inflated.

## Results (source-grouped held-out, n_val = 205 graphs)

| Metric | Value |
|---|---|
| **Defect classification accuracy (4-class)** | **0.756** |
| — clean | 0.870 |
| — sliver_face | 1.000 |
| — open_shell | 0.571 |
| — self_intersection | 0.371 |

Majority-class baseline (always predict "clean", 500/1100) ≈ 0.45; uniform ≈ 0.25. So 0.756 is a real lift, honestly measured.

## Honest gaps (do not paper over)

- **self_intersection (0.371) is weak.** The defect is an overlapping translated copy packaged as a Compound sibling. The encoder has no *geometric-overlap* feature — only per-face surface type, area, normal, curvature, UV extents, and topology. It sees doubled faces but cannot reliably tell overlap from a legitimately busy part. Fixing this needs an interference/penetration feature, not more data.
- **open_shell (0.571) is moderate.** A single removed face is a subtle topological signal (one face with reduced adjacency).
- **sliver_face (1.000) is easy** because the sibling sliver adds distinctive tiny-area faces the pooled embedding picks up immediately — arguably the least interesting class.

## The circular head, on the same honest split (for contrast)

The old refinement head, re-measured on the source-grouped split: **acc 0.848, precision 0.944, recall 0.487**. On the earlier *random* split of parametric-only it reported acc 0.975 / precision 1.000 / recall 0.870, and on real-ish fixtures (`weights/eval_fixtures.json`) it collapses to recall 0.231. Treat the grouped-split numbers as the honest ones; keep the head only as a per-face rule-approximator output.

## Reproduce

```powershell
$env:PYTHONPATH = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady"
# 1. degraded STEPs (200 inputs x 3 defects = 600)
C:\mm\sr\python.exe scripts/generate_degraded_steps.py --input data/parametric --output data/parametric_degraded --max-inputs 200
# 2. label clean + degraded into one manifest (graph_label from tags)
C:\mm\sr\python.exe scripts/auto_label.py data/parametric data/labels_combined --extra-inputs data/parametric_degraded
# 3. train (source-grouped split by default)
C:\mm\sr\python.exe scripts/train.py data/labels_combined weights --epochs 15
```

## Next

- Real-CAD eval: run the trained defect head against the held-out `tests/data/real_eval/` set (user downloading SimJEB/GrabCAD STEPs) to see if it generalizes beyond synthetic degradations — the true test.
- An interference feature for `self_intersection` if that class matters for the demo.
