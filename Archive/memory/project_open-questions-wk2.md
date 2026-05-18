---
name: Open questions raised at end of wk-1, awaiting user answer
description: DEPRECATED 2026-05-17 — open items migrated to BACKLOG.md at repo root. Kept here only as historical record of wk-1/wk-2 transitions. Do not add new items here.
type: project
originSessionId: e6c4775f-7723-4105-956e-d4996f6e145b
---
**DEPRECATED 2026-05-17** — open items migrated to `BACKLOG.md` at SimReady repo root.
Still-open items live there with severity tags (S1/S2/S3). Resolved items are listed below for history only. **Do not add new questions here — use `BACKLOG.md`.**

Surfaced 2026-05-14 at end of wk-1 ship session. User explicitly deferred answers — said to bring up next session to avoid bloating that session's context. Order is by stakes (highest first).

## How to apply
At start of any wk-2 session, when user asks "what's next" / "any questions" / "what should I decide" → surface this list (or top 3-4 by stakes). Do NOT auto-act on any of these; user must answer first. After user answers, update this file (mark resolved with date + decision) or split items into the roadmap.

## 1. Wk-1 has zero ground-truth that the agent loop talks to a real LLM correctly. [highest risk]
All 56 tests mock the OpenAI client. Day-4 manual smoke was deferred. Day-5 CLI rich panels were never seen running on a real model response. Wk-2 stacks Streamlit chat UI + real-CAD recall fix + apply on top of an unverified base.
**Recommendation:** before wk-2 day 8, run the deferred day-4 manual smoke (cost = a few cents). Catches: tool-call argument shape mismatches, prompt confusion, severity_counts not populated, lookup_standard returning no_index visibly, Verdict format ignored.

**RESOLVED 2026-05-16:** Light smoke ran via `scripts/smoke_real_llm.py` against NIM Llama 3.3 70B with canned `analyze_file` stub. 4 iterations, stop_reason=stop, 3-tool chain clean (analyze_geometry → suggest_fixes → lookup_standard), Verdict/Issues/Fixes format respected, no_index gracefully surfaced. 8323 tokens. Full OCC smoke still pending (needs conda env — never installed).

## 2. GrabCAD scraping at scale is probably blocked.
Site has anti-bot + login walls. Existing `download_grabcad_samples.py` is a manual stub. Wk-2 day 8 plan assumes 20-30 STEPs scraped programmatically.
**Suggest:** pivot to curated 10-STEP manual-download set (user picks from GrabCAD search results), keep labeling target small. Or accept that "scrape" = "user downloads, script just verifies."

## 3. FEA PDF corpus is empty and harder to fill than the plan implies.
NAFEMS publications often need membership. ASME PTC standards aren't free. `data/fea_docs/sources.txt` exists as template but no URLs. Without corpus, `lookup_standard` returns `no_index` → demo loses one of three tools' value.
**Public alternatives:** vendor whitepapers (Ansys / Abaqus / MSC tutorial PDFs), MIT / Stanford OpenCourseWare FEA notes, NIST handbook chapters, public engineering textbook excerpts.
**Offer:** at start of wk-2, scout 5-10 stable URLs and present for user to vet.

## 4. Application end of wk-2 day 14 looks tight.
Real-CAD recall fix (day 9) needs labeled data (day 8 user task, ~1 day) and may need iteration if first retrain misses target. Streamlit UI build + bug bash (day 10-11) is 2 days for a polished chat + 3D viz that hasn't been prototyped. Day 12 is 4-6 hour user task. Day 13-14 apply prep.
**Honest read:** day 14 ship is feasible but assumes everything goes right. Slip likely.
**Choose:** protect deadline by cutting scope (e.g., ship 2D findings table only, skip stpyvista 3D viz) OR extend deadline by 3-5 days.

## 5. Two-env split keeps biting.
Base Python lacks OCC + torch_geometric → 33 pre-existing test failures. Conda env has them. Documented in `lessons_python-tooling.md` item 8 but no automation.
**Suggest:** add `pytest -m base` vs `pytest -m occ` marker split + `make test-base` / `make test-conda` (or PowerShell equivalent) so we stop tripping on the same baseline check every session.

## 6. `tool_choice` strategy in the new few-shot prompt is implicit.
Day-4 prompt added 3 reference dialogues but the agent loop still uses `tool_choice="auto"`. Llama tool_choice gotcha (lessons_llm-tool-orchestration.md item 5) means we can't force a final text turn. If a model gets stuck in a tool-call loop, we hit `max_iterations=6` silently and return empty `final_text`.
**Risk for wk-2 demo:** real LLM might over-call lookup_standard or chain unnecessary suggest_fixes.
**Mitigation candidate:** detect a redundant tool_call (same name + same args as previous turn) and force-terminate with prior tool_results as final answer. Worth doing before wk-2 day 10 UI build.

**RESOLVED 2026-05-16 (initial smoke):** NIM Llama 3.3 70B did NOT hit the gotcha. 3-tool chain in 4 iterations, stop_reason=stop. Watch for it once UI is wired and real (varied) user queries arrive — re-evaluate before wk-3.

