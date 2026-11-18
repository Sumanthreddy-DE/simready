# Fresh-install dependencies — VPS handoff

Date: 2026-11-03. Branch: `fix/fresh-install-deps`. Base: `d15ce7e`.
Task: `docs/exec-plans/active/2026-11-03-fresh-install-deps.md`.

## Result and files changed

- `requirements.txt`: `openai>=1.40,<3` (`66382a6`).
- `tests/test_cli.py`: real Python subprocess checks that the complete CLI stdout
  parses as one JSON document containing `status` (`226f67f`). No OCC marker is
  used in the existing file; this test likewise has none (an actionable missing-OCC
  report is also valid JSON).
- This handoff.

The copilot crash is fixed and both live examples passed. The alleged CLI bug is
actually output from the micromamba launcher, not a Python dependency or SimReady.
Consequently `simready/cli.py` needs no change. The exact subprocess test requested
by the task **passed before any CLI fix**, in the old environment: `1 passed,
1 warning in 38.95s`. It was repeated and passed again. This is a characterization
test, not a demonstrated RED-to-GREEN regression test.

## Baseline and reproduction (before tracked edits)

Old `simready`: `python -m pytest -q` exited 0:

```text
228 passed, 11 skipped, 3 warnings in 80.36s (0:01:20)
```

No baseline failures. This run preceded creation of the ignored `.env`; final
discovery has five explicit live-test deselections and one fewer skip. Both runs
are offline default-suite runs, not evidence of live-test coverage.

The old-env README copilot analysis command, after credentials were configured,
exited 1 with:

```text
httpx2/_decoders.py:191 in decode
    decompressed = self._decompress(data, output_buffer_limit=output_buffer_limit)
TypeError: process() takes no keyword arguments
```

The isolated Brotli call from the brief reproduced the same TypeError.
An initial attempt before `.env` creation exited 3 for missing credentials; that
was not counted as reproducing the crash.

The old-env `micromamba run -n simready python -m simready.cli analyze
tests/data/smoke_box.step --json` emitted the report plus `{"log_history": []}`;
`json.load` failed with `Extra data: line 97 column 1 (char 2401)`.

## Environment construction and resolved versions

Reused `/home/sumanth/simready-fresh/mamba/root/envs/simready` unchanged.
Created a second environment with exactly:

```bash
micromamba create -n simready-fix -f environment.yml -y
micromamba run -n simready-fix python -m pip install -r requirements.txt
```

Every environment command set `MAMBA_ROOT_PREFIX`, `PIP_CACHE_DIR`,
`XDG_CACHE_HOME`, and `PATH` to the task's throwaway-folder paths. No hand-installed
extras, lockfile, exact pins, shell init, dotfile edits, or environment.yml edits.

| Distribution | Old simready | New simready-fix |
|---|---|---|
| openai | 3.42.1 | 2.54.0 |
| httpx | absent | 0.28.1 |
| httpx2 | 2.14.0 | 2.14.0 |
| Brotli | 1.0.9 | 1.0.9 |
| torch | 2.13.0 | 2.13.0 |

Upper bound `<3` excludes the observed incompatible SDK major while retaining
the existing `>=1.40` lower bound. This proves the fresh resolve at 2.54.0, not
every historical SDK version in that range. No Brotli bound was necessary:
both live calls worked with Brotli 1.0.9 after openai selected httpx 0.28.1.
httpx2 remains installed transitively, but is no longer the SDK's transport.

## Actual log_history source and usable JSON invocation

Package/executable: **micromamba 2.10.0, libmamba**. Module:
`libmamba/src/core/output.cpp`, upstream tag `2.10.0`:

- `Console::~Console()`, lines 389–395, prints JSON at shutdown when enabled.
- `Console::print_json_output()`, lines 605–613: line 610 inserts `/log_history`;
  line 613 prints `p_data->json_output.dump(4)`.
- Source: https://github.com/mamba-org/mamba/blob/2.10.0/libmamba/src/core/output.cpp#L605-L613

Decisive positive control: even `micromamba run -n simready python -c "pass"
--json` prints `{"log_history": []}`. Python does no importing or printing in
that command. Running the real CLI with the env's Python directly emits one
document; capturing the same Python subprocess inside a micromamba-run parent
also parses successfully. The launcher processes the visible `--json` flag.
Adding `--` did not suppress its JSON output on this version; `--no-json` was
not a working workaround either.

