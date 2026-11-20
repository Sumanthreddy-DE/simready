# ADR 0005 — Benchmark-only free-form build123d arm

- **Status:** Accepted (2026-11-20)
- **Owners:** SimReady / SP2
- **Supersedes:** N/A (ADR 0001 stays in force for the product)
- **Related:** `docs/exec-plans/active/2026-11-20-sp2-vocab-v2-design.md` (E4),
  `docs/exec-plans/completed/2026-09-25-sp1-cad-benchmark-design.md` (D1), ADR 0001.

## Context

SP1 decision D1 deferred "Option C" (let the model write CAD code) to a measured comparison:
does the typed DSL beat free-form code on the same prompts and the same checker? Answering
that needs model-written Python to run. ADR 0001 forbids executing LLM-written code in the
product, and this ADR does not change that.

## Decision

Add a benchmark-only arm, `build123d`, used by `python -m simready.bench run --arm build123d`
and nowhere else.

- The model answers with one fenced Python block that builds a build123d solid and assigns it
  to `part`.
- **AST gate** (`simready/bench/code_arm.py`, before any execution). Only `import build123d` /
  `from build123d import …` and `import math` / `from math import …` are allowed. It rejects
  `open`, `exec`, `eval`, `compile`, `__import__`, `globals`, `locals`, `vars`, `getattr`,
  `setattr`, `delattr`, `input`, `breakpoint`, `memoryview`, `async`/`await`, any name or
  attribute starting with `_`, `import_` or `export_`, and the attributes `format` and
  `format_map`.
- **Dedicated venv** `~/.venvs/simready-b123d` with `build123d==0.13.0`. build123d needs
  `cadquery-ocp-novtk>=8.0,<8.1`, which conflicts with the bench extra's `cadquery-ocp==8.0.1.1.0`.
- **Child process** (`simready/bench/code_exec.py`, `simready/bench/_b123d_child.py`):
  `python -I`; an empty temporary directory as cwd; environment with only `PATH`,
  `HOME` = the temporary directory, `PYTHONNOUSERSITE=1`. The child sets its own limits before
  running the answer: `RLIMIT_CPU` 60 s, `RLIMIT_AS` 4 GiB, `RLIMIT_FSIZE` 64 MiB,
  `RLIMIT_CORE` 0. They are not set through `preexec_fn`, which can deadlock when the parent
  calls from worker threads. The parent kills the child after 90 s wall clock.
- The child writes exactly one file, `part.step`. The parent reads it in the bench venv and grades
  it with the unchanged checker (`CHECKER_VERSION` 1.0.0).

## Consequences

- **No network isolation.** `kernel.apparmor_restrict_unprivileged_userns = 1`, `unshare -rn`
  fails (`write failed /proc/self/uid_map: Operation not permitted`), and bwrap/docker are not
  installed.
- **No filesystem isolation.** The child runs as the user, so it can read anything the user can,
  the repo `.env` included. The AST gate removes the direct routes: `open`, dunder access,
  `str.format`/`format_map`, and build123d's `import_*`/`export_*` path functions. A gate is a
  filter, not a jail, so this risk is accepted, not removed.
- The risk is acceptable because the code comes from the benchmarked models, not from users,
  and every answer is logged and reviewable.
- The arm is never wired into the copilot, and ADR 0001 stays in force for the product.
- Revisit if the arm ever runs untrusted prompts.

## Alternatives considered

- **docker `--network none`:** needs sudo and a new system dependency on the VPS.
- **Kaggle/Colab sandbox:** slow, not reproducible, and the local small model does not fit there.