## 7. Session-save format will rot once we generate fine-tune traces.
Day 5 stores per-CLI-run JSON at `data/copilot_sessions/<ISO>_<part>.json`. Wk-3 day 15 generates 5000 synth tool traces — different schema (full message history for ShareGPT/chatml format).
**Suggest:** when wk-3 trace generator lands, write to `data/fine_tune/traces.jsonl` separately, NOT to `data/copilot_sessions/`. Don't conflate the two folders.

## 8. "Slim summary" for `analyze_geometry` may surprise the LLM mid-conversation.
Few-shot Example 1 shows the model reciting "148 faces, 1 body" exactly. Slim summary returns `geometry.face_count` + `body_count` which support that. But if LLM cites `score.overall` as "72.5/100" and actual return key is `score.overall=72.5` (no /100 suffix), the model may invent the suffix.
**Cheap test:** during day-4 smoke, check whether the model invents number formats not present in tool output. If yes, tighten prompt to "report numbers verbatim, no derived units."

**RESOLVED 2026-05-16:** Llama 3.3 70B cited "142 faces, 1 body" verbatim, reused status string "ReviewRecommended" instead of inventing "/100" suffix. Slim summary is sufficient grounding for this model. Re-test if model is swapped (GPT-4o-mini, Claude).

## Decision A: Wk-2 entry order

Plan says day-8 → day-9 → day-10. I'd reorder to **(deferred day-4 smoke) → day 10 UI prototype on synthetic STEP only → day 8/9 (data + retrain in parallel)**. Reason: validates the LLM loop end-to-end first, lets user see the UI before committing 1 day of labeling work that depends on demo direction being right.
**Awaiting:** user picks order.

---

# Carried into session 2026-05-17+ (added end of 2026-05-16)

## How session 2026-05-16 ended
- Decision A confirmed by user: order is **day 10 → day 8 → day 9 → deferred day-4 smoke last**.
- Light real-LLM smoke ran (commit `563ab6c`, `scripts/smoke_real_llm.py`). Q1/Q6/Q8 resolved at light-smoke level. NIM Llama 3.3 70B + canned OCC payload, 4 iters, clean stop, 3-tool chain, Verdict format respected.
- `pip install openai` ran in base Python 3.12 (see lessons_python-tooling.md item 10).
- No conda/micromamba install on machine — `environment.yml` exists but env never created (lessons_python-tooling.md item 8 correction).
- Local commit only (`563ab6c`). User to push.

## Pending pick — Day-10 UI build path [BLOCKER for next session start]
- **(a) Build UI now, defer OCC env install.** UI talks real LLM + canned/stub pipeline. Fast iteration. Cannot test on real STEPs until env exists → demo screenshots blocked.
- **(b) Install micromamba + create `simready` env first** (~5–10 min download). UI ships against full real pipeline immediately. Demo-ready.
- I lean **(b)** — env needed eventually for day-8/9 retrain regardless.

**RESOLVED 2026-05-17:** User picked **(b)**. Env was already installed at `C:\mm\sr` from 2026-04-23 (memory was wrong — see lessons_python-tooling item 8 re-correction). Verified full stack works: 138/138 tests pass in env. Optional installs deferred: sentence_transformers + pypdf (only when FEA corpus built), pyvista + stpyvista (only if D2 ≠ a).

## Pending sub-decisions for day 10 (raised but not confirmed)
- **D1 demo STEP source.** Options: (a) clean parametric `data/parametric/bracket_with_hole_*.step` — boring; (b) generate degraded synth via `scripts/generate_degraded_steps.py` — needs OCC; (c) existing `tests/data/grabcad/manifold_complex.STEP` — real defects, works today. I leaned (b). With path-pick (a) above, fallback to (c) until env lands.
- **D2 day-10 3D viz scope.** (a) skip viz, ship chat + tool-expanders + citations only → fastest; (b) min stpyvista wireframe; (c) full per-face heatmap (plan target, ~1 day). I leaned (a) for day 10, defer viz polish to day 11.
- **D3 dev LLM strategy.** Mock-for-scaffolding + one real-LLM smoke per session. I leaned mock-then-smoke.

**RESOLVED 2026-05-17:** D1=(b) degraded synth, D2=(a) chat+expanders+citations only (no viz), D3=mock-then-smoke. Day-10 concrete plan: (1) run `scripts/generate_degraded_steps.py` against a clean source STEP, store fixtures; (2) build `ui/copilot_app.py` Streamlit page — file upload, chat history, per-turn tool-expander panels, citation footer; (3) test with mocked openai client; (4) one real-LLM smoke at end via env's openai SDK against NIM.

## Decision B: Apply-time README scope

Plan says "resume only" at apply time, README polish deferred to wk-4. MecAgent recruiter clicking GitHub will see SimReady README in current state. Current README is Phase 3 era with the new "Copilot (Path C)" section we added but no demo screenshot, no hero block.
**Three options:**
1. Trust recruiters to read the new "Copilot (Path C)" section we just added.
2. Add a single hero block at top of README before apply.
3. Keep README as-is and defer everything to interview.
I lean (2). User said no polish before wk-4 — this contrarian to the locked decision in `project_path-c-decisions.md`.
**Awaiting:** user confirms (1/2/3) or holds to wk-4 deferral.
