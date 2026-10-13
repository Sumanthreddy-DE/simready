# Archive

Frozen artefacts from earlier project phases. Not loaded by anything; kept for reference only.

## Layout

```
Archive/
├── phase-1/           # Phase 1 plan + design (CLI pipeline; shipped pre-April 2026)
├── phase-2/           # Phase 2 plan + design (ML + Streamlit; superseded by Phase 2A end-to-end ship 2026-05-13)
├── phase-3/           # Phase 3 plan + checklist (demo hardening; merged 2026-05-13, plan file partly aspirational)
├── brainstorming/     # Early exploration docs (deep-research, brainstorm session)
├── memory/            # Deprecated auto-memory files (open-questions migrated to BACKLOG.md)
├── sessions/          # Local only since 2026-10-10 (gitignored); see below
├── gencad-colab-download-2026-10-07/   # Local only; raw Colab download of the GenCAD results
├── ChaGPT-deep-research-report-2.md   # Pre-existing deep-research artefacts
└── ChatGPT-deep-research-report-1.md
```

## What lives where

### `phase-1/`
- `SimReady-Phase1-Plan.md` — Phase 1 work plan. Done.
- `SimReady-Phase1-Design.md` — Phase 1 design doc. Done.

### `phase-2/`
- `SimReady-Phase2-Plan.md` — Phase 2 work plan. Phase 2A completed end-to-end (real BRepSAGE trained + validated); 2B/2C partial. See `project_simready.md` in memory dir for live status.
- `SimReady-Phase2-Design.md` — Phase 2 design doc.

### `phase-3/`
- `SimReady-Phase3-Plan.md` — Phase 3 work plan (871 lines, partly aspirational). Demo-hardening subset shipped 2026-05-13.
- `memory_phase3_checklist.md` — Phase 3 ship checklist. All Phase 3 items done.

### `brainstorming/`
- `Brainstorming-Session-2026-04-15.md` — Early scope brainstorm. Superseded by Path C decisions (`project_path-c-decisions.md`).
- `deep-research-report.md` — Pre-Path-C research dump.

### `memory/`
- `project_open-questions-wk2.md` — Wk-1 → wk-2 transition questions. All items migrated to `BACKLOG.md` at repo root on 2026-05-17. Kept for history.

### `sessions/`
- `2026-04-21-SimReady-session.tmp` … `2026-04-24-SimReady-session.tmp` — Stale `.tmp` files from old `/save-session` skill version that wrote to `~/.claude/session-data/`. Current skill writes per-project to `~/.claude/projects/<slug>/sessions/` instead. Moved here so the global session-data dir is not cluttered with cross-project files. Untracked from the public repo on 2026-10-10 (`6e0a938`, `Archive/sessions/*.tmp` gitignored); backups in `Projects/_archive/SimReady-sessions-2026-04/`.

### `gencad-colab-download-2026-10-07/` (local only, not in git)
- Raw Colab/Drive download of the first GenCAD eval: generations, both score files, and the 88 generated STEPs as a zip. Verified 2026-10-13 to match the committed copy in `docs/validation/gencad/` (JSON content identical; all 88 STEPs identical apart from line endings). Kept only as the original download; the committed copy is canonical. Excluded locally via `.git/info/exclude`.

### `planning/`
- `next-iteration-notes.md` — End-of-wk-2 contrarian review (2026-05-18). All action items migrated to `BACKLOG.md` Strategic Context section on 2026-05-19. Kept for full narrative.

## Source of truth (live, not here)

- Open issues: `<repo>/BACKLOG.md`
- Current plan: `<repo>/docs/exec-plans/path-c-4week.md`
- Live status: `~/.claude/projects/C--Users-suman-Desktop-Docs-Job-Projects-Mech-SimReady/memory/project_simready.md`
- Locked decisions: same memory dir, `project_path-c-decisions.md`
