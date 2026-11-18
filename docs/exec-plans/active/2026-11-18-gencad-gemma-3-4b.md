# GenCAD Gemma-3-4B Implementation Plan

> **For agentic workers:** Use `executing-plans` to implement this plan inline, task by task. Steps use checkbox (`- [ ]`) syntax. Read the experiment contract below before touching notebooks.

**Status:** paused
**Last verified:** 2026-11-18
**Stage:** planned and self-reviewed; user deferred execution on 2026-11-18. Implementation and GPU runs have not started. Resume through `BACKLOG.md` `apply-gencad-vlm-track` when the user requests execution; review this plan before implementing.
**Goal:** Evaluate untuned and QLoRA-tuned Gemma-3-4B on the same GenCAD-Code task used for Qwen, using the existing two notebooks on Kaggle or Colab, and publish the measured result regardless of outcome.
**Architecture:** Retain `gencad_baseline.ipynb` and `gencad_train_qwen.ipynb` as the evaluation and training entry points for both model families. Extract only GPU-independent configuration, artifact identity, and runtime-path logic into one small shared helper; bundle that helper into generated Kaggle submissions. Keep MecAgent scoring and existing Qwen artifacts intact.
**Tech stack:** Python, Unsloth `FastVisionModel`, Transformers, PEFT/TRL, CadQuery, MecAgent metric code, Kaggle CLI 2.2.5; existing Colab support retained.
**Spec:** This document's Experiment Contract, implementing `BACKLOG.md` `apply-gencad-vlm-track` and `docs/validation/gencad_eval.md` § Next steps.

## Verified starting point

- SP1 is already integrated locally: `main` contains `1e70789` and subsequent unrelated commits. Do not repeat its merge, reset branches, move its tags, or rerun its paid evaluations. Fetch before making a remote-publication claim.
- The two GenCAD notebooks unconditionally import `google.colab.drive`. They also hardcode `/content` for the metric clone and scorer, so changing `OUT` alone is insufficient.
- The evaluation notebook currently defaults to `SHOTS = 1`. Training uses Qwen-specific checkpoint, adapter and log names. Both need explicit run configuration before selecting Gemma.
- Evaluation currently deletes existing generation/score files if eval IDs differ. Replace that deletion with a manifest mismatch error; never erase prior experiments to resume a different one.
- Kaggle `/kaggle/working` is writable output, not automatic cross-session persistence. A later run needs an explicitly attached previous output/dataset and a writable copy of its checkpoint.
- Hugging Face API verified on 2026-11-18: `unsloth/gemma-3-4b-it-unsloth-bnb-4bit`, revision `316726ca0bd24aa323bfaf86e8a379ee1176d1fe`, `gated: false`. This verifies repository access, not GPU compatibility, quality, or license acceptance on the user's behalf.
- Existing notebooks choose the token budget from test-reference lengths and pick tokenizer-filtered training subsets. Those choices must be recorded; do not imply an identical Qwen/Gemma training set unless the actual saved row IDs match.
- `scripts/gencad_checker_bridge.py` directly imports pythonocc; the current OCP-only VPS environment is not proof the full checker bridge works there.

## Experiment Contract / Design

### Intent and approaches

This is a second-model image → CadQuery experiment, not a replacement of Qwen, the copilot model, or the `simready/gen/` typed DSL.

Chosen approach: parameterize the existing two notebooks, retaining their scoring flow, with a small shared runtime/configuration helper. Rejected: separate copied Gemma notebooks (duplicated scoring and resume logic drift) and a new training framework (unnecessary scope for one comparison). Kaggle is the requested GPU platform; Colab remains usable through explicit runtime detection.

### Fixed evaluation and training settings

