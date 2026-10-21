# Hiring-engineer audit: README setup, demos, and results

> Preserved in the original `Mech/SimReady` repository on 2026-10-21. The checkout path and observations below describe the temporary fresh-clone audit, not a new execution in this repository. See BACKLOG `audit-reports-followup`.

**Audit date:** 2026-10-21  
**Checkout:** `C:\Users\suman\Desktop\simready-fresh`  
**Platform:** Windows, PowerShell 5.1; available Python was system Python 3.12  
**Audience:** Claude Code implementing remediation and the repository owner reviewing evidence

## Verdict

The README-only setup did not reach a working Streamlit chat or generate a STEP. The README's main GNN results describe an older experiment than the committed metrics it cites. The first analysis command reports failed validation, then says **“No findings. Clean geometry.”**, prints the report twice, and exits with code 0.

The most urgent problems are result/artifact correspondence, fresh-checkout reproducibility, and failure reporting that implies success when geometry was never analyzed.

## Scope and execution limits

The requested audit was to act as a first-time CAD/AI hiring engineer: use only README.md as the setup guide, attempt the Streamlit chat and `build_part` paths, check results against scripts, change no files, and report blockers without praise.

- All project reads were within this checkout. External author environments were not inspected or used.
- After README commands failed, implementation and committed records were inspected to diagnose discrepancies. Such recovery steps are identified below; they were not supplied by the README.
- “Set up and run” conflicts with “change no files”: environment creation, installing packages, creating `.env`, and generating STEP files require writes. Environment creation was attempted with `--dry-run`; dependency installation and `.env` copying were not performed.
- Therefore this audit does **not** prove the demos fail after a complete, correctly provisioned installation. It establishes what blocked this attempt and what is missing or inconsistent in the published instructions.
- Python probes used `PYTHONDONTWRITEBYTECODE=1` to avoid bytecode writes.
- At the end of the execution audit, `git status --short --untracked-files=all` and `git diff --exit-code` were clean. This report was added afterward at the user's explicit request.
- No actual UI session, authenticated LLM call, model inference evaluation, training run, or full test suite was completed.

## 1. Numbered blockers and required guesses

### 1. Environment-manager prerequisite is unresolved

README setup, attempted with a no-write adaptation:

```powershell
micromamba create -f environment.yml --dry-run
conda env create -f environment.yml --dry-run
```

Errors:

```text
micromamba : The term 'micromamba' is not recognized ...
conda : The term 'conda' is not recognized ...
```

The documented activation also failed:

```powershell
micromamba activate simready
```

```text
micromamba : The term 'micromamba' is not recognized ...
```

**Required guess:** install/bootstrap an environment manager and initialize the shell. The README starts after this prerequisite.

`pip install -r requirements.txt` was not executed: activation had failed and installation would modify the existing environment.

### 2. The setup manifests omit the learned GNN backend dependency

Diagnostic command inferred from the evaluation script and fixture record:

```powershell
python scripts/evaluate.py data/labels_fixtures_v2 weights/brepnet.pt
```

Observed failure:

```text
File "...scripts\evaluate.py", line 16, in <module>
    from torch_geometric.loader import DataLoader
ModuleNotFoundError: No module named 'torch_geometric'
```

Neither `environment.yml` nor `requirements.txt` declares `torch_geometric`. `.github/workflows/ci.yml` installs it separately:

```text
pip install -r requirements.txt torch_geometric
```

The CI comment says Windows installation needs manual wheel selection. The README provides no corresponding procedure. This is a manifest/documentation discrepancy independent of the unavailable environment manager.

### 3. Analysis failure is presented as clean geometry and process success

Exact README command:

```powershell
python -m simready.cli analyze tests/data/smoke_box.step
```

Observed output, with the full report printed twice:

```text
Score: n/a/100  InvalidInput
Validation  | FAIL
...
No findings. Clean geometry.
```

Observed process exit code: **0**.

Diagnostic command:

```powershell
python -m simready.cli analyze tests/data/smoke_box.step --json
```

