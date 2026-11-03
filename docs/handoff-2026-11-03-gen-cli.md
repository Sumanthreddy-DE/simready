# geometry-gen v3 CLI — handoff

**Status:** done
**Last verified:** 2026-11-03

Branch: `feat/gen-cli`, based on `110dd2f`. Task brief:
`docs/exec-plans/active/2026-11-03-gen-cli-v3.md`.

## Changes and commits

- `bbd3d85` — `gen-cli: add prompt-to-STEP CLI with exact artifact analysis`
  - `simready/gen/cli.py`: importable `generate(prompt, *, model=None, timeout=120)`
    and `main(argv)`, final-build event pairing, independent exact-STEP analysis,
    structured failures, JSON/human output and exit codes.
  - `scripts/simready_gen.py`: thin entry point, works from the repo without
    separately setting PYTHONPATH.
  - `tests/test_gen_cli.py`: eight offline tests; only the LLM agent is replaced
    for success, with real local build and analysis of the seven-face plate.
- `9bdf8bf` — `gen-cli: document one-command generation`
  - `README.md`: one paragraph at the end of setup section 4.
- This handoff is the third `gen-cli:` commit; its SHA is available from
  `git log -1 --format=%H -- docs/handoff-2026-11-03-gen-cli.md`.

## Baseline and fail-before evidence

Before any repository edit, activated `simready-fix` and ran `python -m pytest -q`.
The initial tool invocation timed out at 120 seconds; the rerun completed:
**231 passed, 10 skipped, 5 deselected, 3 warnings in 104.75s**.

After writing the CLI tests and before creating the implementation, ran
`python -m pytest tests/test_gen_cli.py -q`: collection failed as expected with
`ImportError: cannot import name 'cli' from 'simready.gen'`.

The first seven tests passed. Initial live runs then exposed buffered OCC stdout
being flushed at process exit after the JSON, producing `JSONDecodeError: Extra
data`. Added a regression using real buffered C stdio; watched it fail with the
same error, then flush native stdio before restoring stdout. All eight tests
passed in **28.56s**, and the complete six-run live proof passed afterward.
Python prints, native writes and inherited subprocess stdout are redirected to
stderr during generation/analysis; buffered native output is flushed there too.

## Live proof — VPS, DLab

Used the existing repo `.env` through dotenv (no credentials printed), verified
endpoint `https://api.dlabkeys.com/v1` and model `gpt-6-1-sol`. Used an activated
shell with the brief's cache/root variables, never `micromamba run`. Each row is
a separate CLI process with the exact prompt from the first three records in
`tests/data/gen_prompts.jsonl`.

| Prompt ID | Mode | Exit | Faces | Score | Analysis status | Wall seconds |
|---|---|---:|---:|---:|---|---:|
| normal_box | human | 0 | 6 | 95.48712079723676 | SimulationReady | 50.10 |
| normal_box | JSON | 0 | 6 | 95.48712079723676 | SimulationReady | 50.46 |
| thin_plate | human | 0 | 6 | 35.48972189426422 | NotReady | 50.35 |
| thin_plate | JSON | 0 | 6 | 35.48972189426422 | NotReady | 52.76 |
| l_bracket | human | 0 | 11 | 89.0875222263011 | ReviewRecommended | 48.86 |
| l_bracket | JSON | 0 | 11 | 89.0875222263011 | ReviewRecommended | 52.83 |

All final builds were OCC-valid; all three JSON stdout streams parsed in full as
exactly one object. Human stdout ended with the specified three summary lines.
The thin plate's exit 0 means successful build/analysis, **not FEA readiness**:
the independent analysis genuinely returned `NotReady`.

Local raw stdout/stderr and timings are under `/tmp/opencode/gen-cli-*`; generated
STEPs remain in ignored `data/gen_parts/`. These are local evidence, not portable
tracked artifacts. The initial failed live proof (before the flush fix) included
one successful human run and one malformed-JSON run and is excluded from the
post-fix table.

## Verified return shapes and decisions

- `build_part` success: `step_path`, `schema_valid`, `occ_valid`, `occ_errors`,
  `faces`, `edges`, `solids`, `bbox_mm`, `wrote`. CLI uses `faces`, `occ_valid`,
  `step_path`; failed builds may provide only `error` and validity flags.
- Agent events: `type`, `name`, `iteration`, `arguments` for a call, `result` for
  its result. The final transaction's spec comes from JSON `arguments.spec`,
  selected with the existing `select_final_build`; a failed later transaction
  invalidates the run rather than selecting an earlier STEP.
- `analyze_generated_part`: `ok`, `step_path`, `status`, nested `analysis`, and
  on failure `error`. `analysis_status` uses outer `status`; numeric `score` uses
  `analysis.score.overall`. Analysis success uses `ok`, not literal status `ok`
  (the actual statuses include `SimulationReady`, `NotReady`, etc.).
- `AgentResponse.model`/agent model and `iterations` supply model and iterations.
- Unavailable fields are JSON `null`: e.g. no final build leaves STEP/spec/face
  count/validity/analysis fields null; no completed agent response leaves
  iterations null. No successful live row lacked a requested field.
- Ruling: `--timeout` bounds the final independent analysis (default 120 s),
  following `analyze_generated_part(timeout_seconds=...)`; it is **not an overall
  LLM-run deadline**. Help text and API docstring state this explicitly. The
  existing agent/provider retries and individual tool timeouts remain in effect.
  Cost if callers expect a total deadline: a run can exceed `--timeout`.
- Reused the existing isolated branch checkout as specified by the brief;
  the walkthrough worktree was left alone. Kept progress/evidence in this requested
  handoff rather than introducing additional scratch conventions in the repo.

## Final verification and review

`python -m pytest -q` in activated `simready-fix`, exit 0:
**239 passed, 10 skipped, 5 deselected, 3 warnings in 135.95s**.
No new failures; eight additional passing tests. Existing warnings are anyio's
pytest deprecation and two torch JIT deprecations.

The requested literal last five lines of `/tmp/opencode/gen-cli-final-pytest.log`
are below (ANSI color escapes removed for readability). Existing native OCC test
output flushes after pytest's summary, so these lines are not the test totals:

```text

** WorkSession : Sending all data

 Step File Name : /tmp/pytest-of-sumanth/pytest-34/test_validate_file_load_valid_0/valid_box.step(350 ents)  Write  Done

```

Self-review checked the final diff against the brief, actual return keys,
failure gates, scope exclusions, native-output handling and README placement;
`git diff --check` passed. No fresh-agent review was run; author self-review is
weaker than an independent review. No deferred code findings.

Neither `~/.conda` nor `~/.mamba` existed at start or finish, so no cleanup was
needed. Nothing was installed and no dotfiles were edited. Protected files and
the other worktree were untouched. No push, merge or session-save was performed.

Not verified here: execution on Windows/PowerShell (the command syntax is shared,
but live and native-buffer checks ran on Linux), an overall LLM wall-clock
timeout, or fresh-clone environment provisioning. The requested VPS task and live
proof are complete.
