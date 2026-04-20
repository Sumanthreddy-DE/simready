# SimReady

CLI-first simulation-readiness checker for STEP CAD files.

## Phase 1A goal
Build the thinnest credible MVP loop:
- validate STEP input
- extract basic geometry summary
- run a few essential checks
- emit a stable JSON report through CLI

## Planned command

```bash
python -m simready.cli analyze part.step
```

## Current Phase 1A scope
- validator
- parser
- report builder
- pipeline orchestrator
- CLI
- focused tests

## Deferred
- UI
- ML integration
- full 11-check suite
- advanced healing and mesh recommendations
