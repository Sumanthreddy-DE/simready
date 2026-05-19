# SimReady — Domain Glossary

Canonical terms for this codebase. Read this before writing or reviewing code so vocabulary matches.

## Domain (FEA pre-processing)

- **STEP file** — Neutral CAD exchange format (ISO 10303). `.step` / `.stp`. Boundary representation, not mesh. Input to the SimReady pipeline.
- **BRep (boundary representation)** — Solid model defined by faces, edges, vertices, and their topology. Distinct from mesh-based or constructive (CSG) representations.
- **FEA (finite element analysis)** — Numerical simulation (stress, thermal, modal, …) that requires a *meshed* model. SimReady does NOT do FEA; it prepares the BRep for meshing.
- **FEA-ready** — A STEP that will mesh cleanly: manifold, no zero-length edges, no slivers, no self-intersections, no thin solids, refinement hints present where curvature is high.
- **Mesh** — Discretised representation (tets, hexes, …) produced *downstream* of SimReady by a mesher. Out of scope here.
- **Refinement** — Per-face hint that local mesh density should be higher (typically at curved features or stress concentrators). One of two BRepSAGE outputs.
- **Complexity tier** — `simple` / `moderate` / `complex` / `very_complex` w/ a confidence scalar. Rough surrogate for mesh cost. Combined output of rule + ML layers.
- **Manifold** — Every edge bounds exactly 2 faces. Non-manifold = a meshing dealbreaker. `check_open_shell` enforces this.
- **Sliver face / sliver edge** — Geometry with extreme aspect ratio (a face that is essentially a line, an edge much shorter than its neighbours). Crashes meshers. `check_sliver_face` and `check_thin_solid` cover this.
- **Self-intersection** — A solid whose boundary intersects itself. Detected via `BOPAlgo_ArgumentAnalyzer` with `SelfInterMode` (NOT via `BRepAlgoAPI_Common(s,s)` — that gives a false positive on every solid; see `lessons_pythonocc-gotchas`).
- **ShapeFix** — OCC's healing layer (`ShapeFix_Shape`). Tolerated-edge cleanup, small-edge removal, etc. The SimReady pipeline runs ShapeFix before checks.

## Pipeline parts (live)

