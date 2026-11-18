# Defect-Head Real-CAD Negative Fine-Tuning Design

**Status:** done  
**Last verified:** 2026-10-25  
**Outcome:** negative; no holdout improvement and synthetic-defect regression. Production checkpoint unchanged.  
**Backlog:** `defect-head-real-cad-augmentation`

## Goal

Run one bounded A/B experiment to determine whether adding verified-clean real-CAD negative examples improves the graph-level defect head's false-positive behaviour on source-disjoint real CAD.

The experiment uses only the 12 existing local STEPs in `tests/data/real_eval/`. It changes only the defect head and does not replace the production checkpoint. A small holdout cannot establish production readiness or broad real-CAD generalization.

## Decisions and constraints

- Start from the current committed BRepSAGE checkpoint, preserved unchanged as the baseline.
- Fine-tune only the graph-level defect classifier; freeze the GraphSAGE encoder, refinement head, and complexity head.
- Use one fixed training configuration and one final holdout evaluation. Do not tune against the final holdout or iterate until results look favourable.
- Use a separate git worktree and branch for implementation. Do not modify either existing worktree or their uncommitted files.
- Write candidate weights and generated data to separate ignored paths. Do not overwrite `weights/brepnet.pt`, existing labels, or existing validation evidence.
- Do not modify README setup/demo material or the other session's active results-remediation files.
- Do not commit, push, archive, move, or delete anything without explicit user approval.

## Rejected alternatives

1. **Retrain the defect head and encoder from scratch:** more model freedom, but substantially greater overfitting risk with only a few real examples and weaker attribution to the new data.
2. **Full multi-task retraining:** rule-derived refinement labels and complexity proxies would also change, confounding the clean-negative experiment and potentially altering unrelated scoring behaviour.

## Data and label provenance

Inspect every candidate STEP with the deterministic geometry checks before assigning a training label. `clean` means **none of the three defect-head classes is present**: `open_shell`, `sliver_face`, or `self_intersection`. It does not mean the part has no FEA findings; thin walls, small features, or a low overall score alone do not disqualify it.

Exclude a part when inspection establishes one of those three defect classes or when the required inspection cannot complete reliably. Record the evidence and reason. Never infer a clean label solely from the McMaster-Carr source or from the model's existing prediction. In particular, `SelfIntersectionSkipped`/`SelfIntersectionTimeout` is inconclusive, not a clean result; a clean label requires independent resolution of that class. The existing checks also do not provide a standalone exhaustive sliver-face certificate, so their coverage and any supplementary inspection must be recorded explicitly. Stop before training if fewer than two verified source families remain or a source-disjoint fit/holdout split cannot be formed.

The experiment manifest must record, per part:

- Stable source identifier and source-family identifier
- Source path and SHA-256
- Inspection status and evidence for the clean label or exclusion reason
- Split membership: `real_fit` or `final_holdout` (`real_fit` also supplies explicitly non-held-out development diagnostics)
- Face count and graph/label artifact paths when extraction succeeds

Existing real-CAD reports are presumed-clean diagnostic evidence, not sufficient labels by themselves. The pre-experiment inspection is the source of truth for this run.

## Source-family split

Assign families before training from part identity and geometry, not model outputs. Near-duplicate variants must remain on one side of the split. At minimum, review:

- The two `1483N...` mounted ball-bearing variants as one candidate family
- The `4519N...` T-slot bracket variants as one candidate family
- The two `43505K...`/`44685K...` pipe-flange parts for family membership based on actual geometry and provenance
- Other bearing and housing parts for shared source geometry rather than relying only on filename keywords

Reserve a small, source-disjoint final holdout before fitting. Use all remaining eligible real parts for fitting and development diagnostics. The exact membership is fixed in the manifest before candidate evaluation and must not be revised after seeing predictions.

No augmented or degraded variant of a real holdout part may enter training. Synthetic source variants remain governed by the existing `source_part` grouped split.

