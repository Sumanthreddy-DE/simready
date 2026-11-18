# Defect-Head Real-CAD Negative Fine-Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one source-disjoint A/B experiment measuring whether verified real-CAD clean negatives improve a frozen-encoder defect head without collapsing synthetic defect recognition.

**Architecture:** A versioned manifest is the gate between OCC inspection and explicitly labeled real graphs. A separate experiment module freezes all non-defect parameters, mixes real clean samples with retained synthetic samples, and writes candidate artifacts to ignored storage. A single evaluation entry point compares baseline and candidate on the frozen real holdout and identical synthetic validation graphs; production inference and weights remain unchanged.

**Tech Stack:** Python 3.10 (`C:\mm\sr\python.exe`), pythonocc-core 7.9, PyTorch 2.12 CPU, PyG 2.7, pytest, JSON/JSONL experiment records.

**Status:** done  
**Last verified:** 2026-10-25  
**Outcome:** negative; one-fit/one-holdout candidate left holdout FP at 1/1 and regressed synthetic defect classes. Production checkpoint unchanged. Implementation and report are on `experiment/defect-real-clean` (`f39fe93`).  
**Design:** `docs/exec-plans/active/2026-10-25-defect-head-real-cad-design.md`

---

## Global constraints

- Do not modify either existing worktree or their uncommitted files. Execute in a new worktree created from `origin/main` after inspecting `git fetch origin` and confirming the base with the user.
- Do not commit or push without explicit user approval for that commit/push. Every commit below is an optional gated checkpoint, not permission to commit.
- Do not touch README setup/demo files, generation code/UI, `docs/validation/reproduce-results.md`, `docs/validation/geometry_gen_eval.md`, or generation-gate evidence.
- Do not overwrite `weights/brepnet.pt`, its adjacent metrics, existing labels, or existing real-CAD reports. Candidate outputs go to `weights/experiments/real_clean_v1/` and graphs/manifests to `data/real_clean_v1/`.
- No final-holdout predictions may be inspected before Task 6. Development predictions on `real_fit` are allowed only after the manifest is frozen.
- `SelfIntersectionSkipped` and `SelfIntersectionTimeout` are inconclusive. Existing rule checks alone do not certify sliver absence. Any unresolved class excludes the part.
- If fewer than two independently verified source families remain, stop before training and record an inconclusive data-coverage result. Never weaken labels to make the experiment runnable.
- Use `$env:PYTHONPATH = <absolute experiment worktree>` before Python commands. Never read `.env`.
- Preserve line endings on scripted edits; use the Edit/Write tools rather than PowerShell text redirection.

## File map

| File | Responsibility |
|---|---|
| `simready/ml/real_clean.py` | Pure-Python manifest validation, family-disjoint splitting, explicit clean-label serialization, and clean-only FP metrics |
| `simready/ml/defect_finetune.py` | Checkpoint loading, non-defect freezing, mixed fitting, frozen-parameter assertions, and four-class defect evaluation |
| `scripts/inspect_real_clean.py` | Guarded OCC evidence extraction; never auto-certifies inconclusive checks |
| `scripts/prepare_real_clean.py` | Converts a reviewed manifest into explicit real graph/label artifacts |
| `scripts/finetune_defect_real_clean.py` | CLI for the single fixed fine-tuning run and metadata |
| `scripts/eval_defect_real_clean.py` | One controlled baseline/candidate comparison and JSON report |
| `tests/test_real_clean.py` | Manifest, split, provenance, and FP-metric unit tests |
| `tests/test_defect_finetune.py` | Frozen-parameter, mixture, checkpoint-selection, and metric unit tests |
| `data/real_clean_v1/` | Ignored reviewed manifest, inspection evidence, graphs, and labels |
| `weights/experiments/real_clean_v1/` | Ignored candidate checkpoint and run/evaluation JSON |
| `docs/validation/defect_head_real_clean_v1.md` | Final experiment-specific evidence and limitations |

## Fixed experiment configuration

Lock these values before implementation and do not tune them against holdout results:

```python
EXPERIMENT_ID = "real_clean_v1"
BASELINE = Path("weights/brepnet.pt")
SYNTHETIC_DATASET = Path("data/labels_combined_v2")
REAL_DATASET = Path("data/real_clean_v1/graphs")
OUTPUT_DIR = Path("weights/experiments/real_clean_v1")
SEED = 20260513
EPOCHS = 10
LEARNING_RATE = 1e-4
BATCH_SIZE = 16
VAL_RATIO = 0.2
# Repeat real clean graphs to approximately one quarter of each fitting epoch,
# never replace synthetic examples. Oversampling is fit-only and deterministic.
REAL_SAMPLE_WEIGHT = 0.25
```

Use a deterministic `torch.utils.data.WeightedRandomSampler` with `replacement=True`, `num_samples=len(synthetic_fit) + ceil(REAL_SAMPLE_WEIGHT * len(synthetic_fit))`, synthetic weight `1.0`, and real weight chosen so total real draw mass is `REAL_SAMPLE_WEIGHT * len(synthetic_fit)`. The real holdout is never passed to the trainer. Validation uses the unmodified source-grouped synthetic split; real fit samples are diagnostics only.

### Task 1: Create the isolated execution workspace

**Files:**
- No source edits

- [ ] **Step 1: Fetch and inspect branch ancestry**

```powershell
git fetch origin
git status --short --branch
git worktree list
git log --oneline -5 origin/main
```

Expected: the two pre-existing worktrees remain registered; no checkout, reset, clean, stash, merge, or branch-pointer change occurs.

- [ ] **Step 2: Ask approval for the exact new worktree and branch**

Propose `C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady-real-clean` and branch `experiment/defect-real-clean` based on `origin/main`. Explain that this directory/branch creation is a git mutation requiring the user's explicit approval. Do not create it until approved.

- [ ] **Step 3: Create the worktree using the worktree skill**

Invoke `superpowers:using-git-worktrees`, then after approval run the exact approved command, expected to be:

```powershell
git worktree add -b experiment/defect-real-clean "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady-real-clean" origin/main
```

Expected: a third clean worktree on the new branch; original worktree status is unchanged.

- [ ] **Step 4: Verify isolation and local inputs**

In the new worktree:

```powershell
git status --short --branch
Test-Path -LiteralPath "data/labels_combined_v2/manifest.json"
Test-Path -LiteralPath "tests/data/real_eval"
```

Expected: clean new branch. Because data and real STEPs are gitignored, either local-data check may be false. If false, do not copy from another worktree automatically: report the missing inputs and ask the user to approve a read-only-source/copy-only-into-new-worktree step with SHA-256 verification.

### Task 2: Manifest schema and family-disjoint data selection

**Files:**
- Create: `simready/ml/real_clean.py`
- Create: `tests/test_real_clean.py`

- [ ] **Step 1: Write failing manifest-validation tests**

```python
import json
import pytest
from simready.ml.real_clean import load_manifest, split_real_samples


def entry(source_id="part-a", family="family-a", split="real_fit"):
    return {
        "source_id": source_id,
        "family_id": family,
        "split": split,
        "sha256": "a" * 64,
        "inspection": {
            "open_shell": "absent",
            "sliver_face": "absent",
            "self_intersection": "absent",
        },
    }


def write_manifest(tmp_path, rows):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"experiment": "real_clean_v1", "parts": rows}), encoding="utf-8")
    return path


def test_only_explicitly_verified_clean_parts_are_eligible(tmp_path):
    path = write_manifest(tmp_path, [entry()])
    rows = load_manifest(path)
    assert rows[0].graph_label == 0
    for field in ("open_shell", "sliver_face", "self_intersection"):
        row = entry()
        row["inspection"][field] = "unknown"
        with pytest.raises(ValueError, match=field):
            load_manifest(write_manifest(tmp_path, [row]))
        row["inspection"][field] = "present"
        with pytest.raises(ValueError, match=field):
            load_manifest(write_manifest(tmp_path, [row]))


def test_manifest_rejects_duplicates_bad_hash_split_and_empty_family(tmp_path):
    variants = [
        [entry(), entry()],
        [entry(sha256="x")],
        [entry(split="validation")],
        [entry(family="")],
    ]
    for rows in variants:
        with pytest.raises(ValueError):
            load_manifest(write_manifest(tmp_path, rows))


def test_family_split_never_mixes_fit_and_holdout(tmp_path):
    rows = [
        entry("part-a", "family-a", "real_fit"),
        entry("part-b", "family-b", "final_holdout"),
        entry("part-c", "family-b", "real_fit"),
    ]
    with pytest.raises(ValueError, match="family-b"):
        split_real_samples(load_manifest(write_manifest(tmp_path, rows)))
```

