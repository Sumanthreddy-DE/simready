# SimReady Backlog

Living list of open issues, deferred work, and known caveats. Updated each session.

---

## Strategic Context (wk-3, updated 2026-05-19)

**Three critical demo credibility gaps (from contrarian review, end of wk-2):**
1. `lookup_standard` returns `no_index` always — third copilot tool is dead in every live demo. Fix: populate RAG corpus.
2. BRepSAGE real-CAD recall is ~0.23. UI gives no warning. Engineers get silently unreliable ML scores on real parts (>200 faces). Fix: ML confidence banner.
3. Text-only fix suggestions are useless to engineers in NX/SolidWorks. Fix: auto-heal + return STEP download.
4. `check_self_intersection` silently skips above 150 faces — most important check is invisible on production geometry. Fix: surface skip warning explicitly.

**Gaps vs JD (MecAgent ML/AI Founding Engineer):**

| JD Requirement | SimReady State | Gap |
|---|---|---|
| Geometry generation | Not built | Hard gap — analysis only |
| Tool orchestration | 3 tools, multi-turn | Thin — LLM is mostly a prose wrapper |
| GNN / embeddings | BRepSAGE trained, real-CAD recall 0.23 | Recall gap on non-parametric geometry |
| Model fine-tune pipeline | Not done yet | Clear JD requirement, wk-3 task |
| Production ML + CAD APIs | pythonocc + Streamlit demo | No deployment, no mesher hook |
| Bridge AI + real workflows | Upload → chat → colored PNG | No healed STEP output, no mesher integration |

**Wk-3 priority order (decided 2026-05-19):**
1. Fix broken demo (S1 RAG corpus + S2 self-intersection warning + S2 ML confidence banner) — ~2.5 days
2. Heal + return STEP (S2) — closes biggest ME frustration, demonstrates OCC depth — ~2 days
3. Fine-tune pipeline (exec plan days 15-17) — clear JD requirement — remaining days
4. Param-CAD generation — wk-4 stretch only (risky, deferred)

---

**Severity rubric**
- **S1** — blocker / data loss / broken demo. Fix before next ship.
- **S2** — UX gap, missing polish recruiters will notice, deferred decision.
- **S3** — tech debt, deprecations, low-impact polish, dead code.

**Conventions**
- New issue → append to correct severity section.
- Mention by short slug in commit body (e.g. "Closes: multi-turn-history").
- On close → move to **Done this session** with commit SHA.
- End of session → user sweeps **Done** → **Archived** (one-line compress).
- Last swept: **2026-05-24** (ran the two pending wk-3 runs to completion: trace gen 1455, 70B gold baseline n=50; added eval pacing flags; fixed brepbndlib; relocated all stale `[x]` items out of Open into Done/Archived; reconciled apply status — confirmed **applied 2026-05-18**, corrected a mid-session mis-conclusion).

---

## Open — S1 (blocker / broken demo)

_(none open)_

---

## Open — S2 (UX gap, polish, deferred decisions)

- [ ] **S2 · readme-polish** — README still reflects Phase-3-era framing; needs hero block + Copilot (Path C) section at top. Note: MecAgent already applied 2026-05-18, so this is **interview-prep** polish (not an apply gate) — do before any interview / at wk-4 start. *Opened 2026-05-14.*
- [ ] **S2 · grabcad-scrape-blocked** — `download_grabcad_samples.py` is a manual stub; site has anti-bot + login walls. Pivot to curated 10-STEP manual-download set instead of scraping 20–30. **Blocks day-9 GNN combined retrain** (the higher-signal technical deepening). *Opened 2026-05-14 (wk-1 Q2).*
- [ ] **S2 · gmsh-calibration** *(user task)* — Run 10-15 STEPs from `tests/data/` through Gmsh at 2mm target: `gmsh part.step -3 -clmax 2 -o part.msh`. Record pass/fail + worst element quality. Correlate with SimReady score. Even rough correlation makes every score claim on the resume defensible. Requires: download Gmsh from https://gmsh.info (~100 MB, free). *Opened 2026-05-19.*

---

## Open — S3 (tech debt, deprecations, low-impact polish)

- [ ] **S3 · base-vs-env-marker-split** — Two-Python-env reality (base 3.12 vs `C:\mm\sr` 3.10) keeps confusing tests. Add `pytest -m base` vs `pytest -m occ` marker split + a Makefile/PS shortcut. Less acute now that env is verified working, but the gotcha remains. *Opened 2026-05-14 (wk-1 Q5).*
- [ ] **S3 · adr-backlog** — Write 2–3 ADRs under `docs/adr/` for Path C decisions that will be hard to reconstruct in 6 months: (1) OpenAI-compatible SDK over Anthropic-native (why `base_url` swap matters), (2) RAG-lite JSON + cosine over a vector DB (corpus size assumption), (3) multi-turn loop pattern w/ `AgentResponse.messages` round-trip. Useful for the interview narrative. *Opened 2026-05-17.*

---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session (2026-05-24)