Verified workaround that still uses `micromamba run`, without exposing the flag
as a launcher argument (run on the VPS from the repo root with the task env
variables exported):

```bash
micromamba run -n simready-fix python -c 'import runpy,sys; sys.argv=["simready.cli","analyze","tests/data/smoke_box.step","--json"]; runpy.run_module("simready.cli",run_name="__main__")' | micromamba run -n simready-fix python -m json.tool > /dev/null
```

This pipeline exited 0 (`JSON-OK`). The brief's literal micromamba JSON pipeline
still fails because the launcher adds its own document. Altering SimReady stdout
cannot suppress output from its parent process.

## Live copilot proof

Created root `.env` (mode 0600) with the authorized D Labs base URL, model
`gpt-6-1-sol`, and key read from `~/.config/opencode/dlab.key`, without displaying
the key. `git check-ignore .env` returned `.env` and `git status --short --ignored
.env` returned `!! .env`. No fallback model was needed.

Both exact README copilot commands from the brief ran in `simready-fix`, exited
0, and produced answers. Trimmed outputs:

```text
Q: What's wrong with this part and how do I fix it?
tool_call #1 analyze_geometry
tool_call #2 suggest_fixes
Verdict: SimulationReady · score 92.71/100 · simple (6 faces, 1 bodies)
Issues: No geometry defects detected; geometry validation passed.
Fixes: No geometry repairs recommended. Proceed to meshing, then verify
mesh quality, material properties, loads, and boundary conditions.
iterations=3
```

```text
Q: Create an 80 x 60 x 10 mm plate with a centered 10 mm through-hole.
tool_call #3 build_part
spec: box(80,60,10), cylinder(r=5,h=10,at=[40,30,0]), cut(a=0,b=1)
schema_valid=true, occ_valid=true, faces=7, edges=30, solids=1, wrote=true
STEP: data/gen_parts/gen_dbaecd5366fb.step
tool_call #4 analyze_geometry [that exact generated STEP]
Verdict: ReviewRecommended · score 88.75/100 · simple (7 faces, 1 bodies)
Issues: Minor SmallFeatures, 10 short local edges; no small faces.
Fixes: Inspect flagged edges; preserve intended plate and hole dimensions.
iterations=6
```

## Final checks

- `import OCC, torch_geometric, pydantic, streamlit`: `setup OK`.
- New-env full suite, exit 0:
  `229 passed, 10 skipped, 5 deselected, 3 warnings in 96.62s (0:01:36)`.
- No new failures. Warnings: anyio pytest CallSpec deprecation and two
  torch.jit.script deprecations, also present in baseline.
- Skips: missing degraded fixture (1), gitignored UI degraded data (1),
  missing GrabCAD samples (3), absent gitignored real_eval data (5).
- Five live tests deselected by repo pytest configuration.
- `git diff --check` passed. Self-review of the small production/test diff;
  no delegated review was requested.

The final suite log has buffered native OCC output *after* the pytest summary.
Its literal last five lines, with ANSI color escapes removed, were:

```text

** WorkSession : Sending all data

 Step File Name : /tmp/pytest-of-sumanth/pytest-25/test_validate_file_load_valid_0/valid_box.step(350 ents)  Write  Done

```

One redundant detailed-suite attempt hit the shell's 120-second timeout; it was
rerun with a 240-second timeout and produced the final successful result above.

## Cleanup, decisions, and remaining limitations

- `~/.conda` and `~/.mamba` were **both absent at start**. Environment creation
  created them. Inspected their contents, then deleted both as expressly required.
- Both named environments remain under the throwaway folder. Final
  `du -sh /home/sumanth/simready-fresh`: **4.5G**.
- Ignored `.env`, generated STEP/healed artifacts and copilot sessions remain
  local. No tracked data/weights/validation content was edited.
- No BACKLOG, STATE, README, memory, or plan edits. No push.
- Ruling: do not implement the planned CLI stdout fix or claim a fail-before
  result; the specified Python subprocess already passes in the old env. Cost
  if wrong: an independent Python-side contaminant could remain undetected;
  the committed real-process test covers the observed CLI contract.
- The launcher-level JSON issue remains in the literal task command. A future
  README/setup change can explain the wrapper/direct-Python invocation or an
  upstream micromamba fix, separately from this task's scoped files.
