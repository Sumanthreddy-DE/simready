# readme-linux-commands + three S3 cleanups — task brief

**Status:** active
**Last verified:** 2026-11-03

BACKLOG S2 `readme-linux-commands`, S3 `brepnet-dead-import`,
S3 `graph-extractor-dup-face-iter`, S3 `report-schema-unused`. Written for an agent on the
VPS in opencode; reviewed and merged on the laptop. Branch: `chore/readme-linux-s3`,
cut from `main`.

**Another agent is working in `~/projects/Mech/SimReady` right now** (branch
`fix/fresh-install-deps`). You work in a separate worktree,
`~/projects/Mech/SimReady-readme-s3`, and never touch the other checkout, its branch, or
the env `simready-fix`. Files that branch changes — `requirements.txt`,
`environment.yml`, `simready/cli.py`, `tests/test_cli.py` — are off limits for you.

## Environment

Use the existing env `simready` under the throwaway folder (read-only use; install
nothing into it):

```bash
export MAMBA_ROOT_PREFIX=~/simready-fresh/mamba/root PIP_CACHE_DIR=~/simready-fresh/cache/pip XDG_CACHE_HOME=~/simready-fresh/cache PATH=~/simready-fresh/mamba/bin:$PATH
micromamba run -n simready python -m pytest -q
```

Never `micromamba shell init`, never edit dotfiles. Its copilot is broken (the other
branch fixes that) — you need no LLM call.

## Task 1 — `readme-linux-commands` (README.md only)

The README says Linux works (CI on Ubuntu) but some snippets are PowerShell-only. In the
README on `main` (line numbers as of `d15ce7e`):

1. Line ~145 `$built = python -m simready.gen.build | Select-Object -Last 1 | ConvertFrom-Json`
   and ~146 `python -m simready.cli analyze $built.step_path`: add a ` ```bash ` block
   right after the PowerShell block with a working Bash equivalent (e.g. `tail -n 1` +
   `python -c` reading `step_path` from the JSON line). **Run it** in the env and paste
   the output in the handoff.
2. Line ~160 `Copy-Item .env.example .env`: add `cp .env.example .env` for Bash (a
   one-line Bash block or an inline note — keep the section short).
3. Lines ~131–133 `analyze part.step …`: replace `part.step` with
   `tests/data/smoke_box.step` so every line runs on a fresh clone. **Run all four
   lines** and record the exit codes (the `--json` one may print a second JSON object on
   this env — that is the other branch's bug; note it, don't fix it).
4. Line ~234 "with the project environment and `PYTHONPATH` set": the reproduction
   guide (`docs/validation/reproduce-results.md:16`) sets it with
   `$env:PYTHONPATH = (Get-Location).Path`. In the README sentence, name both forms:
   PowerShell `$env:PYTHONPATH = (Get-Location).Path`, Bash `export PYTHONPATH="$PWD"`.
   Do not change the claim itself (the dataset question is a separate decision).

Delete the outputs those runs write (`report.html`, `out.step`, `data/gen_parts/*`
stays ignored) so `git status --short` is clean at the end.

Keep the README's voice: plain, short, no new sections, no marketing words. Change
nothing else in the README.

## Task 2 — `brepnet-dead-import`

`simready/ml/brepnet.py:177–180`: the `try: from simready.ml.dataset import
build_edge_index_from_adjacency / except ImportError: … = None` block imports a name
that `simready.ml.dataset` does not define, and the name is never used (verified: it
appears only on those lines). **Delete the four lines.** No other change in the function.

## Task 3 — `graph-extractor-dup-face-iter`

`simready/ml/graph_extractor.py:109` `_iter_faces()` re-walks faces with its own
`TopExp_Explorer` loop. `simready/occ_utils.py:106` `iter_faces()` is the canonical
0-based iterator ("Shared across checks and ML modules"). Rebuild `_iter_faces` on top of
it, the way `simready/checks.py:129–132` already does:
`[FaceEntry(index=i, face=f, hash_code=_shape_hash(f) or i) for i, f in iter_faces(shape)]`.
Same return type and values; keep the function name (its caller is line 369). Add a test
that, for `tests/data/smoke_box.step`, the extractor's face indices and count equal
`occ_utils.iter_faces` on the same shape.

## Task 4 — `report-schema-unused`

`simready/report_schema.json` (required: `input_file`, `status`, `summary`, `validation`,
`findings`, `bodies`) is loaded by no code. **Decision: keep it and test it.** Add a test
that runs `analyze_file_safe("tests/data/smoke_box.step")` and validates the result
against the schema with `jsonschema` (installed transitively in the env; use
`pytest.importorskip("jsonschema")`, add no dependency). If the real report does not
match, **the code is the truth**: change the schema to match the report, never the
report-building code, and list every schema change (path, old → new) in the handoff.

## Commands and baseline

Before any edit, in the worktree: `micromamba run -n simready python -m pytest -q` →
put the summary line in the handoff (Linux numbers may differ from the laptop's 255
passed / 5 deselected; failures already present are not yours — list them, don't fix).
Final run: no new failures. Each new test: run it before the code change where that
makes sense (Task 3 test passes before and after — that is the point; Task 4 test may
fail first if the schema is stale — report).

## Rules

- Setup is done by the owner before you start (`git worktree add ../SimReady-readme-s3
  -b chore/readme-linux-s3 main` from `~/projects/Mech/SimReady`). Check you are in
  `~/projects/Mech/SimReady-readme-s3` on `chore/readme-linux-s3`; work only there.
- One commit per task, prefix `readme-linux-s3:`; a last commit for the handoff.
- Never edit `BACKLOG.md`, `STATE.md`, memory files, anything under `docs/superpowers/`,
  `weights/`, `data/`, `docs/validation/`, or the off-limits files above. No new files
  except the tests and the handoff. No `/save-session`. No push.
- End: write `docs/handoff-2026-11-03-readme-linux-s3.md` — files changed per task, the
  commands you ran for Task 1 with their output/exit codes, schema changes (if any),
  baseline and final pytest summary lines, all commit SHAs, anything not done. Commit it.