- **trace-gen-restart** (S2) — resumed 1368 → **1455 traces** (8B, NIM; 45 lost to 429s, resume-safe, exit 0). Ample for 3B QLoRA.
- **gold-eval-incomplete** (S2) — full **70B gold baseline n=50, errors=0** (`tool_call_exact 0.760`, `partial 0.920`, `tool_order 0.780`, `format 0.780`, `theme 0.678`). Added `--request-delay`/`--max-retries`/`--initial-backoff` to `eval_finetune.py` to survive NIM 429s; purged 3 stale partial gold blocks from `finetune_results.md`, filled the summary table's Llama-70B column.
- **brepbndlib-deprecation** (S3) — `brepbndlib_Add` → `brepbndlib.Add` static in `scripts/generate_degraded_steps.py`; verified no DeprecationWarning under `-W error`.
- **chore** — `logs/` added to `.gitignore`; refreshed `path-c-4week.md` (wk-3 run ticks, day-15/18-run-1 done) and `project_simready.md` memory; **reconciled apply status** — confirmed applied 2026-05-18 (`v0.4.0-apply`), corrected a mid-session mis-conclusion that it hadn't been sent.
- *(SHA: this session's commit — see `git log`.)*

---

## Archived (older sweeps, compressed)

- **2026-05-21 · wk-3 days 15-19 scaffolding** — `4e74ff0` (7 files / 1670 ins): `synth_tool_traces.py`, `prep_finetune_dataset.py`, `finetune_copilot.ipynb` (Colab T4 QLoRA on Qwen2.5-3B), `eval_finetune.py` (6 metrics), `finetune_results.md` template, gitignore `data/fine_tune/`. `trace-format-rot` closed by design. `project_api-key-todo` memory opened. 160/160 tests, no prod-code changes.
- **2026-05-19→20 · contrarian-review demo fixes** — `71ccacf` + `dd45eef`. Closed the 4 demo-credibility gaps: `fea-rag-corpus-empty` (rag.py API-rename + OpenBLAS-crash fixes, index rebuilt), `heal-return-step` (auto ShapeFix/ShapeUpgrade → healed-STEP download), `ml-confidence-banner` (unreliable-score banner when `face_count>200`), `self-intersection-skip-warning` (explicit "skipped N faces" finding above 150).

- **2026-05-18 · apply-timeline-tight** — Application sent to MecAgent at `v0.4.0-apply` (`34a93e7`). Item obsolete.
- **2026-05-13 · Phase 2A bug-fix sweep** (5 items) — see commits `b689b71`..`ec4f33a`. SelfIntersection false-positive, face index 0/1 mismatch, ML weights-loaded lying, GrabCAD manifold hang guard, rule_face_count rename.
- **2026-05-14 · Path C wk-1 ship** (6 days of work) — see commits `7212e52`..`d8fcc1f`. Copilot stack, 3 tools, RAG-lite, multi-turn loop, terminal UI, degraded-STEP generator.
- **2026-05-16 · Wk-1 Q1/Q6/Q8 resolved** — light real-LLM smoke (`563ab6c`) validated LLM loop end-to-end on NIM Llama. No tool_choice gotcha. Slim summary respected. Day-10 sub-decisions D1=b, D2=a, D3=mock-then-smoke locked.
- **2026-05-17 · Path C wk-2 day 10 ship** (4 items) — `056a746`..`69539ef`. Streamlit chat UI + dropdown dedupe, sidebar score badge, multi-turn history via `AgentResponse.messages` round-trip, Verdict-with-score format. Real-LLM smoke gained a turn-2 follow-up (10/10 NIM checks).
- **2026-05-17 · Path C wk-2 day 11 ship** (7 items) — `636d140`..`c3df6c0`. Static colored-face PNG via OCC tess + PIL painter's-algo (replaces deferred pyvista; matplotlib also broken in sr OCC env on Win); `check_thin_solid` detector + drop broken `zero_length_edge` synth; STEP file uploader + 5MB warn; typed `_classify_agent_exception` chips (RateLimit/Timeout/ConnError/Auth/BadRequest); `[synth]`/`[real]` dropdown grouping; per-session JSON persist under `data/copilot_sessions/`. 160/160 tests in sr env (+15 from session start).
- **2026-05-17 · Memory + archive cleanup sweep** — see commits `32fd451..5a917d4`. Phase 1/2/3 plans + designs + brainstorming + deep-research + stale memory + old `~/.claude/session-data/` .tmp files moved into `Archive/{phase-1,phase-2,phase-3,brainstorming,memory,sessions}/` (move-only, never deleted). Added `CONTEXT.md` (FEA/BRep/copilot domain glossary + avoid-terms + example dialogue) and `SESSION-END.md` (7-step manual end-of-session checklist). Memory dir refreshed: `project_simready.md` rewritten to current Path-C-wk2-day11 state, `project_simready-roadmap.md` collapsed to pointer-only (real plan lives at `docs/exec-plans/path-c-4week.md`), `project_open-questions-wk2.md` moved to `Archive/memory/`. Global `~/.claude/CLAUDE.md` extended w/ BACKLOG/SESSION-END/Archive harness rules, memory-vs-repo duplication rule, /save-session-path gotcha, and two-trigger new-project harness check (session-start + memory-folder creation). `~/.claude/templates/new-project/` seeded w/ BACKLOG.md + SESSION-END.md + Archive/README.md so `new-project-init.sh` scaffolds them. Opened: `adr-backlog` (S3, write 2-3 ADRs for Path C decisions, defer wk-3).
