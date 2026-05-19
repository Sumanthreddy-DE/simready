# SimReady

AI-assisted simulation pre-processing tool for structural FEA. Takes a STEP file, analyzes geometry quality, applies safe healing, and outputs simulation-readiness reports in terminal, JSON, and HTML formats.

## What SimReady Does Now

```
STEP file  -->  SimReady  -->  readiness score + findings + optional healed geometry
```

Current Phase 3 state includes:
- two-pass validation and healing flow
- rule-based geometry checks with per-face scoring groundwork
- custom B-Rep graph extraction for ML features
- BRepNet inference scaffold with graceful fallback behavior
- rule + ML score fusion into a unified 0-100 score
- terminal pretty-print output
- self-contained HTML report generation
- Streamlit UI for demo-ready data exploration
- multi-body handling with per-body reports
- complexity tier and confidence hints for larger models

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

## Demo

### Terminal
```bash
python -m simready.cli analyze tests/data/smoke_box.step
python -m simready.cli analyze tests/data/multi_body.step --verbose
python -m simready.cli analyze tests/data/open_face.step --html report.html
```

### Streamlit UI
```bash
streamlit run ui/app.py
```
Upload any STEP file to see the full analysis report.

A browser-driven smoke test script is also included:
```bash
node scripts/ui_smoke.js
```
It uploads `tests/data/smoke_box.step` to a running local Streamlit app and verifies key UI sections are rendered.

### Batch Analysis
```bash
python scripts/demo_analysis.py
```

## Copilot (Path C, work-in-progress)

LLM-orchestrated tool-use wrapper around the SimReady pipeline. Three tools (`analyze_geometry`, `suggest_fixes`, `lookup_standard`) and an OpenAI-compatible client (use OpenAI, OpenRouter, NVIDIA NIM, or local Ollama-with-OpenAI-shim by swapping `OPENAI_BASE_URL`).

### Setup

```bash
pip install -r requirements.txt   # adds openai, sentence-transformers, pypdf
cp .env.example .env              # set OPENAI_API_KEY (and OPENAI_BASE_URL if non-OpenAI)
```

Optional — build the FEA standards index for `lookup_standard`:

```bash
# 1. Paste public PDF URLs into data/fea_docs/sources.txt (one per line)
python scripts/scrape_fea_docs.py
# 2. Chunk + embed → data/fea_docs_index.json
python scripts/index_fea_docs.py
```

### Try the copilot

```bash
# Rich-formatted terminal chat with tool-call panels
python -m simready.copilot.cli tests/data/grabcad/bracket_simple.STEP \
    "What manufacturing issues does this part have?"

# Plain text fallback (no rich)
python -m simready.copilot.cli tests/data/grabcad/manifold_complex.STEP --no-rich

# Don't persist the session transcript
python -m simready.copilot.cli tests/data/grabcad/housing_moderate.stp --no-save
```

Sessions are saved to `data/copilot_sessions/<timestamp>_<part>.json` by default (gitignored).

## Phase 3 Architecture

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
rule/ML score fusion + complexity tier
  |
  v
terminal report / JSON / HTML / Streamlit UI
```

## Report Outputs

### Terminal
Default CLI output is a readable summary with:
- unified 0-100 readiness score
- geometry counts
- graph topology summary
- top findings
- optional per-face scores with `--verbose`

### JSON
Use `--json` for scripting and downstream tooling.

### HTML
Use `--html report.html` for a single-file shareable report.

### Streamlit
Use `streamlit run ui/app.py` for an interactive demo UI with findings tables, score breakdown, graph metadata, and download buttons.

## ML Layer Notes

SimReady includes:
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
- `scripts/demo_analysis.py`
- `scripts/download_grabcad_samples.py`
- `scripts/generate_degraded_steps.py` — auto-introduce defects (zero-length edges, open shells, sliver faces, self-intersections) into clean parametric STEPs to lift recall on real-world parts

These support fixture analysis, demo workflows, and future model fine-tuning.

Degraded-synthetic generator usage:

```bash
python scripts/generate_degraded_steps.py \
    --input data/parametric --output data/parametric_degraded \
    --max-inputs 50
```

Each input STEP yields up to 4 degraded variants (one per defect class) plus a `.tags.json` sidecar with the ground-truth defect label, ready to feed back into `auto_label.py` + `train.py` for the recall fix in week 2.

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
    demo_analysis.py
    download_grabcad_samples.py
  ui/
    app.py
    viz.py
  tests/
  simready/report_schema.json
  environment.yml
  requirements.txt
```

## Phase 3 Completion Status

Completed:
- Pre-Task 0 OCC hardening fixes
- pipeline timeout and exception hardening
- complexity tier and confidence reporting
- Streamlit demo UI rewrite
- HTML and terminal report polish
- demo batch analysis script
- GrabCAD smoke-test scaffolding
- environment and README cleanup

Pending final validation:
- run final real-world checks on 3 manually downloaded GrabCAD STEP files
- optional manual browser walkthrough on additional fixtures beyond the automated smoke test

## Current Caveats

- BRepNet model uses heuristic fallback (geometry-based scoring) — actual neural weights require fine-tuning on labeled data.
- pythonocc-core 7.9+ required (older versions may have API incompatibilities).
- Streamlit UI provides data visualization only — no 3D CAD rendering.
- Test coverage is comprehensive for the analysis pipeline; real-world validation on industrial parts is ongoing.

## License

[MIT](LICENSE)