- **`analyze_file`** — Top-level entry. Validate → parse → ShapeFix → split bodies → run checks → build report. 120 s thread timeout wrapper, per-check try/except (broken check skips w/ Info, doesn't abort).
- **`run_essential_checks_detailed`** — Sequential 12-check pass. Each check returns `(severity, message, per_face_or_edge_data)`.
- **`combiner`** — Fuses rule severity counts + ML face scores into `combined_per_face_scores`, overall score, complexity tier. Uses **0-based face indexing throughout** (rule + ML + body checks all unified via `simready.occ_utils.iter_faces`; pre-2026-05-13 there was a 1-vs-0 bug — never reintroduce 1-based indexing).
- **`BRepSAGE`** — 2-layer GraphSAGE GNN, 32 hidden, multi-task head (refinement classification + complexity regression). PyG. CPU-trainable. Weights at `weights/brepnet.pt`. Dual-backend: real checkpoint when present, graph-feature heuristic when not. **Always report `weights_loaded`, `model_name`, `score_source` honestly** — pre-2026-05-13 it lied (claimed weights loaded while running heuristic); fixed in `run_brepnet_inference`.

## Copilot parts (Path C, current)

- **Copilot** — LLM agent loop. Three tools, multi-turn, conversation history round-tripped via `AgentResponse.messages`.
- **Tools** — Pure-Python functions exposed as OpenAI-compatible tool schemas. NOT autonomous code execution.
  - `analyze_geometry(step_path)` — Wraps `analyze_file`. Returns slim summary + `severity_counts` (LLMs choke on full report; summarizer + truncator drops large fields).
  - `suggest_fixes(findings_json)` — Templated ranked actions. No LLM call inside.
  - `lookup_standard(topic, k=3)` — RAG over FEA PDFs. **Corpus currently empty → returns `{"status": "no_index"}`**. BACKLOG `fea-rag-corpus-empty` tracks fill.
- **RAG-lite** — Sentence-transformers embeddings + cosine over a JSON index. NOT a vector DB. Pre-normalised vectors, `argpartition` top-k. Suited for ≤10 docs; switch to a real DB if corpus grows.
- **System prompt** — Verdict-with-score → Issues → Fixes → Citations. 3 reference dialogues. Format violations get re-prompted, not auto-corrected.
- **`on_event` observer** — Per-turn Rich panels in CLI; same hook used by Streamlit UI for live event stream.

## Environments

- **`sr` env** — `C:\mm\sr\python.exe`, Python 3.10, pythonocc-core 7.9, torch 2.12.0+cpu, torch_geometric 2.7.0. **The only env where the full test suite passes (160/160).** Use this for OCC + ML work.
- **Base env** — Python 3.12 system install. No pythonocc, no torch_geometric. 33 pre-existing failures expected. Use for copilot-only (non-OCC) work and lightweight smokes.
- **PYTHONPATH** — Prepend `$env:PYTHONPATH = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady"` before any script. PowerShell here-strings + module imports get tripped without it.

## Avoid these terms

- **"validate"** for the full pipeline — reserve `validate` for the up-front STEP-syntax check. The full pass is `analyze`.
- **"refine"** — ambiguous (could mean ShapeFix healing or BRepSAGE refinement hint). Say which.
- **"score"** without prefix — say `face_score`, `combined_score`, `overall_score`, or `brepnet_score`.
- **"mesher" / "solver"** — out of scope; SimReady does not do these.
- **"agent"** — only the copilot loop is the agent. Don't call `analyze_file` an agent.

## Resume bullet (apply-ready, 2026-05-18)

> Built SimReady Copilot — agentic LLM system (OpenAI-compatible multi-turn tool-use loop) that ingests STEP CAD files, runs a BRepSAGE GNN analysis pipeline, and returns ranked manufacturability fix suggestions with RAG-cited FEA-standard references; shipped as a Streamlit app with 3D face-score visualization, 160 passing tests.

---

## Stakeholders / external context

- **MecAgent** — Target employer (ML/AI Founding Engineer role). Application date: wk-2 day-14 (~2026-05-23). Demo screen-recording + repo link + 1-page bullet list = apply package. See `project_mecagent-alignment.md`.
- **GrabCAD** — Source of real-world STEPs. Anti-bot + login walls block scraping; pivot is curated 10-STEP manual download.
- **NAFEMS / ASME PTC** — Authoritative FEA standards, but mostly paywalled. Public fallbacks for the RAG corpus: vendor whitepapers, MIT OCW, NIST handbook chapters.

## Example dialogue (matches the system prompt)

> **User:** What's wrong with this bracket?
>
> **Copilot:** *[calls `analyze_geometry`]*
> **Verdict: not FEA-ready (score 42/100).**
> Issues:
> 1. Open shell on face 7 (non-manifold edge).
> 2. Sliver face on face 14 (aspect ratio 1:340).
> 3. ThinSolid: overall aspect ratio 1:180 — meshing will need shell elements.
> Fixes:
> 1. Close shell at face 7 (try `ShapeFix_Shell`).
> 2. Merge or remove sliver face 14.
> 3. Consider shell-element discretisation given the part thickness.
> Citations: *(none — `lookup_standard` returned no_index; FEA corpus not yet built.)*

## Live source-of-truth files

- `BACKLOG.md` (repo root) — open issues by severity.
- `docs/exec-plans/path-c-4week.md` — full plan + progress.
- `docs/validation/` — synth + real-CAD validation tables.
- `docs/impl/brepnet-implementation-notes.md` — BRepSAGE model + dataset notes.
- `BACKLOG.md` Strategic Context section — wk-3 priorities, contrarian review summary, gaps vs JD table.
- `~/.claude/projects/C--.../memory/project_simready.md` — live status (this file's companion in auto-memory).