- Dataset: `CADCODER/GenCAD-Code`; evaluate exactly its test `hundred_subset`, 100 unique rows. Pin and record the resolved dataset revision before official runs.
- Gemma base: the verified repository/revision above; base and adapter evaluations use the same base revision and configuration.
- Main comparison: `SHOTS = 0`, dataset prompt, greedy decoding, no stop-rule repair, no hidden retries of bad generations. One-shot and R1 stop-rule results, if run, are separate rows.
- Freeze `max_new_tokens = 1825` for the Gemma base/adapter pair, matching the recorded Qwen generation cap. Record tokenizer-specific truncation counts; equal token caps do not imply equal text capacity across tokenizers.
- MecAgent metric: preserve its implementation unchanged. Resolve the recorded historical `dc94ef8` to its full SHA and confirm the scoring functions before pinning; record the full revision and metric-file hashes. No silent fallback to moving HEAD.
- Report VSR, shell IoU over valid programs, and shell IoU with invalid programs counted as zero. Distinguish geometry failure, scoring failure, truncation, and infrastructure failure. Infrastructure errors do not become model scores.
- QLoRA: 6,000 train rows, seed 0, one epoch; frozen vision tower, language attention + MLP adapters, `r=16`, `alpha=16`, dropout 0; effective batch 8, learning rate `2e-4`, warmup 20, linear schedule, weight decay 0.01, checkpoint every 50 steps, two retained checkpoints. Preserve the existing FP16/BF16 hardware detection.
- Retain the existing training `max_length=2048` and 1,500-code-token eligibility limit initially, but prove with the Gemma processor that a complete image/prompt/target fits without dropping image tokens or truncating the target. If it does not, stop and explicitly revise the configuration before freezing train IDs; do not silently discard target suffixes.
- Prefer the original saved Qwen training row IDs if retrievable. If unavailable, freeze and publish the Gemma train-ID manifest before training, describe the subset difference, and avoid attributing cross-model changes solely to architecture. No dataset code/images committed publicly.
- Never silently lower dataset size, change epochs, switch the model, or trim long targets to overcome OOM. A failed five-row load/train smoke blocks the full job and produces an explicit configuration decision.

### Outputs, identity and persistence

Use separate model/run identities: `qwen25vl3b` and `gemma3_4b`; modes `base` and `qlora`. Colab's existing Qwen paths remain compatible. Gemma writes model-specific checkpoint, adapter, generation and score filenames beneath the existing output root.

Each job writes a manifest with run ID, mode, base ID/revision, adapter identity (if any), dataset/metric revisions, eval/train row IDs or their hashes, settings, dependency versions, GPU, and source commit. Resume requires a matching manifest; mismatch stops without changing old files.

Generated Kaggle upload payloads and downloaded results live under the existing gitignored `data/gencad/` tree. New paths there are explicitly proposed by this plan: `kaggle_jobs/` and `kaggle_outputs/`. Checkpoints remain private. Use private kernels and do not bake credentials into cells, metadata, outputs, or manifests.

### Success criteria

1. Both notebooks run configuration/path cells on Kaggle without importing Colab; Colab behavior remains valid.
2. A private Kaggle smoke actually runs on a GPU, writes a completion manifest, and its output is downloaded and checked locally. `kernels list --mine` alone establishes neither auth failure nor success.
3. Base and tuned results cover the same 100 eval IDs, use frozen settings, and have complete manifests. The training adapter can be loaded in a fresh evaluation session using attached output.
4. Results and reproduction steps are recorded in `docs/validation/gencad_eval.md`; README/backlog claims are updated only after corresponding evidence exists.

## Global constraints

- Planning does not authorize starting GPU jobs, installing global software, accepting licenses, committing, or pushing. Obtain approval for remote job launches; use existing credentials without reading their values.
- Implementation uses an isolated `gencad-gemma` branch/worktree if another session shares the repository. Preserve the two unrelated untracked project-understanding/walkthrough files.
- No new top-level directories. New artifact paths proposed above require approval of this plan before creation.
- No changes to SP1 prompts, scores, tags, or reward implementation.
- No claim that Gemma improves quality until its own base-vs-adapter results exist.
- Keep historical Qwen evidence and source programs separate from new output. No destructive cleanup of prior runs.

## File map

| File | Responsibility |
|---|---|
| `scripts/gencad_notebook_runtime.py` (new) | Lightweight runtime paths, model settings, manifests, safe resume; no GPU imports |
| `scripts/gencad_kaggle.py` (new) | Generate private Kaggle payload from canonical notebook + bundled helper; explicit owner/run arguments |
| `notebooks/gencad_baseline.ipynb` | Shared base/adapter evaluation; runtime-neutral metric clone/scorer paths |
| `notebooks/gencad_train_qwen.ipynb` | Shared Qwen/Gemma training; retain filename for existing readers |
| `tests/test_gencad_notebook_runtime.py` (new) | Real temporary-path/manifest tests and isolated notebook setup checks |
| `tests/test_gencad_kaggle.py` (new) | Payload generation, privacy and setting propagation tests |
| `docs/validation/gencad_eval.md`, `README.md`, `BACKLOG.md` | Measured results, reproduction and task status |

## Review focus

1. Kaggle output attachment is read-only: copy resume checkpoints into writable output and reject an unrelated model's checkpoint (Task 1 tests).
2. An existing generation file with changed eval IDs/settings must fail closed rather than delete outputs or silently skip rows (Tasks 1–2 tests).
3. Adapter loading uses the correct base revision and Gemma processor/chat template; base and adapter jobs cannot share an output filename (Task 2 tests + GPU smoke).
4. The remote notebook payload must contain its shared helper, not depend on a VPS import path or an unpushed GitHub branch (Task 3 tests).
5. Partial generation/scoring or upstream metric failure cannot produce a 100-row success claim; artifact coverage must match expected IDs (Task 4 acceptance).