Underlying error:

```json
{
  "check": "MissingDependency",
  "severity": "Critical",
  "detail": "pythonocc-core is not available in the current environment."
}
```

**Defect:** the terminal report omits the actionable validation error, declares clean geometry despite no analysis, and returns success to automation. Missing OCC explains the failure; it does not excuse misleading failure presentation.

### 4. Streamlit chat did not launch

Exact README command:

```powershell
streamlit run ui/copilot_app.py
```

Error:

```text
streamlit : The term 'streamlit' is not recognized ...
```

Recovery probe:

```powershell
python -m streamlit run ui/copilot_app.py
```

Error:

```text
...Python312\python.exe: No module named streamlit
```

No browser/chat interaction was verified. This is a consequence of the blocked setup, not proof of an application crash in a provisioned environment.

### 5. Copilot needs credentials; the example defaults create provider ambiguity

Exact README command:

```powershell
python -m simready.copilot.cli tests/data/smoke_box.step "What's wrong with this part and how do I fix it?"
```

Error:

```text
ERROR: OPENAI_API_KEY not set. Create .env from .env.example, or pass api_key=...
```

The README's `cp .env.example .env` was not executed because it writes a file.

The README quickstart says to set `OPENAI_API_KEY`, with `OPENAI_BASE_URL` for non-OpenAI providers. However, `.env.example` already selects:

```text
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_MODEL=minimaxai/minimax-m2.7
```

**Required guess:** which provider's key to obtain and whether to replace both endpoint and model. Setting an OpenAI key alone leaves the example pointed at NVIDIA. No authenticated request was made, so provider/model availability was not verified.

### 6. The chat's built-in demo inputs are absent

Static inspection of `ui/copilot_app.py`, not observed browser output:

The sample selector reads only:

```text
data/parametric_degraded/
tests/data/grabcad/
```

Both directories are absent. The committed `tests/data/smoke_box.step` is not included in that selector.

The UI fallback instructs:

```powershell
python scripts/generate_degraded_steps.py --input data/parametric --output data/parametric_degraded --max-inputs 5
```

But `data/parametric/` is absent too. That write-producing fallback was not executed.

**Required guess:** generate source parts first or manually upload the smoke fixture. The README gives neither chat workflow.

### 7. `build_part` has no README execution recipe

The README names `build_part` but gives no generation command, example chat prompt, expected artifact, or output location. Its only copilot example analyzes an existing file.

A callable route had to be discovered in the implementation. Diagnostic command:

```powershell
python -c "from simready.gen.build import build_part, BRepPrimAPI_MakeBox; assert BRepPrimAPI_MakeBox is None; print(build_part(dict(steps=[dict(op='box', dx=80, dy=60, dz=10)]), output_dir='.'))"
```

The assertion ensures this probe stops if OCC is available; `output_dir='.'` avoids creating the default output directory. This is an audit-only failure probe, **not** the proposed user-facing demo command.

Returned result:

```text
schema_valid: True
occ_valid: False
RuntimeError: pythonocc-core is not importable in this Python environment.
Run geometry-gen under the sr env (C:\mm\sr\python.exe).
```

**README/code disagreement:** setup names the environment `simready`; runtime directs outsiders to an author-specific `sr` environment at a hard-coded path. No such external environment was inspected or used.

### 8. GNN reproduction inputs and exact recipe are absent

The evaluation command in blocker 2 failed first on PyG. Independently, its inferred dataset directory is missing:

```text
data/labels_fixtures_v2/
```

The README calls the numbers “committed and reproducible” but gives no exact sequence to reconstruct training graphs, labels, source-grouped split, and fixture evaluation.

**Required guess:** reconstruct the experiment from scripts and historical documents. Committed metric summaries are not an independently rerun experiment.

### 9. GenCAD analysis fails on an absent reference cache

Diagnostic command:

```powershell
python scripts/gencad_analyse.py
```

Error:

```text
FileNotFoundError: [Errno 2] No such file or directory:
'C:\Users\suman\Desktop\simready-fresh\data\gencad\gt_hundred.json'
```

