# SimReady Phase 1 Implementation Plan

**Goal:** Build a disciplined CLI-first MVP for SimReady that takes a STEP file and outputs a JSON simulation-readiness report for structural FEA.

**Phase 1 principle:** Do the thinnest credible vertical slice first. Do not build the whole product skeleton up front.

**Primary outcome for Phase 1A:**
- load a STEP file
- validate file load and null shape
- extract a few core geometry facts
- run a small set of essential checks
- produce a stable JSON report
- expose the flow through a working CLI

**Deliberately deferred:**
- Streamlit UI
- PyVista viewer
- real ML integration
- full 11-check rule set
- aggressive mesh recommendation logic
- broad synthetic dataset generation
- polishing for features we have not proven yet

**Spec reference:** `SimReady-Phase1-Design.md` remains the product/design vision. This file is the implementation order for the approved MVP.

---

## Approved Build Order

### Phase 1A: Thin vertical slice
1. Lock repo scaffold and environment
2. Verify OCC/STEP read works on one tiny file
3. Implement validator
4. Implement parser for basic geometry extraction
5. Implement essential checks only
6. Implement stable report builder
7. Implement pipeline orchestrator
8. Implement CLI
9. Add focused tests for the vertical slice

### Phase 1B: Core robustness
1. Add multi-body splitting if needed for real sample files
2. Add conservative auto-heal support
3. Improve report detail and error handling
4. Add more representative test files
5. Add simple heuristic mesh guidance only if the core output is trustworthy

### Phase 1C: Value expansion
1. Thin walls
2. Small features
3. Sharp edges
4. Small fillets
5. Duplicate faces
6. Self-intersection
7. Face orientation nuance
8. Healed STEP export
9. ML stub or integration only if still justified

### Phase 1D: Optional wrapper/polish
1. README/demo polish
2. Validation documentation
3. Optional UI wrapper over the same pipeline

---

## Phase 1A Scope

### In scope
- CLI-first Python package
- STEP file validation
- basic shape parsing
- JSON report output
- minimal but real geometry checks
- tests for the vertical slice

### Out of scope for Phase 1A
- UI
- BRepNet integration
- all 11 checks
- full mesh recommendation system
- complex auto-heal workflow
- production-grade assembly intelligence

---

## Phase 1A File Map

### Create first
- `README.md`
- `environment.yml`
- `requirements.txt`
- `simready/__init__.py`
- `simready/validator.py`
- `simready/parser.py`
- `simready/report.py`
- `simready/pipeline.py`
- `simready/cli.py`
- `tests/conftest.py`
- `tests/test_validator.py`
- `tests/test_parser.py`
- `tests/test_report.py`
- `tests/test_pipeline.py`
- `tests/test_cli.py`

### Optional in Phase 1A if clearly needed
- `simready/checks/__init__.py`
- `simready/checks/core.py`
- `tests/data/`

Do **not** create a bunch of speculative modules before they earn their place.

---

## Phase 1A Essential Checks Only

Implement these first:
1. file load failure / invalid STEP / null shape / global validation gate
2. degenerate geometry
3. non-manifold edges
4. gaps or open boundaries
5. short edges

Why these first:
- they provide real simulation-readiness value early
- they are enough to prove the product loop
- they reduce the risk of false-positive noise from harder checks

---

## Phase 1A Tasks

### Task 1: Repo scaffold and environment

**Create:**
- `simready/`
- `tests/`
- `tests/data/`
- `README.md`
- `environment.yml`
- `requirements.txt`
- `.gitignore`

**Requirements:**
- keep dependencies minimal
- solve environment risk early
- verify one tiny STEP read before deeper coding

**Done when:**
- project structure exists
- environment spec is written
- OCC import test succeeds locally

---

### Task 2: Validator

**Create:**
- `simready/validator.py`
- `tests/conftest.py`
- `tests/test_validator.py`

**Responsibilities:**
- file exists check
- STEP read status check
- null shape check
- optional global OCC validation gate if stable enough for MVP
- return structured validation result

**Done when:**
- valid STEP returns usable shape
- invalid/missing STEP returns structured critical failure

---

### Task 3: Parser

**Create:**
- `simready/parser.py`
- `tests/test_parser.py`

**Responsibilities:**
- extract basic geometry facts from valid shape
- face count
- edge count
- bounding box
- maybe solid count if cheap and reliable

**Done when:**
- parser returns stable structured geometry summary for a simple part

---

### Task 4: Essential checks

**Create:**
- lightweight check functions in `validator.py`, `parser.py`, or a tiny `checks/` package only if that improves clarity

**Implement only:**
- degenerate geometry
- non-manifold edges
- gaps/open boundaries
- short edges

**Rules:**
- keep thresholds explicit and configurable later
- prefer conservative detection over noisy detection
- if a check is unreliable, stub it cleanly or defer it

**Done when:**
- checks produce structured findings with severity and suggestion text

---

### Task 5: Report builder

**Create:**
- `simready/report.py`
- `tests/test_report.py`

**Responsibilities:**
- stable JSON-friendly output
- input file summary
- geometry summary
- findings list
- top-level readiness/status field

**Done when:**
- report shape is predictable and can be asserted in tests

---

### Task 6: Pipeline orchestrator

**Create:**
- `simready/pipeline.py`
- `tests/test_pipeline.py`

**Responsibilities:**
- wire validator → parser → checks → report
- fail fast on critical input issues
- keep orchestration simple and readable

**Done when:**
- one function can run the end-to-end analysis and return a report object

---

### Task 7: CLI

**Create:**
- `simready/cli.py`
- `tests/test_cli.py`

**Responsibilities:**
- command like `simready analyze input.step`
- print JSON to stdout
- optional output file path

**Done when:**
- CLI works end-to-end against a simple test file

---

### Task 8: Focused tests

**Responsibilities:**
- validate end-to-end vertical slice
- keep fixtures small and synthetic
- test clean path and critical failure path first

**Do not do yet:**
- huge synthetic data generator
- broad benchmarking
- fake “complete coverage” theater

---

## Architecture Guardrails

- `pipeline.py` stays the orchestrator
- CLI is the primary interface
- UI is a later wrapper, not the core
- design for extension, but do not prebuild unused layers
- avoid creating ML or UI modules during Phase 1A
- do not treat all checks as equally easy or equally reliable

---

## Risks to manage early

### 1. OCC environment pain
Biggest practical risk.

**Mitigation:**
- solve environment first
- verify import and one STEP read immediately

### 2. Over-scoping
Biggest planning risk.

**Mitigation:**
- hold Phase 1A line
- only add modules when the working slice demands them

### 3. False positives
Biggest product risk.

**Mitigation:**
- conservative thresholds
- simple clean test parts early
- prioritize trust over breadth

---

## Exit Criteria for Phase 1A

Phase 1A is complete when SimReady can:
- accept a STEP file from CLI
- reject broken input cleanly
- read a valid file
- extract basic geometry summary
- run the essential checks
- output a stable JSON simulation-readiness report
- pass focused tests for the above

If that works, the MVP loop is real.

---

## Blunt summary
This plan intentionally cuts ambition.
That is the point.

The right move is to prove the core loop fast, keep the output trustworthy, and earn the next layer of complexity after the CLI slice works.