Also test a valid four-family fixture with one family held out; assert returned fit IDs and holdout IDs exactly match the manifest. Expected initial failure: module does not exist.

- [ ] **Step 2: Run RED**

```powershell
C:\mm\sr\python.exe -m pytest tests/test_real_clean.py -q
```

Expected: collection failure for missing `simready.ml.real_clean`.

- [ ] **Step 3: Implement the minimal manifest model and splitter**

Use frozen dataclasses and stdlib only. Public interfaces:

```python
@dataclass(frozen=True)
class RealCleanSample:
    source_id: str
    family_id: str
    split: str
    sha256: str
    inspection: dict[str, str]
    graph_label: int = 0


def load_manifest(path: Path) -> list[RealCleanSample]: ...
def split_real_samples(samples: list[RealCleanSample]) -> tuple[list[RealCleanSample], list[RealCleanSample]]: ...
```

`load_manifest` requires experiment ID `real_clean_v1`, nonempty unique source/family IDs, split in `{"real_fit", "final_holdout"}`, exactly 64 lowercase hexadecimal SHA characters, and every inspection field exactly `absent`. Any `present`, `unknown`, `skipped`, `timeout`, missing, or other value raises `ValueError` naming the source and field. This loader intentionally represents only the training-eligible manifest; raw inspected/excluded parts live in a separate evidence JSON and cannot be silently promoted.

`split_real_samples` rejects a family assigned to both splits, requires at least one fit and one holdout family, and returns fit/holdout lists in manifest order without mutating inputs.

- [ ] **Step 4: Run GREEN and isolation checks**

```powershell
C:\mm\sr\python.exe -m pytest tests/test_real_clean.py -q
```

Expected: all manifest tests pass.

- [ ] **Step 5: Optional approval-gated commit**

Ask permission before staging only these two files. Suggested message: `feat: validate real-clean experiment manifests`. Do not commit without approval.

### Task 3: Guarded inspection and explicit graph preparation

**Files:**
- Modify: `simready/ml/real_clean.py`
- Create: `scripts/inspect_real_clean.py`
- Create: `scripts/prepare_real_clean.py`
- Modify: `tests/test_real_clean.py`

- [ ] **Step 1: Add failing clean-label and clean-FP tests**

```python
from simready.ml.real_clean import build_real_labels, clean_false_positive_rate


def test_real_labels_carry_provenance_not_implicit_default(tmp_path):
    sample = load_manifest(write_manifest(tmp_path, [entry()]))[0]
    graph = type("Graph", (), {"node_features": [{"face_index": 0}]})()
    labels = build_real_labels(sample, graph)
    assert labels == {
        "face_count": 1,
        "indices": [0],
        "graph_label": 0,
        "graph_label_name": "clean",
        "label_source": "reviewed_real_clean_v1",
        "source_id": "part-a",
        "family_id": "family-a",
        "source_sha256": "a" * 64,
    }


def test_clean_false_positive_rate_counts_each_defect_class():
    rows = [
        {"predicted_defect": "clean"},
        {"predicted_defect": "open_shell"},
        {"predicted_defect": "sliver_face"},
    ]
    result = clean_false_positive_rate(rows)
    assert result == {"flagged": 2, "total": 3, "rate": 2 / 3}
    with pytest.raises(ValueError, match="total"):
        clean_false_positive_rate([])
```

Expected failure: functions do not exist.

- [ ] **Step 2: Implement serialization and metric helpers**

