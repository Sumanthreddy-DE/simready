# SimReady

CLI-first simulation-readiness checker for STEP CAD files.

## What Phase 1 does now
SimReady can:
- validate STEP input
- parse basic geometry summary
- run simulation-readiness heuristics
- auto-heal conservatively with OCC ShapeFix
- split multi-body files and report per body
- emit stable JSON through the CLI
- optionally export a healed STEP file

## Current CLI

```bash
python -m simready.cli analyze part.step
python -m simready.cli analyze part.step --output report.json
python -m simready.cli analyze part.step --export-healed part_healed.step
```

## Current checks and heuristics
- invalid or unreadable STEP input
- null shape / global validation failure
- degenerate geometry
- non-manifold edges
- open boundaries
- short edges
- thin walls
- small features
- small holes / cylindrical features
- duplicate body heuristic
- duplicate face heuristic
- orientation nuance for non-solid face geometry

## Current output shape
Top-level JSON includes:
- `input_file`
- `status`
- `summary`
- `validation`
- `geometry`
- `findings`
- `bodies`
- `heal`
- optional `healed_export`

## Deliberately not in Phase 1
- UI
- ML integration
- full production-grade geometry intelligence
- solver-specific mesh recommendations

## Environment
A working local micromamba-based env was used during development.

Typical run pattern:

```bash
~/bin/micromamba run -n simready python -m simready.cli analyze tests/data/smoke_box.step
```