The failure occurs before its report write. The README supplies neither the reference-cache preparation sequence nor a complete GenCAD evaluation environment.

The GenCAD adapter is also absent from `weights/`. The README says it lives on Google Drive but gives no retrieval recipe there. The BRepSAGE checkpoint, by contrast, exists and is 16,895 bytes; it must not be reported as missing.

## 2. README claims versus available evidence

### GNN tables disagree with their cited committed records

These are document/artifact comparisons, **not fresh model inference results**.

| Claim | README | Committed records |
|---|---:|---:|
| Training graphs | 1,100 | 2,272 |
| Epochs / training time | 15 / 25 s | 30 / 56.18 s |
| Train / validation graphs | 895 / 205 | 1,801 / 471 |
| Validation refinement accuracy / precision / recall | .848 / .944 / .487 | .825 / .929 / .609 |
| Validation defect accuracy | .756 | .686 |
| Self-intersection class accuracy | .37 | .212 |
| Fixture graphs / faces | 7 / 51 | 27 / 3,612 |
| Fixture accuracy / precision / recall | .725 / .750 / .692 | .853 / .920 / .895 |

Sources: `weights/metrics.json`, `weights/brepnet_meta.json`, and `weights/eval_fixtures.json`.

The .756 defect result is explicitly labeled a **v1 baseline** in `metrics.json`. The README presents it as the main held-out result without identifying that version. Checkpoint/metric correspondence was not established by inference.

### GenCAD: saved-output arithmetic was checked; inference was not

Read-only aggregation of `docs/validation/gencad/scores_qwen25vl3b_base.json` and `scores_qwen25vl3b_qlora.json` produced:

| Metric | Recomputed from saved rows |
|---|---:|
| Base valid programs | 0 / 100 |
| Tuned valid programs | 88 / 100 |
| Tuned IoU, valid only | 0.2557678008165767 |
| Tuned IoU, invalid = 0 | 0.22507566471858748 |
| Tuned median IoU, valid only | 0.047348784061404164 |
| Valid programs at IoU >= .5 | 22 |
| Filled IoU mean, valid only | 0.5629464692073265 |

The final value was aggregated from `iou_shell_vs_filled.json`. These match the rounded README figures, but do **not** validate the underlying model execution, valid-solid classification, voxelization, or metric implementation.

Stored checker records contain 88 generated and 88 reference rows. Comparing findings supports the saved-record counts of three generated-only self-intersections, six generated-only thin-wall findings, and one generated invalid solid. The geometry checker itself was not rerun.

### Remaining unverified claims and gate weaknesses

| README claim | Evidence boundary / discrepancy |
|---|---|
| Generation passes 5/5 across hosted models | No live rerun. `data/gen_eval/` raw records are absent; the validation document says they are gitignored. |
| End-to-end generate then analyze validation | `tests/test_gen_e2e.py` records analyze calls but gates STEP existence, OCC validity, and face-count range. It does not assert that analysis was called successfully, used the final artifact, or returned a valid analysis report. |
| Generation correctness | The existing gate does not assert dimensions, hole placement, or truthful verdict prose. `geometry_gen_eval.md` records historical hallucinated verdict details despite passing artifact checks. |
| Copilot gold metrics | Fifty gold input rows exist. The historical Markdown repeats the values; a live run and raw-run metric recomputation were not completed. |
| Copilot reference date | README says 2026-07; `docs/finetune_results.md` dates the reference run 2026-05-24. |
| Real-CAD scores and timing; 11/12 completed and 11/11 false positives | Not rerun. OCC setup blocked; GrabCAD sample inputs absent. |
| 227 passing tests | Not established by this audit; full suite not run. |
| Multi-turn chat, per-face rendering, provider switching | No runtime verification because Streamlit did not launch. |
| Learned-checkpoint inference and provenance reporting | Checkpoint file exists; actual loading and prediction were not exercised. |

## 3. What a hiring engineer would doubt first, ranked