`build_real_labels(sample, graph)` derives sorted integer face indices from graph nodes, requires at least one node, and writes only graph-level clean labels plus provenance. It deliberately omits refinement/complexity targets because those heads are frozen and real labels are not being trained.

`clean_false_positive_rate(rows)` requires nonempty predictions, validates every `predicted_defect` against `DEFECT_CLASSES`, counts every non-clean class as a false positive, and returns the exact schema above. It must not name this metric accuracy.

- [ ] **Step 3: Implement guarded OCC inspection**

`scripts/inspect_real_clean.py --input tests/data/real_eval --output data/real_clean_v1/inspection.json` must:

- Enumerate case-insensitively deduplicated STEP files and hash source bytes.
- Validate STEP load and BRep validity; invalid inputs are excluded.
- Run inspection in a killable spawn child, reusing the process pattern in `scripts/eval_real_cad.py`, with default 60-second timeout.
- Record `OpenBoundaries`, `PotentialGaps`, `SelfIntersection`, `SelfIntersectionSkipped`, `SelfIntersectionTimeout`, `ThinSolid`, and graph extraction errors verbatim as evidence.
- Mark `self_intersection` `unknown` for skipped/timeout results; never translate them to `absent`.
- Mark open shell `present` for `OpenBoundaries`/`PotentialGaps`.
- Treat sliver status as `unknown` unless a documented supplementary inspection actually covers thin faces/solids. `ThinSolid` absent alone is not exhaustive sliver-face certification.
- Write evidence only. It must not create an eligible manifest or infer labels from catalog names or existing ML predictions.

The reviewer must inspect geometric evidence and create the eligible manifest explicitly. Unreviewed evidence cannot pass `load_manifest`.

- [ ] **Step 4: Implement graph preparation and integrity checks**

`scripts/prepare_real_clean.py --manifest data/real_clean_v1/manifest.json --input tests/data/real_eval --output data/real_clean_v1/graphs` must load the strict manifest, locate exactly one STEP per `source_id`, recompute SHA-256 and require equality, extract a nonempty graph, and write:

```text
<source_id>.graph.json
<source_id>.labels.json
manifest.json
```

The output manifest entries include `status: ok`, `stem`, `source_id`, `family_id`, `split`, `face_count`, `graph_label: 0`, and `graph_label_name: clean`. Reuse `simready.ml.dataset.load_sample` compatibility: refinement/complexity maps may be empty because no loss is computed for those heads. Refuse nonempty output directories to prevent accidental overwrites.

- [ ] **Step 5: Run unit tests and inspect real evidence**

```powershell
C:\mm\sr\python.exe -m pytest tests/test_real_clean.py -q
$env:PYTHONPATH = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady-real-clean"
C:\mm\sr\python.exe scripts/inspect_real_clean.py --input tests/data/real_eval --output data/real_clean_v1/inspection.json
```

Expected: unit tests pass; inspection JSON records all 12 source hashes and explicit coverage/unknowns. Do not claim all parts clean.

- [ ] **Step 6: Review families and stop if coverage is insufficient**

Use filenames, source provenance, geometry summaries, and inspection evidence to assign family IDs. Keep the known variant groups together. Create the strict manifest only for independently resolved clean parts. Require at least two eligible source families and nonempty fit/holdout sets. Otherwise stop and document `docs/validation/defect_head_real_clean_v1.md` as inconclusive due to verified-data coverage; do not train.

- [ ] **Step 7: Prepare and verify graph artifacts**

```powershell
C:\mm\sr\python.exe scripts/prepare_real_clean.py --manifest data/real_clean_v1/manifest.json --input tests/data/real_eval --output data/real_clean_v1/graphs
```

Expected: one graph/label pair per eligible part, all source hashes match, no holdout family appears in fit, and every output label has explicit `label_source: reviewed_real_clean_v1`.

- [ ] **Step 8: Optional approval-gated commit**

Ask permission before staging only source/scripts/tests from this task. Local evidence/manifests remain ignored. Suggested message: `feat: prepare verified real-clean graph data`.

### Task 4: Frozen defect-head training with synthetic retention

