# SimReady

AI-assisted simulation pre-processing tool for structural FEA. Takes a STEP file, outputs a simulation-readiness report with geometry health checks and auto-healing.

## The Problem

Before running FEA, engineers spend 30-60 minutes manually inspecting CAD geometry: checking for thin walls, non-manifold edges, small features, gaps, and other issues that break or degrade meshing. No open-source tool automates this.

## What SimReady Does Today (Phase 1)

```
STEP file  -->  SimReady  -->  JSON readiness report + optional healed geometry
```

- **Validates** STEP input (file integrity, null shape, global geometry check)
- **Auto-heals** topology on files that pass initial validation, via OCC ShapeFix (gap stitching, wire repair, face fixes). Note: files that fail global BRepCheck validation are currently rejected before healing. A two-pass validate-heal-revalidate flow is planned for Phase 2.
- **Analyzes** geometry with 10 rule-based checks (see table below)
- **Splits** multi-body files and reports per body
- **Exports** healed geometry as a new STEP file

## Quick Start

### Prerequisites

SimReady requires `pythonocc-core`, which is only available through conda/mamba:

```bash
# Create environment
micromamba create -f environment.yml
micromamba activate simready

# Or with conda
conda env create -f environment.yml
conda activate simready
```

### Usage

```bash
# Analyze a STEP file
python -m simready.cli analyze part.step

# Save report to file
python -m simready.cli analyze part.step --output report.json

# Export healed geometry
python -m simready.cli analyze part.step --export-healed part_healed.step

# All options
python -m simready.cli analyze part.step --output report.json --export-healed part_healed.step
```

### Example Output

```json
{
  "input_file": "bracket.step",
  "status": "ReviewRecommended",
  "summary": {
    "total": 2,
    "by_severity": {"Critical": 0, "Major": 0, "Minor": 2, "Info": 0},
    "major_checks": []
  },
  "validation": {"is_valid": true, "errors": []},
  "geometry": {
    "face_count": 24,
    "edge_count": 48,
    "solid_count": 1,
    "bounding_box": {"xmin": 0.0, "ymin": 0.0, "zmin": 0.0, "xmax": 80.0, "ymax": 40.0, "zmax": 15.0}
  },
  "findings": [
    {
      "check": "SmallFilletsOrHoles",
      "severity": "Minor",
      "detail": "Detected 2 cylindrical faces with radius below 2.4",
      "suggestion": "Inspect small fillets or holes that may need defeaturing or local refinement."
    }
  ],
  "heal": {"attempted": true, "applied": true, "valid_before": true, "valid_after": true},
  "bodies": []
}
```

## Architecture

Five-stage pipeline, CLI-first:

```
STEP file
  |
  v
Stage 1: File Validation (validator.py)
  - File exists, STEP readable, shape not null, BRepCheck passes
  |
  v
Stage 2: Auto-Heal (healer.py)
  - OCC ShapeFix topology repair on whole shape, optional healed STEP export
  |
  v
Stage 3: Parse + Check whole shape (parser.py, checks.py)
  - Face/edge/solid counts, bounding box, 10 geometry checks
  |
  v
Stage 4: Split + Per-Body Analysis (splitter.py)
  - If multi-body: split into solids, run parse + check on each body
  |
  v
Stage 5: Report Generator (report.py)
  - JSON output with findings, severity, suggestions
  |
  v
CLI (cli.py)
```

Note: In the current implementation, per-body analysis also runs healing on each body individually. This double-healing is a known issue and will be fixed in Phase 2 (heal once at the top level, pass healed bodies downstream).

## Geometry Checks

| Check | Severity | What It Detects |
|-------|----------|----------------|
| Degenerate geometry | Major | Zero-area faces, zero-length edges, collapsed topology |
| Non-manifold edges | Major | Edges shared by more than 2 faces |
| Open boundaries | Major | Open edges, non-watertight shells |
| Short edges | Major/Minor | Edges below 0.5% of max dimension |
| Thin walls | Major | Bounding box aspect ratio below threshold |
| Small features | Minor | Faces/edges below 2% of part scale |
| Small fillets/holes | Minor | Cylindrical faces with radius below 3% of max dimension |
| Duplicate bodies | Major | Overlapping solids (bounding box heuristic) |
| Duplicate faces | Major/Minor | Coincident faces (bounding box heuristic) |
| Orientation nuance | Minor | Face-only geometry without closed solid |

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| Critical | File unreadable, no valid solid | Pipeline aborts |
| Major | Defect that blocks meshing | Must fix before simulation |
| Minor | Quality issue that degrades mesh | Warning with suggestion |
| Info | Clean area or optimization hint | No action needed |

## Running Tests

```bash
# All tests (requires pythonocc environment)
python -m pytest tests/ -v

# Tests that work without pythonocc (pure logic)
python -m pytest tests/test_report.py tests/test_checks.py::test_summarize_findings_counts_by_severity -v
```

## Project Structure

```
SimReady/
  simready/
    __init__.py
    cli.py            # Click CLI entry point
    pipeline.py       # Orchestrator: validate -> heal -> parse -> check -> report
    validator.py      # STEP file validation
    parser.py         # Geometry extraction
    healer.py         # OCC ShapeFix auto-healing
    splitter.py       # Multi-body detection and splitting
    checks.py         # Rule engine (10 geometry checks)
    report.py         # Report generation
  tests/
    conftest.py       # Shared fixtures
    data/             # Synthetic STEP test files
    test_*.py         # Per-module tests
  docs/               # Implementation notes and references
  environment.yml     # Conda environment spec
  requirements.txt    # Pip dependencies
  LICENSE             # MIT
```

## Tech Stack

| Component | Library |
|-----------|---------|
| STEP parsing | pythonocc-core (OpenCASCADE Python bindings) |
| File validation | OCC BRepCheck_Analyzer |
| Auto-healing | OCC ShapeFix |
| CLI | Click |
| Testing | pytest |

## Roadmap

### Shipped
- [x] Phase 1: CLI pipeline, rule engine, auto-healing, multi-body support, JSON reports

### Planned (Phase 2)
- [ ] ML layer — BRepNet per-face complexity scoring on B-Rep topology
- [ ] Human-readable reports — terminal pretty-print (0-100 score) + HTML single-file report
- [ ] Validate-heal-revalidate flow — let healer attempt repair before rejecting invalid geometry
- [ ] Additional checks — sharp edges (dihedral angle), self-intersection, improved gap/overlap detection
- [ ] Real-world validation — SimJEB brackets, GrabCAD models
- [ ] Visual UI — Streamlit + PyVista with 3D colored overlays

### Future (Phase 3+)
- [ ] IGES file support (`IGESControl_Reader`)
- [ ] pip packaging (`pyproject.toml`)
- [ ] REST API
- [ ] Boundary condition suggestions

## License

[MIT](LICENSE)