### 1. Whether the results belong to the shipped artifact

The README's named evidence contradicts its headline GNN table. Missing evaluation inputs and absent raw generation runs prevent resolving the discrepancy through execution. Experiment/version control is in doubt before another accuracy number is credible.

### 2. Whether anyone except the author can independently run the project

The documented dependency recipe omits PyG; chat samples are missing; generation has no README walkthrough; errors direct users to an author-specific interpreter. A reviewer must reverse-engineer workstation assumptions before reaching the central demo.

### 3. Whether “FEA-ready” and “generation passes” mean what users infer

The observed CLI calls unexamined geometry clean. The generation gate can pass without asserting successful analysis or dimensionally correct geometry. The README itself reports 11/11 real-CAD defect false positives and no correlation against mesher outcomes. These weaken the meaning of the verdict, not merely its presentation.

## 4. Claude Code remediation handoff

Treat this section as proposed work, not completed fixes. Reproduce against the current checkout before changing code: the repository may have changed since this audit. Do not obtain secrets from external directories or assume the author's `sr` environment is available.

### Priority 1 — Stop false-success failure reporting

- Reproduce the missing-OCC analysis path and inspect CLI/report rendering.
- Surface validation errors in the terminal output.
- Do not print “Clean geometry” when validation failed or checks did not execute.
- Return a nonzero exit status for dependency/input/analysis failures.
- Remove duplicate terminal report output after tracing its source.
- Verify failure behavior and a genuine successful fixture analysis separately.

### Priority 2 — Make README setup and both demos reproducible

- Choose and document a supported platform-specific setup path, including environment-manager prerequisites and shell activation.
- Include the learned backend dependency in the install recipe; document/test any Windows wheel constraints rather than relying on CI's extra install.
- Verify compatibility of all direct dependencies, including the Pydantic v2 API used by the DSL; avoid relying accidentally on transitive versions.
- Make provider configuration internally consistent and identify which values a user must replace.
- Remove author-specific interpreter advice from runtime errors.
- Give the chat a committed sample that works on a fresh checkout, or document a complete generation chain for its samples.
- Add an exact generation prompt/entry point, expected artifact location and checks, followed by analysis of the generated artifact.
- Actually launch Streamlit and exercise chat/build/analyze with supplied credentials or a documented local backend. A server-start message alone is insufficient.

### Priority 3 — Reconcile results with the checkpoint and rerunnable experiments

- Determine which experiment produced `weights/brepnet.pt`; do not infer that solely from adjacent JSON filenames.
- Re-evaluate against reconstructed or supplied datasets and reconcile README tables with that result.
- Label historical v1/v2 runs explicitly; do not silently replace one experiment's table with another's.
- Supply an exact data/label/split/evaluation recipe, seeds, dependency versions and expected output. Keep generated inputs retrievable or reproducibly constructible.
- Provide the GenCAD reference-cache preparation and evaluation setup, plus an actionable adapter retrieval route if inference reproduction is intended.
- Correct the copilot reference date using primary run evidence.
- Preserve or publish sufficient raw generation/evaluation evidence to recompute claims.

### Priority 4 — Tighten the claimed generation gate

- Assert successful analysis of the final generated STEP, not merely record an analyze call count.
- Distinguish grammar/artifact validity, mechanical constraint correctness, and prose faithfulness in reported metrics.
- Add meaningful checks for the claimed dimensions and features, or narrow the README's interpretation of the 5/5 gate.
- Do not describe heuristic screening as demonstrated meshability without mesher evidence.

### Completion evidence to return

1. Exact setup commands that worked on a fresh environment, with OS and versions.
2. Browser-observed chat/build/analyze behavior and final artifact evidence.
3. Failure-path output plus nonzero exit code, and a separate successful analysis.
4. Fresh evaluation output tied to a specific checkpoint and input/split identity.
5. A concise diff summary and remaining blocked/unverified claims.

Do not close an item merely because documentation was edited. Distinguish executable proof, saved-output arithmetic, and historical claims.