**Files:**
- Create: `simready/ml/defect_finetune.py`
- Create: `tests/test_defect_finetune.py`

- [ ] **Step 1: Write failing freeze and mixed-fitting tests**

Construct `BRepSAGE(ModelConfig(hidden_dim=4, num_layers=2, dropout=0.0))` and deterministic tiny `Data` graphs with `graph_label` values covering all four classes. Tests:

```python
def test_only_defect_head_is_trainable():
    model = BRepSAGE(ModelConfig(hidden_dim=4, dropout=0.0))
    freeze_non_defect_parameters(model)
    assert all(p.requires_grad for p in model.defect_head.parameters())
    frozen = [p for n, p in model.named_parameters() if not n.startswith("defect_head.")]
    assert frozen and not any(p.requires_grad for p in frozen)


def test_training_does_not_change_frozen_parameters(tiny_fit_data):
    model = BRepSAGE(ModelConfig(hidden_dim=4, dropout=0.0))
    before = {n: p.detach().clone() for n, p in model.named_parameters() if not n.startswith("defect_head.")}
    history = finetune_defect_head(
        model, tiny_fit_data, tiny_fit_data,
        epochs=1, lr=1e-3, batch_size=2, seed=7,
    )
    assert history
    for name, parameter in model.named_parameters():
        if not name.startswith("defect_head."):
            assert torch.equal(parameter.detach(), before[name])


def test_fit_mix_rejects_missing_real_or_synthetic_defects(real_and_synthetic_data):
    with pytest.raises(ValueError, match="real"):
        build_fit_weighting(real_and_synthetic_data[:1], [])
    with pytest.raises(ValueError, match="defect"):
        build_fit_weighting([], [g for g in real_and_synthetic_data if g.graph_label.item() == 0])
```

Add an optimizer test proving `configure_defect_optimizer` contains only defect-head parameters. Use pure synthetic graphs for unit tests; no OCC or real holdout.

- [ ] **Step 2: Run RED**

```powershell
C:\mm\sr\python.exe -m pytest tests/test_defect_finetune.py -q
```

Expected: missing-module collection failure.

- [ ] **Step 3: Implement the minimal training API**

Public interfaces:

```python
def load_brepsage_checkpoint(path: Path) -> BRepSAGE: ...
def freeze_non_defect_parameters(model: BRepSAGE) -> None: ...
def configure_defect_optimizer(model: BRepSAGE, lr: float) -> Adam: ...
def build_fit_weighting(real_fit: list[Data], synthetic_fit: list[Data], real_mass: float = 0.25) -> tuple[list[Data], list[float]]: ...
def evaluate_defect(model: BRepSAGE, data: list[Data], batch_size: int = 16) -> dict: ...
def finetune_defect_head(model: BRepSAGE, real_fit: list[Data], synthetic_fit: list[Data], *, epochs: int, lr: float, batch_size: int, seed: int, real_mass: float = 0.25) -> list[dict]: ...
```

`build_fit_weighting` requires nonempty real and synthetic lists and all four synthetic labels present. It returns synthetic entries followed by real entries (attribute `is_real_clean=True` only on real samples), with weights implementing the fixed real mass. Reject nonpositive `real_mass` and real entries whose label is not clean.

`finetune_defect_head` uses cross-entropy only, `WeightedRandomSampler`, CPU, deterministic seed, model.train(), and records per-epoch fitting loss plus synthetic-validation `evaluate_defect`. It never calculates refinement/complexity loss. Assert after every optimizer step that non-defect tensors are byte-identical to their initial values; raise if violated.

`evaluate_defect` returns `samples`, `accuracy`, `per_class_accuracy`, `per_class_samples`, and per-sample `source_id`, `target`, `prediction`, `confidence`, `probabilities`. It never derives real holdout accuracy from clean-only rows.

- [ ] **Step 4: Run GREEN and existing ML tests**

```powershell
C:\mm\sr\python.exe -m pytest tests/test_real_clean.py tests/test_defect_finetune.py tests/test_brepnet.py tests/test_defect_head.py -q
```

Expected: all pass; no production model/dataset files changed.

- [ ] **Step 5: Optional approval-gated commit**

