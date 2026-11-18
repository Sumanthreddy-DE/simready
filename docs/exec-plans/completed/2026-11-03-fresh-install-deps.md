# fresh-install-copilot-crash + cli-json-extra-document — task brief

**Status:** done
**Last verified:** 2026-11-03

BACKLOG S1 `fresh-install-copilot-crash` and S2 `cli-json-extra-document`. Written for
an agent working on the VPS in opencode; reviewed and merged on the laptop. Repo:
`~/projects/Mech/SimReady`. Branch: `fix/fresh-install-deps`. Evidence of both bugs:
the fresh-clone test report (summary in the two BACKLOG items).

## The two bugs

1. **Copilot crash on a fresh install.** `requirements.txt` says `openai>=1.40` with no
   upper bound. A fresh Linux resolve on 2026-11-03 gave openai 3.42.1 + httpx2 2.14.0 +
   Brotli 1.0.9 (Brotli from conda-forge), and every copilot request died in
   `httpx2/_decoders.py … TypeError: process() takes no keyword arguments`
   (`brotli.Decompressor().process(b'', output_buffer_limit=1024)` fails the same way).
   The owner's working Windows env has openai 2.36.0 + httpx 0.28.1 + brotli 1.2.0.
2. **`analyze --json` prints two JSON documents** on that fresh env: the report, then
   `{"log_history": []}`. The string `log_history` is nowhere in `simready/`. Note:
   `analyze_file_safe` (`simready/pipeline.py:280`) runs the analysis in a subprocess
   whose stdout and stderr go to `DEVNULL`, so the extra output comes from the **parent**
   process — an import side effect or an exit hook of some dependency. On the laptop env
   the output is one valid document.

## Environment — reuse the throwaway folder

The broken fresh env exists at `~/simready-fresh/mamba/root/envs/simready`. Set, in every
command that touches an env:

```bash
export MAMBA_ROOT_PREFIX=~/simready-fresh/mamba/root PIP_CACHE_DIR=~/simready-fresh/cache/pip XDG_CACHE_HOME=~/simready-fresh/cache PATH=~/simready-fresh/mamba/bin:$PATH
```

Use `micromamba run -n <env> <cmd>`. Never `micromamba shell init`, never edit dotfiles.
At the start, record whether `~/.conda` and `~/.mamba` exist; at the end, delete each of
them **only if it did not exist at the start**, and say so in the handoff.

- Reproduce both bugs first in the existing env `simready` (run from the repo root).
- The proof for your fix is a **second, new env** `simready-fix` built from this branch's
  `environment.yml` + `requirements.txt` exactly as the README says
  (`micromamba create -n simready-fix -f environment.yml -y`, then
  `micromamba run -n simready-fix python -m pip install -r requirements.txt`).
  Do not hand-install extra packages into it; if something is needed, it goes into the
  two files. Both envs stay; the owner deletes the folder later.

## Decided — do not change these

1. **Bound, don't freeze.** Fix bug 1 in `requirements.txt` (and `environment.yml` only
   if the cause is a conda package) with version ranges: give `openai` an upper bound
   below the major that breaks (expected `<3`; confirm). Add a lower bound for `brotli`
   only if the copilot still fails without it. No lock file, no `==` pins, no change to
   other packages unless a test proves they break.
2. **Copilot proof (live).** In `simready-fix`, with `.env` in the repo root holding
   `OPENAI_BASE_URL=https://api.dlabkeys.com/v1`, `OPENAI_MODEL=gpt-6-1-sol` and the key
   from `~/.config/opencode/dlab.key` (never print it; `.env` is gitignored — check
   `git status` shows it as ignored, not untracked), both README copilot commands must
   exit 0 with an answer:
   `python -m simready.copilot.cli tests/data/smoke_box.step "What's wrong with this part and how do I fix it?"`
   and the same with `"Create an 80 x 60 x 10 mm plate with a centered 10 mm through-hole."`
   For the second, the output must show a `build_part` call and a STEP path under
   `data/gen_parts/`. If gpt-6-1-sol fails for a provider reason, retry with `glm-5-3`
   and report both.
3. **One JSON document.** Find what prints `{"log_history": []}` (name the package,
   module and line in the handoff). Fix it in `simready/cli.py` so stdout with `--json`
   is exactly the report — e.g. keep third-party output off stdout — without changing the
   JSON content or the non-JSON terminal output. Do not patch site-packages.
4. **Test.** Add a test to `tests/test_cli.py` that runs the real CLI in a subprocess
   (`[sys.executable, "-m", "simready.cli", "analyze", "tests/data/smoke_box.step",
   "--json"]`, `cwd` = repo root) and asserts `json.loads(stdout)` succeeds and has
   `status`. **Run it in the old `simready` env first and confirm it fails there**;
   report that in the handoff. Mark it with whatever marker the existing OCC-dependent
   tests in that file use, if any.

## Not decided — your call, record it in the handoff

The exact upper/lower bounds (with the resolved versions that prove them), and the
mechanism of the stdout fix.

## Commands

```bash
micromamba run -n simready-fix python -m pytest -q
micromamba run -n simready-fix python -c "import OCC, torch_geometric, pydantic, streamlit; print('setup OK')"
micromamba run -n simready-fix python -m simready.cli analyze tests/data/smoke_box.step --json | micromamba run -n simready-fix python -m json.tool > /dev/null && echo JSON-OK
```

Baseline first: run the full `pytest -q` in the old `simready` env before any edit and
put the summary line in the handoff (the owner's Windows env had 255 passed / 5
deselected on 2026-10-25; Linux may differ — failures already there are not yours, list
them, do not fix them). The final run in `simready-fix` must have no new failures.

## Rules

- Commits: (1) dependency bounds, (2) stdout fix + test, message prefix
  `fresh-install-deps:`; (3) the handoff.
- Never edit `BACKLOG.md`, `STATE.md`, `README.md` (README fixes are a separate item),
  memory files, anything under `docs/superpowers/`, or tracked files under `data/`,
  `weights/`, `docs/validation/`. No `/save-session`. No push.
- End: write `docs/handoff-2026-11-03-fresh-install-deps.md` — files changed; resolved
  versions of openai / httpx(2) / brotli / torch in both envs; the bounds chosen and why;
  the `log_history` source; the two copilot outputs (trimmed, no key); last 5 lines of the
  final pytest run; fail-before result of the new test; `~/.conda` / `~/.mamba` handling;
  `du -sh ~/simready-fresh`; anything not done. Commit it.