---

### Task 1: Runtime paths and artifact identity

**Files:** Create `scripts/gencad_notebook_runtime.py`, `tests/test_gencad_notebook_runtime.py`.
**Interfaces:** `resolve_paths(runtime: str, output_root: Path | None = None) -> dict[str, Path]` returns `out`, `scratch`, `metric_repo`; `resolve_settings(model_family: str, mode: str) -> dict`; `check_run_manifest(path: Path, expected: dict) -> None` creates a new manifest or rejects differing settings; `prepare_resume(source: Path, destination: Path, expected: dict) -> Path` validates identity and copies a checkpoint to writable storage without mutating source.

- [ ] **Step 1: Write RED tests** using temporary roots and fake manifests, without Unsloth/torch imports:
  - Kaggle resolves output beneath `/kaggle/working/gencad`, scratch/metric paths beneath `/kaggle/working`; Colab uses mounted `/content/drive/MyDrive/gencad` and `/content` scratch.
  - Unknown runtime raises; explicit local root supports tests without mounting Drive.
  - Gemma base/QLoRA settings select the fixed revision and cap 1825, with distinct filenames; Qwen defaults preserve existing names.
  - Manifest mismatch raises and leaves generation/checkpoint bytes unchanged.
  - Read-only attached checkpoint is copied to writable output; mismatched base revision is rejected before copying.
- [ ] **Step 2: Run RED:** `python -m pytest tests/test_gencad_notebook_runtime.py -q` in the selected project interpreter. Expected: missing helper/import failure before implementation.
- [ ] **Step 3: Implement** the exact interfaces above with stdlib paths/JSON; mount Drive only in the Colab notebook branch, not at helper import.
- [ ] **Step 4: Run GREEN:** the same test command passes; verify helper import does not load torch, Unsloth, or Colab.
- [ ] **Step 5: Commit only if authorized:** helper and tests, message `feat(gencad): portable notebook paths and run manifests`.

### Task 2: Parameterize the existing evaluation and training notebooks

**Files:** Modify the two existing notebooks; extend `tests/test_gencad_notebook_runtime.py`.
**Consumes:** Task 1 settings/path/manifest interfaces.
**Produces:** The same canonical notebooks support explicit Qwen/Gemma and base/adapter configurations; no copied Gemma training/eval notebooks.

- [ ] **Step 1: Write RED tests** that parse notebook JSON, compile code cells, and execute setup/configuration with isolated runtime dependencies. Assert Kaggle never imports Colab; metric clone/scorer paths use resolved runtime paths; Qwen/Gemma outputs differ; changed eval IDs stop without deletion; adapter/base manifest mismatch prevents resume; saved scores require 100 unique expected IDs for official runs.
- [ ] **Step 2: Run RED:** `python -m pytest tests/test_gencad_notebook_runtime.py -q`; expect the existing unconditional Colab import/destructive reset or missing configuration to fail the new behavior tests.
- [ ] **Step 3: Implement** model-family/run-mode settings before side-effecting setup; replace every `/content` metric/scorer assumption, not just `OUT`. Keep model loading through `FastVisionModel`. Colab entry cells explicitly locate the helper in a checkout at the recorded source commit; generated Kaggle jobs use Task 3's embedded helper, with no moving-branch download. Record processor behavior and versions; verify Gemma image-first chat packing and complete target preservation with a GPU smoke rather than assuming Qwen tokenization is compatible. Preserve raw generation before fence stripping.
- [ ] **Step 4: Verify** notebook JSON validity, compile all code cells, run the setup tests, and inspect the diff for unchanged scorer math/training defaults. No stale notebook outputs or credentials in the diff.
- [ ] **Step 5: Commit only if authorized:** notebooks and tests, message `feat(gencad): parameterize shared notebooks for Gemma and Kaggle`.

### Task 3: Build and verify private Kaggle job payloads

**Files:** Create `scripts/gencad_kaggle.py`, `tests/test_gencad_kaggle.py`.
**Interfaces:** CLI accepts explicit `--owner`, `--job` (`smoke`, `base`, `train`, `qlora-eval`), `--output-dir`, and optional attached checkpoint source. It generates `kernel-metadata.json` plus a notebook whose initial cell embeds the canonical helper source. It prepares payloads only; upload/run is a separate command.

