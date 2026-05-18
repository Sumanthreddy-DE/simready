# SimReady Backlog

Living list of open issues, deferred work, and known caveats. Updated each session.

**Severity rubric**
- **S1** — blocker / data loss / broken demo. Fix before next ship.
- **S2** — UX gap, missing polish recruiters will notice, deferred decision.
- **S3** — tech debt, deprecations, low-impact polish, dead code.

**Conventions**
- New issue → append to correct severity section.
- Mention by short slug in commit body (e.g. "Closes: multi-turn-history").
- On close → move to **Done this session** with commit SHA.
- End of session → user sweeps **Done** → **Archived** (one-line compress).
- Last swept: **2026-05-17** (memory + archive cleanup sweep — done-phase docs moved to `Archive/`, CONTEXT.md + SESSION-END.md added, adr-backlog opened).

---

## Open — S1 (blocker / broken demo)

_(none currently)_

---

## Open — S2 (UX gap, polish, deferred decisions)

- [ ] **S2 · readme-polish** (Decision B) — Apply-time README scope. Plan says defer to wk-4 but recruiter clicking GitHub during wk-2 apply will see Phase-3-era README. Options: (1) trust new "Copilot (Path C)" section, (2) add hero block at top before apply, (3) defer everything to interview. Lean (2). *Opened 2026-05-14.*
- [ ] **S2 · apply-timeline-tight** — Wk-2 day-14 apply ship is feasible only if everything goes right. Cut scope or extend deadline 3–5 days. Re-decide end of wk-2 day 12. *Opened 2026-05-14 (wk-1 Q4).*
- [ ] **S2 · grabcad-scrape-blocked** — `download_grabcad_samples.py` is a manual stub; site has anti-bot + login walls. Pivot to curated 10-STEP manual-download set instead of scraping 20–30. *Opened 2026-05-14 (wk-1 Q2).*
- [ ] **S2 · fea-rag-corpus-empty** — `data/fea_docs/` is empty → `lookup_standard` returns `no_index` → demo loses one of three tools' value. Public alternatives: vendor whitepapers, MIT OCW, NIST handbook. Scout 5–10 stable URLs, present for user vet, then `pip install sentence-transformers pypdf` + run scrape/index scripts. *Opened 2026-05-14 (wk-1 Q3).*

---

## Open — S3 (tech debt, deprecations, low-impact polish)

- [ ] **S3 · brepbndlib-deprecation** — `scripts/generate_degraded_steps.py:95` uses deprecated `brepbndlib_Add` (pythonocc 7.7+ wants `brepbndlib.Add` static method). Spams 4 warnings per test run. *Opened 2026-05-17.*
- [ ] **S3 · trace-format-rot** — Wk-3 day-15 plan generates ~5000 synth tool traces for fine-tune. Schema will differ from current per-CLI-run JSON in `data/copilot_sessions/`. Write traces to `data/fine_tune/traces.jsonl` separately when that lands. *Opened 2026-05-14 (wk-1 Q7).*
- [ ] **S3 · base-vs-env-marker-split** — Two-Python-env reality (base 3.12 vs `C:\mm\sr` 3.10) keeps confusing tests. Add `pytest -m base` vs `pytest -m occ` marker split + a Makefile/PS shortcut. Less acute now that env is verified working, but the gotcha remains. *Opened 2026-05-14 (wk-1 Q5).*
- [ ] **S3 · adr-backlog** — Write 2–3 ADRs under `docs/adr/` for Path C decisions that will be hard to reconstruct in 6 months: (1) OpenAI-compatible SDK over Anthropic-native (why `base_url` swap matters), (2) RAG-lite JSON + cosine over a vector DB (corpus size assumption), (3) multi-turn loop pattern w/ `AgentResponse.messages` round-trip. Defer until wk-3 — non-blocking; useful for the interview narrative, not for shipping. *Opened 2026-05-17.*

---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session (2026-05-17)

_(none — swept to Archived at end of session.)_

---

## Archived (older sweeps, compressed)

- **2026-05-13 · Phase 2A bug-fix sweep** (5 items) — see commits `b689b71`..`ec4f33a`. SelfIntersection false-positive, face index 0/1 mismatch, ML weights-loaded lying, GrabCAD manifold hang guard, rule_face_count rename.
- **2026-05-14 · Path C wk-1 ship** (6 days of work) — see commits `7212e52`..`d8fcc1f`. Copilot stack, 3 tools, RAG-lite, multi-turn loop, terminal UI, degraded-STEP generator.
- **2026-05-16 · Wk-1 Q1/Q6/Q8 resolved** — light real-LLM smoke (`563ab6c`) validated LLM loop end-to-end on NIM Llama. No tool_choice gotcha. Slim summary respected. Day-10 sub-decisions D1=b, D2=a, D3=mock-then-smoke locked.
- **2026-05-17 · Path C wk-2 day 10 ship** (4 items) — `056a746`..`69539ef`. Streamlit chat UI + dropdown dedupe, sidebar score badge, multi-turn history via `AgentResponse.messages` round-trip, Verdict-with-score format. Real-LLM smoke gained a turn-2 follow-up (10/10 NIM checks).
- **2026-05-17 · Path C wk-2 day 11 ship** (7 items) — `636d140`..`c3df6c0`. Static colored-face PNG via OCC tess + PIL painter's-algo (replaces deferred pyvista; matplotlib also broken in sr OCC env on Win); `check_thin_solid` detector + drop broken `zero_length_edge` synth; STEP file uploader + 5MB warn; typed `_classify_agent_exception` chips (RateLimit/Timeout/ConnError/Auth/BadRequest); `[synth]`/`[real]` dropdown grouping; per-session JSON persist under `data/copilot_sessions/`. 160/160 tests in sr env (+15 from session start).
- **2026-05-17 · Memory + archive cleanup sweep** — see commits `32fd451..5a917d4`. Phase 1/2/3 plans + designs + brainstorming + deep-research + stale memory + old `~/.claude/session-data/` .tmp files moved into `Archive/{phase-1,phase-2,phase-3,brainstorming,memory,sessions}/` (move-only, never deleted). Added `CONTEXT.md` (FEA/BRep/copilot domain glossary + avoid-terms + example dialogue) and `SESSION-END.md` (7-step manual end-of-session checklist). Memory dir refreshed: `project_simready.md` rewritten to current Path-C-wk2-day11 state, `project_simready-roadmap.md` collapsed to pointer-only (real plan lives at `docs/exec-plans/path-c-4week.md`), `project_open-questions-wk2.md` moved to `Archive/memory/`. Global `~/.claude/CLAUDE.md` extended w/ BACKLOG/SESSION-END/Archive harness rules, memory-vs-repo duplication rule, /save-session-path gotcha, and two-trigger new-project harness check (session-start + memory-folder creation). `~/.claude/templates/new-project/` seeded w/ BACKLOG.md + SESSION-END.md + Archive/README.md so `new-project-init.sh` scaffolds them. Opened: `adr-backlog` (S3, write 2-3 ADRs for Path C decisions, defer wk-3).