Ask permission before staging only the new module/tests. Suggested message: `feat: add frozen defect-head fine-tuning`.

### Task 5: Single-run training and evaluation CLIs

**Files:**
- Modify: `.gitignore`
- Create: `scripts/finetune_defect_real_clean.py`
- Create: `scripts/eval_defect_real_clean.py`
- Modify: `tests/test_defect_finetune.py`

- [ ] **Step 1: Add failing explicit-checkpoint evaluation test**

Write two tiny checkpoints whose defect biases force different classes on one fixed graph. Call `compare_checkpoints(baseline_path, candidate_path, real_rows, synthetic_rows)` and assert output model sections contain the exact resolved checkpoint paths and expected predictions. Also assert calling with a missing checkpoint raises `FileNotFoundError`, never heuristic fallback.

- [ ] **Step 2: Implement explicit A/B comparison**

In `simready/ml/defect_finetune.py` add:

```python
def compare_checkpoints(baseline_path: Path, candidate_path: Path, real_data: list[Data], synthetic_val: list[Data]) -> dict: ...
```

Load both using `load_brepsage_checkpoint` and identical `evaluate_defect` settings. Return separate `baseline` and `candidate` sections with path, SHA-256, synthetic metrics, and per-real-source predictions. Add `clean_false_positive_rate` only for real rows explicitly marked `final_holdout`; the CLI supplies holdout data separately from real-fit diagnostics. Reject empty synthetic validation or real holdout.

- [ ] **Step 3: Implement fixed training CLI**

`scripts/finetune_defect_real_clean.py` has no tuning arguments beyond paths. It loads `data/labels_combined_v2`, splits synthetic data with existing `split_train_val_by_source(val_ratio=0.2, seed=20260513)`, loads only `real_fit` rows from the real graph manifest, verifies all four synthetic classes in synthetic fit, and runs the fixed 10 epochs / `1e-4` / batch 16 / seed `20260513` configuration.

Write `candidate.pt`, `config.json`, `history.json`, `synthetic_split.json` with source IDs and families, `baseline_sha256`, `code_revision`, and non-defect baseline/candidate tensor equality evidence. Refuse existing output files. Never copy the candidate over production weights.

- [ ] **Step 4: Implement one-shot evaluation CLI**

`scripts/eval_defect_real_clean.py --baseline weights/brepnet.pt --candidate weights/experiments/real_clean_v1/candidate.pt --output weights/experiments/real_clean_v1/evaluation.json` loads real fit and final holdout separately and the exact recorded synthetic validation IDs. It writes baseline/candidate synthetic metrics, final-holdout clean-FP rates and per-part probabilities, real-fit diagnostics marked `held_out: false`, and all skipped/excluded IDs from inspection evidence.

Refuse to run if `evaluation.json` already exists. This mechanically enforces one final evaluation rather than relying on intention.

- [ ] **Step 5: Add ignored artifact rules**

Append:

```gitignore
# Real-CAD clean-negative experiment; evidence and candidate weights stay local.
data/real_clean_v1/
```

`weights/*` already ignores `weights/experiments/`; verify with `git check-ignore -v weights/experiments/real_clean_v1/candidate.pt data/real_clean_v1/manifest.json`. Do not add negations for these artifacts.

- [ ] **Step 6: Run focused and regression tests**

```powershell
C:\mm\sr\python.exe -m pytest tests/test_real_clean.py tests/test_defect_finetune.py tests/test_brepnet.py tests/test_defect_head.py -q
git diff --check
git status --short
```

Expected: tests pass; diff contains only planned experiment files; real/candidate artifacts ignored.

- [ ] **Step 7: Optional approval-gated commit**

Ask permission before staging only planned tracked files. Suggested message: `feat: add one-shot real-clean defect experiment`.

### Task 6: Execute the frozen experiment once

**Files:**
- Create locally, ignored: `data/real_clean_v1/*`
- Create locally, ignored: `weights/experiments/real_clean_v1/*`
- Create: `docs/validation/defect_head_real_clean_v1.md`

- [ ] **Step 1: Record immutable baseline and source hashes**