## Training design

Extract real-CAD graphs using the existing extractor and serialize them with explicit, externally verified `graph_label = 0` (`clean`). Reuse the existing dataset schema without silently treating missing labels as verified real-clean labels.

Fine-tune from the baseline checkpoint with only the defect-classification parameters trainable. The fitting batches must include retained synthetic defect examples as well as real clean negatives, preventing a trivial always-clean collapse. Synthetic examples continue to carry their injected ground-truth labels.

Choose one conservative epoch count, learning rate, batch composition, random seed, and synthetic grouped-validation split before final evaluation. Record them in the run metadata. Development metrics may diagnose optimization or obvious collapse but may not drive repeated final-holdout evaluations.

Save at least:

- Candidate checkpoint and immutable baseline reference/hash
- Training configuration and code revision
- Real-data manifest and split assignments
- Synthetic data version and source-grouped validation membership
- Parameter-freezing verification
- Training history and development metrics

Candidate artifacts live under a new ignored experiment-specific directory. Existing committed weights and metrics remain byte-for-byte unchanged.

## Evaluation

Evaluate baseline and candidate with identical preprocessing, model-selection logic, and inputs.

### Primary result

On the untouched real-CAD holdout, report per-part predicted class, confidence, and false-positive rate for the three defect classes. Do not report clean-only holdout accuracy as evidence of general defect-detection performance.

### Regression gate

On the same source-grouped synthetic validation set, compare four-class defect accuracy and per-class recall/accuracy for `clean`, `open_shell`, `sliver_face`, and `self_intersection`. Explicitly check for an always-clean or severe synthetic-defect recall collapse. There is no pretext that clean holdout improvement alone is sufficient.

### Secondary diagnostics

Report real fitting/development predictions and confidence changes, clearly marked non-held-out. Include extraction/inspection exclusions, skipped files, and errors in the denominator discussion rather than silently dropping them.

The tiny final holdout supports only a directional finding about this experiment. Confidence intervals or strong statistical claims are not required and must not be used to imply precision the sample cannot support.

## Completion and stopping rule

Run the fixed experiment once and publish the result whether positive, negative, or inconclusive. Stop after the single final-holdout comparison. Do not adjust the split, hyperparameters, or training mixture in response to final-holdout results.

The production checkpoint is not promoted in this task. Any later promotion requires separate review, a stronger real-CAD dataset, and explicit approval.

Document results in a new experiment-specific file under `docs/validation/`; update backlog status only after the experiment is actually complete and without disturbing parallel edits.

## Implementation boundaries and tests

Keep changes limited to explicit real-clean graph/label preparation, source-family manifest/splitting, defect-head-only fine-tuning, and A/B evaluation support. Reuse existing graph extraction, dataset loading, model, and inference interfaces where practical.

Add focused tests for:

- Real-clean labels requiring explicit verified provenance; missing labels cannot silently become verified negatives
- Source-family disjointness, including near-duplicate variants and exclusion of holdout-derived samples
- Only defect-head parameters receiving gradients/updates; encoder and other heads remain unchanged
- Synthetic defect examples remaining in the fitting mixture
- Baseline and candidate evaluation resolving their intended checkpoints
- Metrics distinguishing clean-only false-positive rate from four-class synthetic validation performance
- Malformed manifests, missing files, duplicate source IDs, and incomplete inspection failing explicitly

Run targeted tests and the relevant ML regression suite with `C:\mm\sr\python.exe`. Preserve the baseline artifact and compare it against the candidate on identical fixtures before making any improvement claim.

## Expected deliverables

1. Reviewed real-CAD inspection and source-family manifest
2. Minimal tested data-preparation, frozen-defect-head training, and A/B evaluation support
3. One baseline/candidate experiment with synthetic regression evidence
4. Honest validation report and backlog update reflecting the observed outcome
5. No production checkpoint replacement and no changes to the other session's active work
