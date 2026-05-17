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
- Last swept: **2026-05-17**.

---

## Open — S1 (blocker / broken demo)

_(none currently)_

---

## Open — S2 (UX gap, polish, deferred decisions)

- [ ] **S2 · weak-synth-defects** — `bracket_with_hole_*__zero_length_edge.step` scores 91/100 (SimulationReady, 1 Minor finding); `__sliver_face.step` scores 58 (NeedsAttention but thin). Pipeline doesn't catch these synth defect types via Compound. Either drop from dropdown, label "(weak demo)", or fix detectors. *Opened 2026-05-17.*
- [ ] **S2 · readme-polish** (Decision B) — Apply-time README scope. Plan says defer to wk-4 but recruiter clicking GitHub during wk-2 apply will see Phase-3-era README. Options: (1) trust new "Copilot (Path C)" section, (2) add hero block at top before apply, (3) defer everything to interview. Lean (2). *Opened 2026-05-14.*
- [ ] **S2 · apply-timeline-tight** — Wk-2 day-14 apply ship is feasible only if everything goes right. Cut scope or extend deadline 3–5 days. Re-decide end of wk-2 day 12. *Opened 2026-05-14 (wk-1 Q4).*
- [ ] **S2 · grabcad-scrape-blocked** — `download_grabcad_samples.py` is a manual stub; site has anti-bot + login walls. Pivot to curated 10-STEP manual-download set instead of scraping 20–30. *Opened 2026-05-14 (wk-1 Q2).*
- [ ] **S2 · fea-rag-corpus-empty** — `data/fea_docs/` is empty → `lookup_standard` returns `no_index` → demo loses one of three tools' value. Public alternatives: vendor whitepapers, MIT OCW, NIST handbook. Scout 5–10 stable URLs, present for user vet, then `pip install sentence-transformers pypdf` + run scrape/index scripts. *Opened 2026-05-14 (wk-1 Q3).*

---

## Open — S3 (tech debt, deprecations, low-impact polish)

- [ ] **S3 · session-persist-ui** — Copilot CLI saves to `data/copilot_sessions/` per turn, Streamlit UI does not. Lost transcripts on browser refresh. *Opened 2026-05-17.*
- [ ] **S3 · dropdown-grouping** — 22 dropdown items mix `data/parametric_degraded/` (synth) and `tests/data/grabcad/` (real). Group by source so user knows which is which. *Opened 2026-05-17.*
- [ ] **S3 · brepbndlib-deprecation** — `scripts/generate_degraded_steps.py:95` uses deprecated `brepbndlib_Add` (pythonocc 7.7+ wants `brepbndlib.Add` static method). Spams 4 warnings per test run. *Opened 2026-05-17.*
- [ ] **S3 · trace-format-rot** — Wk-3 day-15 plan generates ~5000 synth tool traces for fine-tune. Schema will differ from current per-CLI-run JSON in `data/copilot_sessions/`. Write traces to `data/fine_tune/traces.jsonl` separately when that lands. *Opened 2026-05-14 (wk-1 Q7).*
- [ ] **S3 · base-vs-env-marker-split** — Two-Python-env reality (base 3.12 vs `C:\mm\sr` 3.10) keeps confusing tests. Add `pytest -m base` vs `pytest -m occ` marker split + a Makefile/PS shortcut. Less acute now that env is verified working, but the gotcha remains. *Opened 2026-05-14 (wk-1 Q5).*

---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session (2026-05-17)

- [x] **S2 · 3d-viz** (`636d140`) — Option C shipped: static colored-face PNG via OCC tessellation + PIL painter's-algorithm in fixed isometric projection. Rendered per `analyze_geometry`, embedded in chat bubble + sidebar via `image_path`. Skipped pyvista/stpyvista to avoid Win DLL flake; matplotlib also crashes inside the sr env's OCC DLL space on Win, so PIL is the safer pick. 7 new tests in `tests/test_copilot_render.py`, 152/152 total in sr env.
- [x] **S2 · multi-turn-coverage** (`e906bfc`) — `scripts/smoke_real_llm.py` extended with T2 follow-up using `resp1.messages` as history. T2 answered in 1 iter, 0 tool calls, cited SelfIntersection from T1. 10/10 smoke checks OK against NIM Llama 3.3 70B. ~11.5k tokens total.
- [x] **S1 · dropdown-duplicates** (`056a746`) — Windows globs case-insensitive; `*.step` + `*.STEP` matched same files (44 entries, 22 unique). Deduped via `set(p.resolve())` in `ui/copilot_app.py:_list_demo_steps`. *Test: `tests/test_copilot_ui.py::test_list_demo_steps_is_deduped`.*
- [x] **S2 · verdict-format-missing-score** (`056a746`) — `DEFAULT_SYSTEM_PROMPT` updated to require `Verdict: <status> · score X/100 · <complexity> (<faces> faces, <bodies> bodies)` and blank lines between Verdict / Issues / Fixes / Citations sections. Example dialogues match new format.
- [x] **S2 · multi-turn-history** (`056a746`) — `CopilotAgent.run` now accepts `history` kwarg; new `run_messages` method; `AgentResponse.messages` exposes full message list. UI persists in `st.session_state._llm_history` and passes back on each turn. Backward-compatible.
- [x] **S2 · score-sidebar** (`056a746`) — Sidebar "Last analysis" badge shows status color, score/100, faces/edges/findings metrics, severity bar, complexity. Captured via `on_event` filter for `analyze_geometry` tool results.
- [x] **Day-10 step 1** (`d8fcc1f`) — `data/parametric_degraded/` populated, 20 STEPs (5 inputs × 4 defects) + manifest via `scripts/generate_degraded_steps.py`.
- [x] **Day-10 step 2–3** (`056a746`) — `ui/copilot_app.py` Streamlit chat shipped + 7 AppTest smoke tests in `tests/test_copilot_ui.py`.
- [x] **Day-10 step 4** (`563ab6c`) — Real-LLM smoke ran clean in env against NIM Llama 3.3 70B via `scripts/smoke_real_llm.py`. 4 iters, 8321 tokens, all 5 smoke checks OK.
- [x] **env-rediscovered** — Conda env was already at `C:\mm\sr` from 2026-04-23 (memory said missing). Verified full stack: py 3.10.20, OCC 7.9.0, torch 2.12.0+cpu, pyg 2.7.0, openai 2.36.0, streamlit 1.56.0. 145/145 tests pass.

---

## Archived (older sweeps, compressed)

- **2026-05-13 · Phase 2A bug-fix sweep** (5 items) — see commits `b689b71`..`ec4f33a`. SelfIntersection false-positive, face index 0/1 mismatch, ML weights-loaded lying, GrabCAD manifold hang guard, rule_face_count rename.
- **2026-05-14 · Path C wk-1 ship** (6 days of work) — see commits `7212e52`..`d8fcc1f`. Copilot stack, 3 tools, RAG-lite, multi-turn loop, terminal UI, degraded-STEP generator.
- **2026-05-16 · Wk-1 Q1/Q6/Q8 resolved** — light real-LLM smoke (`563ab6c`) validated LLM loop end-to-end on NIM Llama. No tool_choice gotcha. Slim summary respected. Day-10 sub-decisions D1=b, D2=a, D3=mock-then-smoke locked.