Run SHA-256 over `weights/brepnet.pt`, real manifest, and every eligible STEP; verify they match the frozen manifest/config. Run:

```powershell
git rev-parse HEAD
git status --short
```

Expected: no unplanned source changes; baseline remains the original committed checkpoint.

- [ ] **Step 2: Run the fixed training command once**

```powershell
$env:PYTHONPATH = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady-real-clean"
C:\mm\sr\python.exe scripts/finetune_defect_real_clean.py
```

Expected: 10 epochs, candidate saved under experiment weights, all non-defect tensors equal baseline, synthetic fit retains all four classes, no final-holdout output.

- [ ] **Step 3: Inspect development-only evidence**

Inspect training loss, synthetic validation metrics, and optional real-fit predictions. Do not open final-holdout predictions and do not alter any hyperparameters. If optimization fails mechanically, record failure; do not silently rerun with different settings.

- [ ] **Step 4: Run final A/B evaluation exactly once**

```powershell
C:\mm\sr\python.exe scripts/eval_defect_real_clean.py --baseline weights/brepnet.pt --candidate weights/experiments/real_clean_v1/candidate.pt --output weights/experiments/real_clean_v1/evaluation.json
```

Expected: baseline and candidate evaluated on identical frozen holdout and synthetic validation graphs. A second invocation fails because output exists.

- [ ] **Step 5: Verify production artifact preservation**

Hash `weights/brepnet.pt` again and compare to Step 1. Run `git status --short` and confirm no production weights/metrics or parallel-session files changed.

- [ ] **Step 6: Write the honest result**

In `docs/validation/defect_head_real_clean_v1.md` include exact eligible/excluded counts and reasons, family memberships, fit/holdout IDs, fixed config, baseline/candidate hashes, per-part holdout predictions, clean-FP rates, synthetic four-class metrics/per-class values, non-held-out diagnostics label, and the narrow conclusion.

Use these outcome rules without forcing a positive narrative:

- Lower holdout FP plus no material synthetic per-class collapse: directional improvement on this tiny sample only.
- Lower holdout FP plus severe synthetic-defect collapse: rejected tradeoff/always-clean behaviour, not success.
- Same or worse holdout FP: negative result for this lever at this scale.
- Too few eligible families or mechanical failure: inconclusive, no model-quality claim.

Do not edit README or existing `real_eval*.md` tables. Do not promote candidate weights.

- [ ] **Step 7: Run final verification**

```powershell
C:\mm\sr\python.exe -m pytest tests/test_real_clean.py tests/test_defect_finetune.py tests/test_brepnet.py tests/test_defect_head.py -q
C:\mm\sr\python.exe -m pytest -q
git diff --check
git status --short
```

Record exact pass/skip/fail counts. Investigate failures before claiming completion; do not hide pre-existing failures.

- [ ] **Step 8: Update backlog without disturbing parallel work**

Move `defect-head-real-cad-augmentation` to `Doing` only while active. After the experiment, either close it with the exact observed scope or leave it open with this attempt recorded, following the existing pattern for honest negative results. Since state/backlog edits are conventionally main-owned and parallel work is active, present the proposed one-entry patch to the user rather than directly editing a busy shared file.

- [ ] **Step 9: Request review and separate commit approval**

Summarize evidence, test output, files changed, and remaining limitations. Invoke `superpowers:requesting-code-review`. Do not commit or push unless the user explicitly approves a separate commit operation.

## Plan self-review

- Spec coverage: explicit labels and exclusions (Tasks 2–3), family split (Tasks 2–3), frozen head and synthetic retention (Task 4), immutable baseline/candidate and one-shot holdout (Tasks 5–6), isolated worktree (Task 1), honest report/no promotion (Task 6).
- No placeholder hyperparameters or unspecified public interfaces remain.
- Type consistency: `RealCleanSample`, `Data`, `BRepSAGE`, and checkpoint paths are used consistently; real holdout is never a trainer argument.
- Coverage caveat: existing deterministic checks cannot certify every class on every real part; insufficient verified families is a stopping outcome, not permission to invent labels.
