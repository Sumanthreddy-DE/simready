# README Linux commands and S3 cleanups — handoff

Executed 2026-11-03 in `/home/sumanth/projects/Mech/SimReady-readme-s3`, branch
`chore/readme-linux-s3`, starting at `5e802cb`.
Brief: `docs/exec-plans/active/2026-11-03-readme-linux-and-s3-cleanups.md`.

## Changes and commits

| Task | Files | Commit |
|---|---|---|
| 1 — Linux README commands | `README.md`: Bash build→analyze, Bash configuration copy, runnable smoke fixture in all four analyze commands, both PYTHONPATH forms | `149c1813ff8142889f2625c7b8ee06002b59158e` |
| 2 — dead import | `simready/ml/brepnet.py`: deleted exactly the four-line unused import/fallback block | `27c9bb000af407660c41ba49b53ec67b1f5aa0d5` |
| 3 — shared face iterator | `simready/ml/graph_extractor.py`: `_iter_faces` wraps canonical `iter_faces`; `tests/test_graph_extractor.py`: smoke-box index/count parity test | `fe28d3db6f9bcbb3593ee24768b5a81e9a33c053` |
| 4 — schema coverage | `tests/test_report_schema.py`: real safe-pipeline smoke report validated with `pytest.importorskip("jsonschema")` | `939079cf05ef7792f1a0e2fffe2d00436beaca55` |

This handoff is the fifth, final commit (`readme-linux-s3: record verification handoff`).
Its SHA is available with `git log -1 --format=%H` at handoff HEAD; a commit cannot
contain its own SHA.

## Environment and baseline

Used the existing `simready` environment without installing packages or changing its
configuration. All Python commands below used this environment and these variables:

```bash
export MAMBA_ROOT_PREFIX=~/simready-fresh/mamba/root PIP_CACHE_DIR=~/simready-fresh/cache/pip XDG_CACHE_HOME=~/simready-fresh/cache PATH=~/simready-fresh/mamba/bin:$PATH
micromamba run -n simready python -m pytest -q
```

Baseline, before any edit (exit 0):

```text
228 passed, 11 skipped, 3 warnings in 88.19s (0:01:28)
```

Final, same command (exit 0):

```text
230 passed, 11 skipped, 3 warnings in 87.09s (0:01:27)
```

No baseline or final failures. Warnings in both runs: one anyio pytest-plugin
`CallSpec2` deprecation and two torch `torch.jit.script` deprecations.

## Task 1 command evidence

The Bash snippet was run inside `micromamba run -n simready bash -c`:

```bash
step_path=$(python -m simready.gen.build | tail -n 1 | python -c 'import json, sys; print(json.load(sys.stdin)["step_path"])')
python -m simready.cli analyze "$step_path"
```

Both the assignment pipeline and analyze command exited 0. Analysis stdout:

```text
SimReady Analysis: /home/sumanth/projects/Mech/SimReady-readme-s3/data/gen_parts/gen_73d8028b0009.step
Score: 88.7470385006496/100  ReviewRecommended
Complexity: Simple Geometry (confidence: high)
+---------------------------------+
| Category    | Value             |
|-------------+-------------------|
| Validation  | PASS              |
| Faces       | 7                 |
| Edges       | 30                |
| Solids      | 1                 |
| Graph Edges | 15                |
| Coedges     | 30                |
| Elapsed     | 4.729409284889698 |
+---------------------------------+
Top issues:
[Minor] SmallFeatures: Detected 0 small faces and 10 short local edges relative to part scale.
  -> Inspect tiny local features that may force unnecessary mesh refinement.
ML: BRepSAGE-multitask (brepsage-checkpoint)
```

All four commands were run separately through `micromamba run -n simready`:

```bash
python -m simready.cli analyze tests/data/smoke_box.step
python -m simready.cli analyze tests/data/smoke_box.step --json
python -m simready.cli analyze tests/data/smoke_box.step --html report.html
python -m simready.cli analyze tests/data/smoke_box.step --export-healed out.step
```

| Command option | Exit | Output |
|---|---:|---|
| none | 0 | SimulationReady, overall score 92.70735571781795/100; validation PASS; 6 faces, 24 edges, 1 solid, 12 graph edges, 24 coedges; no findings; elapsed 4.454625779995695 s |
| `--json` | 0 | Report JSON: status SimulationReady, validation.is_valid true, geometry counts 6/24/1, findings [], score.overall 92.70735571781795; elapsed_seconds 4.586724692024291; followed by a second JSON object `{"log_history": []}` |
| `--html report.html` | 0 | Same clean-geometry summary and counts; elapsed 4.212870247894898 s; wrote `report.html` |
| `--export-healed out.step` | 0 | Same clean-geometry summary and counts; elapsed 4.917498699855059 s; wrote `out.step` |

All four reported Simple Geometry (confidence high), with ML
`BRepSAGE-multitask (brepsage-checkpoint)`. The extra JSON object is the known
other-branch issue and was not changed.

Deleted the generated `report.html` and `out.step`. The generated STEP remains
ignored under `data/gen_parts/`, as the brief permits. The `.env` copy and historical
fixture-evaluation command were documented, not executed.

## Tasks 2–4 verification

Commands below were each prefixed with `micromamba run -n simready`:

| When | Command | Result (exit 0) |
|---|---|---|
| After dead-import deletion | `python -m pytest -q tests/test_brepnet.py` | 3 passed, 3 warnings in 7.90s |
| Before iterator refactor | `python -m pytest -q tests/test_graph_extractor.py::test_smoke_box_face_indices_match_canonical_iterator` | 1 passed, 1 warning in 0.39s |
| After iterator refactor | `python -m pytest -q tests/test_graph_extractor.py` | 10 passed, 1 warning in 0.46s |
| New schema test, existing schema | `python -m pytest -q tests/test_report_schema.py` | 1 passed, 1 warning in 13.50s |

The iterator test catches mismatched extractor indices/counts against canonical
iteration on the same smoke-box shape, with a six-face sanity check. It passed before
and after the behavior-preserving refactor, as required. The schema test ran (did not
skip) and passed immediately. **Schema changes: none**; no report-building code changed.

## Review and execution notes

- Pre-flight: the four tasks share no changed interfaces; only the schema test consumes
  the existing pipeline, which the tasks leave intact.
- Used this required handoff as the durable execution record instead of creating skill
  scratch ledgers/briefs, to respect the explicit no-new-files constraint.
- Independent final read-only review of `5e802cb..939079c`: no findings. Review limits:
  reviewer inspected source/diff but did not rerun commands; parity test checks indices
  and count rather than face identity/hashes (source comparison confirmed equivalent
  traversal, casting, indexing and hash fallback); this handoff was not yet written.
- `git diff --check 5e802cb..HEAD` passed before this handoff. Working tree was clean
  after task commits and final pytest, before adding this handoff.
- No deferred findings or unfinished task items. No push performed. Plan status left
  active because the brief limits edits to the task files and handoff.
- The Citadel shell hook repeatedly reported `pwsh: ENOENT` and used its fallback
  matcher; command/test results above are the actual outputs despite that hook notice.
