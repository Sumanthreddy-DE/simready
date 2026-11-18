# simready-pyproject report

**Status:** done
**Last verified:** 2026-11-18
**Status evidence:** f3b80a6 is an ancestor of main (verified 2026-11-18)

Branch: gpt/simready-pyproject   Base: 5f830dbc4fcfbc81134ff9a2413217ee2160d71d   Head: f3b80a6c686c29686f4be197ba1f6ef660b4a37c
## Result
DONE -- SimReady builds an installable benchmark wheel with packaged concepts and an optional OCP backend.
## Commits
- f3b80a6 package metadata and benchmark install instructions -- verified by `/home/sumanth/.venvs/simready-ocp/bin/python -m pytest -q -s -p no:cacheprovider /tmp/opencode-simready-pyproject/test_packaging.py` -> `3 passed in 8.13s`
## Checks
- P1: PASS -- `Requires-Python: >=3.10|Requires-Dist: pydantic>=2|Provides-Extra: bench|Requires-Dist: cadquery-ocp==8.0.1.1.0; extra == "bench"|`
- P2: PASS -- `P2: 2` (concepts_v1.jsonl and templates/report.html in wheel).
- P3: PASS -- `P3: OK 37`; fresh scratch-target wheel install, outside checkout, no click/rich/jinja2 imports.
- P4: PASS -- `211 before passing; 211 after passing; 0 regressions`; compared PASSED node IDs from both full-suite logs, with reference-spec positive control.
- P5: PASS -- `P5: 3` (heading and both OCP install lines).
- P6: PASS -- `/home/sumanth/.venvs/simready-ocp/bin/python /tmp/opencode-simready-pyproject/audit.py` -> `P6 external roots: pydantic`; dynamic backend roots `OCC.Core` or `OCP`.
- P6 import list: concepts.py:15 imports pydantic BaseModel, ConfigDict, Field, TypeAdapter, model_validator; spec.py:25 imports pydantic BaseModel, ConfigDict, Field, NonNegativeInt, model_validator.
- P6 dynamic import list: occ_compat.py:39,42,50,54,56,62,69,71 loads OCP.collections, backend geometry modules, OCC.Core.BRepTools, OCP.TopoDS; remaining audited files import only stdlib or simready modules.
- Mutation: PASS -- removing the pydantic dependency yielded `1 failed in 0.04s`; restoring it yielded `1 passed in 0.01s`.
- Diff hygiene: PASS -- `git diff --check` emitted no output; status clean after implementation commit.
## Baseline
before: 20 failed, 211 passed, 28 skipped in 19.94s   after: 20 failed, 211 passed, 28 skipped in 24.55s
## Deviations
- Acceptance commands were implemented as equivalent scratch Python/pytest checks to keep all scratch output under /tmp/opencode-simready-pyproject and avoid /dev/null; wheel builds used --no-deps --no-build-isolation and installation used --no-deps --target.
- Required added unit checks and mutation test live only in scratch because the contract forbids changes under tests/; P4 uses captured pre-edit baseline at the exact sp1-bench SHA rather than another archive/run.
## Questions
- none
## Not verified
- pythonocc backend and Python 3.10 execution (unavailable here); remote tag-based installation (no tag yet, network forbidden).