- [ ] **Step 1: Write RED tests:** private kernel metadata, GPU/internet enabled, explicit owner required, fixed Gemma revision, `SHOTS=0`, token cap 1825, bundled helper works without repo imports; QLoRA eval rejects missing adapter input. Smoke executes only GPU/model load plus a tiny inference/train check; no full 6,000-row run accidentally starts.
- [ ] **Step 2: Run RED:** `python -m pytest tests/test_gencad_kaggle.py -q`; expected missing script/interfaces.
- [ ] **Step 3: Implement** payload generation from the two canonical notebooks. Generate metadata in the requested directory only; never write home/global configuration or infer a username from secret files.
- [ ] **Step 4: Run GREEN** and verify generated notebook cell syntax. Check `kaggle kernels push --help`, `status --help`, and `output --help` before using flags (verified 2026-11-18: push `-p`, `-t`; output `-p`; status accepts `owner/slug`).
- [ ] **Step 5: After launch approval, run a private smoke.** Establish the real owner through account/profile information without displaying token contents. Use the exact metadata `id` for status/output commands. Verify `torch.cuda.is_available()`, actual GPU, one-image decoding, and a tiny backward/adapter-save-reload check; download and inspect its completion manifest. If authentication/phone verification/permission fails, record the exact error without prematurely diagnosing `Not found` as invalid credentials.
- [ ] **Step 6: Record smoke evidence** and commit the generator/tests only if authorized. No claim of cross-session resume until a second session has successfully loaded downloaded/attached adapter output.

### Task 4: Freeze manifests, run base → train → adapter evaluation, publish evidence

**Files:** Modify `docs/validation/gencad_eval.md`, `README.md`, `BACKLOG.md`; new model-tagged artifacts in existing `docs/validation/gencad/` after review.
**Consumes:** Shared notebooks, prepared Kaggle payloads, successful GPU smoke.
**Produces:** Gemma's own base-vs-QLoRA result and reproducible manifests.

- [ ] **Step 1: Freeze experiment inputs** before full GPU runs: dataset and model revisions, full metric SHA/hashes, eval IDs, train IDs, run settings. Retrieve the historical Qwen train-ID file if available; otherwise disclose unavailable exact subset parity. Do not tune prompts or the training recipe against held-out failures.
- [ ] **Step 2: Run untuned base evaluation** on exactly 100 IDs with `SHOTS=0`. Download and validate raw outputs, per-row scores, errors/truncations and manifest. Keep smoke outputs separate. Report infrastructure gaps rather than treating missing rows as model failures.
- [ ] **Step 3: Run QLoRA training** with the fixed recipe. Download checkpoints/adapter/logs after completion; confirm files and hashes locally. Record actual hardware, duration, optimizer steps and training-row count. An interrupted session is not a completed epoch.
- [ ] **Step 4: Run adapter evaluation in a fresh session** using explicitly attached output, same base revision, eval IDs, prompt, cap and scorer. Prove the adapter was loaded; compare base/adapter manifests and require 100 unique completed eval rows each.
- [ ] **Step 5: Publish base-vs-adapter VSR and IoU**, including invalid=0, hardware and all deviations. Keep historical Qwen rows unchanged and distinguish tokenization/subset/hardware differences from within-Gemma treatment effects. Report negative results as-is.
- [ ] **Step 6: Checker follow-up:** retain generated STEPs for the existing bridge. Execute it only in an environment that actually supports its pythonocc imports; if unavailable, mark checker results pending separately rather than claim OCP benchmark support implies pipeline compatibility. Generalizing the hardcoded Qwen bridge is a separate scoped follow-up if needed.
- [ ] **Step 7: Verification:** runtime/payload tests pass; notebook cells compile; manifests align; rows cover exactly the frozen 100 IDs; official score summaries recompute from per-row artifacts; inspect artifact values for secrets and unlicensed reference/training material before staging.
- [ ] **Step 8: Update backlog and README with measured evidence**, request final review of the experiment/implementation, and commit only approved files. Move this plan to completed only after its success criteria are met; otherwise leave explicit blocked/partial status with the next action.

## Self-review

- Scope: second-model GenCAD comparison; no SP1 integration redo or core DSL change.
- Coverage: Task 1 owns runtime/persistence identity; Task 2 owns both notebook paths and experimental configuration; Task 3 proves remote execution and payload self-containment; Task 4 owns data completeness and reported results.
- Interfaces: Task 2 imports Task 1 helper; Task 3 bundles that helper and consumes the canonical notebooks; Task 4 consumes Task 3 outputs and frozen manifests.
- Honest boundaries: model repository access is verified; Kaggle GPU access, Unsloth/Gemma runtime compatibility, historical Qwen train-ID availability, and cross-session checkpoint reuse remain execution gates.
- No automatic platform fallback, new training recipe, public upload, software install, commit, or GPU spend is implied by writing this plan.
