# SimReady

AI-assisted simulation pre-processing tool for structural FEA. Takes a STEP file, analyzes geometry quality, applies safe healing, and outputs simulation-readiness reports in terminal, JSON, and HTML formats.

## What SimReady Does Now

```
STEP file  -->  SimReady  -->  readiness score + findings + optional healed geometry
```

Current Phase 2 state includes:
- two-pass validation and healing flow
- rule-based geometry checks with per-face scoring groundwork
- custom B-Rep graph extraction for ML features
- BRepNet inference scaffold with graceful fallback behavior
- rule + ML score fusion into a unified 0-100 score
- terminal pretty-print output
- self-contained HTML report generation
- dataset auto-label and training scaffolding
- multi-body handling with per-body reports

## Quick Start

### Prerequisites

SimReady requires `pythonocc-core`, so use the conda/mamba environment:

```bash
micromamba create -f environment.yml
micromamba activate simready
```

### Usage

```bash
# Default: pretty terminal report
python -m simready.cli analyze part.step

# Raw JSON
python -m simready.cli analyze part.step --json

# Save JSON + HTML report
python -m simready.cli analyze part.step --output report.json --html report.html

# Export healed geometry
python -m simready.cli analyze part.step --export-healed part_healed.step

# Verbose per-face terminal output
python -m simready.cli analyze part.step --verbose
```

## Phase 2 Architecture

```
STEP file
  |
  v
validate_file_load -> validate_brep
  |
  +-> if invalid: heal -> revalidate
  |
  v
parse geometry + rule checks
  |
  v
extract B-Rep graph
  |
  v
BRepNet inference scaffold
  |
  v
rule/ML score fusion
  |
  v
terminal report / JSON / HTML
```

## Report Outputs

### Terminal
Default CLI output is a readable summary with:
- unified 0-100 readiness score
- geometry counts
- top findings
- optional per-face scores with `--verbose`

### JSON
Use `--json` for scripting and downstream tooling.

### HTML
Use `--html report.html` for a single-file shareable report.

## ML Layer Notes

SimReady now includes:
- `simready/ml/graph_extractor.py` for custom face/edge/coedge extraction
- `simready/ml/brepnet.py` for checkpoint-aware inference scaffolding
- `simready/ml/combiner.py` for per-face rule/ML fusion and overall scoring

If BRepNet weights are unavailable, SimReady falls back gracefully instead of failing hard.

## Dataset and Training Scaffolding

Scripts included:
- `scripts/auto_label.py`
- `scripts/download_fusion360.py`
- `scripts/train.py`
- `scripts/evaluate.py`

These are scaffolds for the Fusion360 Gallery subset workflow and Colab-friendly fine-tuning path.

## Project Structure

```
SimReady/
  simready/
    cli.py
    pipeline.py
    validator.py
    parser.py
    healer.py
    splitter.py
    checks.py
    occ_utils.py
    report.py
    html_report.py
    templates/report.html
    ml/
      graph_extractor.py
      brepnet.py
      combiner.py
  scripts/
    auto_label.py
    download_fusion360.py
    train.py
    evaluate.py
  ui/
    app.py
    viz.py
  tests/
  report_schema.json
  environment.yml
  requirements.txt
```

## Current Caveats

- Full BRepNet model wiring is still scaffold-level, not final production inference.
- Real-world validation set coverage is still pending.
- UI work now has a Streamlit scaffold in `ui/app.py`, but 3D OCC/PyVista face rendering is still pending.
- Actual pytest execution still depends on a populated project environment with pythonocc installed.

## License

[MIT](LICENSE)
