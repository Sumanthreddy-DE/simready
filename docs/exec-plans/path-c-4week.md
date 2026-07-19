# Path C — 4-Week Execution Plan

**Author:** SimReady team
**Created:** 2026-05-13
**Status:** SUPERSEDED by the wave plan (`BACKLOG.md` "Triage 2026-07-19") — kept as historical wk-1..3 record. **CORRECTION 2026-07-19: application was NEVER sent; `v0.4.0-apply` (`34a93e7`) tagged application *prep* only** (this line previously claimed otherwise — the same false record corrected in BACKLOG/memory on 2026-07-19; this copy was missed until the wave-2 wrap). Wk-1 + wk-2 shipped as described below; wk-3 fine-tune scaffolding landed but the QLoRA run never executed (now Stream D item B, one run then stop). Post-plan work (gen-mvp v1/v2, real-CAD eval, OCC-hang fix, defect-head v2) is tracked in BACKLOG + `docs/session-prompts.md`, not here.
**Target:** MecAgent ML/AI Founding Engineer application + interview-ready demo

## Progress

- [x] **Wk 1 days 1–7** — copilot core, 3 tools, RAG-lite, terminal CLI, degraded-STEP generator. Commits `7212e52..d8fcc1f`.
- [x] **Wk 2 day 8 (partial)** — GrabCAD scrape blocked by anti-bot; pivoted to curated set, tracked in BACKLOG (`grabcad-scrape-blocked`).
- [ ] **Wk 2 day 9** — combined-dataset BRepSAGE retrain (not started; pending GrabCAD curated set).
- [x] **Wk 2 day 10** — Streamlit copilot UI + multi-turn history + Verdict format + real-LLM smoke (`056a746..69539ef`). 4 dropdown duplicates, sidebar score badge, verdict format, multi-turn coverage all closed.
- [x] **Wk 2 day 11** — Static colored-face PNG (option C, PIL painter's algo), ThinSolid detector + drop broken zero-length-edge synth, STEP uploader, typed error chips, dropdown grouping (synth/real), session persist (`636d140..c3df6c0`). 160/160 tests pass.
- [x] **Wk 2 day 12** — Gold traces (50 hand-crafted Q&A). `tests/data/gold_traces.jsonl` committed + pushed.
- [x] **Wk 2 day 13** — Apply prep (lite). Done ~2026-05-18.
- [x] **Wk 2 day 14** — **Applied to MecAgent 2026-05-18**, tagged `v0.4.0-apply` (`34a93e7`). Weeks 3-4 deepen the artifact while in flight.
- [ ] **Wk 2 day 9** — combined-dataset BRepSAGE retrain. Still not started (blocked on 10-STEP curated GrabCAD set). Highest-signal *technical* deepening per contrarian #3 — strong candidate for next focus.
- [x] **Wk 3 days 15–19** — pipeline scaffolding shipped (`4e74ff0`). **Runs (2026-05-24):** trace gen → 1455 traces (45 lost to NIM 429s); 70B gold baseline → n=50, errors=0 (tool_call_exact 0.760, partial 0.920, theme 0.678). Eval gained `--request-delay`/`--max-retries`/`--initial-backoff` for NIM rate-limit survival.
- [~] **Wk 3 days 16–21** — **day-16 prep run done** (951 train / 39 val, 2026-05-24); **day-20 done** (serve-via-vLLM decision + `docs/serve_finetuned.md` + Streamlit Backend selector, not the in-process backend). **Still pending — gated on user Colab run:** day-17 QLoRA train (T4), day-18 base+LoRA eval (runs 2+3 via served endpoint), day-19 fill `finetune_results.md` numbers.

---

## Goal

Evolve SimReady from "Phase 2A: trained BRepSAGE on parametric STEPs" into "AI Copilot for FEA pre-processing" — an LLM-orchestrated tool-use system that ingests a STEP file, answers manufacturability questions, suggests text-only fixes, and renders 3D visualizations.

Application sent at end of week 2. Weeks 3–4 deepen the artifact (fine-tune pipeline, expanded recall) so the repo keeps improving while application is in flight.

---

## North-Star User Journey (wk-2 demo)

1. User opens Streamlit app.
2. Uploads `manifold_complex.STEP` (or picks one of 3 built-in demo STEPs).
3. Asks: "What manufacturing issues does this part have?"
4. LLM (paid API: GPT-4o-mini or Claude Sonnet) invokes `analyze_geometry` tool.
5. Tool returns SimReady pipeline output (findings, scores, complexity tier).
6. LLM follows up with `suggest_fixes` → returns 3 ranked text-only fix suggestions (L1 modification scope; no part regeneration).
7. LLM cites a relevant NAFEMS/ASME paragraph via `lookup_standard` (RAG over scraped FEA PDFs, JSON + cosine).
8. Streamlit renders the part in 3D via stpyvista with finding-locations highlighted.

---

## Architectural Decisions (locked)

| Decision | Choice | Reason |
|----------|--------|--------|
| LLM client | OpenAI-compatible SDK (swappable: GPT-4o-mini, Claude via OpenRouter, local) | User already has paid API key; swappable client = no provider lock |
| UI | Streamlit + stpyvista | User has prior experience → wk-2 ship risk down; Snowflake-backed = real industry adoption for AI/ML internal tools |
| Modification scope | L1 (text-only suggestions) | L2/L3 (codegen + sandboxed exec) deferred to roadmap |
| RAG | JSON + cosine search over scraped FEA PDFs | 5–10 docs → chroma overkill |
| Fine-tune base | Qwen2.5-3B-Instruct, QLoRA 4-bit | Apache 2.0, fits free Colab T4, ~3 hr train |
| Fine-tune narrative | C: capability-demo, not product | Demo uses paid LLM; fine-tune = "I can do the loop" artifact w/ honest gap analysis |
| Order | Copilot wk-1 → recall fix + demo + apply wk-2 → fine-tune wk-3–4 | Application deadline drives demo quality, not fine-tune |
| Eval | Held-out 200 synth traces + 50 hand-written gold traces (user-written) + 5 GrabCAD STEPs side-by-side | Synth-only eval = circular |

---

## Week 1 — Copilot Core (days 1–7)

### Day 1 — scaffolding + smoke test
- `simready/copilot/__init__.py`
- `simready/copilot/tools.py` — three tool resolvers:
  - `analyze_geometry(step_path: str)` → wraps `analyze_file`
  - `suggest_fixes(findings: list[Finding])` → templated text suggestions
  - `lookup_standard(query: str)` → stub returning canned response (RAG plumbed day 3)
- `simready/copilot/agent.py` — OpenAI-compatible client + tool-use loop, single-turn
- `simready/copilot/cli.py` — terminal entry: `python -m simready.copilot.cli <step_path> "<question>"`
- Smoke test: `analyze_geometry("tests/data/grabcad/bracket_simple.STEP")` returns human-readable summary
- `pip install openai python-dotenv` → add to `requirements.txt`
- `.env.example` w/ `OPENAI_API_KEY=` + `OPENAI_BASE_URL=` (for OpenRouter compatibility)

### Day 2 — multi-turn tool loop + system prompt
- System prompt design: define copilot role, tool descriptions, output format
- Multi-turn agent loop: model calls tool → result fed back → model continues
- Error handling: invalid STEP path → fail gracefully; tool exception → reported back to LLM; rate-limit → exponential backoff
- Token budget: truncate large findings reports (>3000 tokens) before feeding back to LLM
- Test: `tests/test_copilot_agent.py` w/ mocked OpenAI client; covers tool-call parsing, error paths

### Day 3 — RAG-lite
- `scripts/scrape_fea_docs.py` — fetch 5–10 public PDFs (NAFEMS quality, ASME PTC 60, open mesh-quality docs); store under `data/fea_docs/` (gitignored)
- `scripts/index_fea_docs.py` — extract paragraphs via pypdf, embed via OpenAI embedding API (or sentence-transformers if cheaper), store as `data/fea_docs_index.json`
- `simready/copilot/rag.py` — cosine search over JSON index; returns top-3 paragraphs w/ source citation
- Wire `lookup_standard` → `rag.search`
- Test: query "mesh quality criteria" returns NAFEMS-tagged paragraph

### Day 4 — agent quality pass
- Few-shot examples in system prompt (3 reference dialogues)
- Tool-output schema tightening: structured JSON not freeform text
- Add `analyze_geometry` to return `complexity_tier` field (already in pipeline)
- Add `suggest_fixes` to return ranked suggestions w/ severity tags
- Manual smoke-test loop on 3 GrabCAD STEPs — record outputs in `docs/copilot_dry_runs.md`

### Day 5 — terminal demo polish
- Pretty terminal output: rich-formatted tool calls, findings, fix suggestions
- Streaming responses for UX (token-by-token display)
- Conversation history persisted to `data/copilot_sessions/<timestamp>.json`
- README section: "Try the copilot — `python -m simready.copilot.cli <step> <question>`"

### Day 6 — recall fix prep (parallel start)
- `scripts/generate_degraded_steps.py` — auto-introduce defects into parametric STEPs:
  - Zero-length edges via near-coincident vertices
  - Open shells via removed faces
  - Sliver faces via tiny offset surfaces
  - Self-intersections via overlapping bodies
- Target: 200 degraded-synthetic STEPs across defect classes
- Reuses `auto_label.py` w/ defect-tagged ground truth

### Day 7 — wk-1 ship gate
- All 77 existing tests still pass
- New tests: `test_copilot_agent.py`, `test_copilot_rag.py`, `test_copilot_tools.py`
- `python -m simready.copilot.cli tests/data/grabcad/manifold_complex.STEP "find issues"` returns sensible output end-to-end
- Commit + push: `feat: Path C wk-1 — LLM copilot core + RAG-lite + degraded-synth scaffolding`

---

## Week 2 — Recall Fix + Demo + Apply (days 8–14)

### Day 8 — GrabCAD scrape + manual label kickoff
- `scripts/scrape_grabcad.py` — fetch 20–30 free-tier STEPs across categories (bracket, gear, lattice, sheet metal, housing, gusset, bearing block)
- Store under `tests/data/grabcad_extended/` (gitignored)
- **User task:** manually label all scraped STEPs with defect tags via `scripts/manual_label_ui.py` (Streamlit form: STEP file → checkbox per defect type → save JSON). ~1 day user work.

### Day 9 — combined dataset retrain
- Merge: 500 parametric + 200 degraded-synth + 20–30 manually-labeled GrabCAD = ~720–730 examples
- Retrain BRepSAGE: `python scripts/train.py --dataset combined --epochs 50`
- Eval: `python scripts/evaluate.py --dataset val_combined` → expect recall lift from 0.23 → target >0.55 on real-CAD held-out
- If recall <0.50 → diagnose: class imbalance? feature mismatch? Iterate one round.

### Day 10 — Streamlit demo build ✅ SHIPPED (`056a746`, `e906bfc`)
- [x] `ui/copilot_app.py` — chat input + history, demo dropdown (deduped), tool-call expanders, sidebar score badge, multi-turn history via `AgentResponse.messages` round-trip.
- [x] `simready/copilot/agent.py` — `run_messages` + `history` kwarg + Verdict format in system prompt.
- [x] Real-LLM smoke against NIM Llama 3.3 70B (10/10 checks, ~11.5k tokens).
- *Deferred:* stpyvista interactive 3D — replaced by Day-11 static PNG (Option C). Reasoning in commit `636d140`.

### Day 11 — Streamlit polish + bug bash ✅ SHIPPED (`636d140`, `749961c`, `46a51de`, `e0708ee`)
- [x] **3d-viz (Option C):** OCC tessellation → PIL painter's-algorithm isometric PNG, embedded in chat bubble + sidebar. Skipped pyvista/matplotlib due to Win DLL conflict w/ pythonocc.
- [x] **weak-synth-defects:** `check_thin_solid` detector (aspect ratio ≥ 100:1) catches sliver class; broken `zero_length_edge` synth removed (STEPControl_Writer round-trip strips the 1e-9 edge).
- [x] **Error states:** sidebar `st.file_uploader`, 5MB warning, `_classify_agent_exception` → typed friendly chat chips (RateLimit / Timeout / ConnError / Auth / BadRequest / generic).
- [x] **Dropdown grouping:** `[synth]` / `[real]` prefixes + per-source count caption.
- [x] **Session persist:** `data/copilot_sessions/<session_id>.json` overwritten each turn; `SIMREADY_SESSION_DIR` env var for tests.
- [x] 160/160 tests pass in sr env (was 145 at session start, +15).
- *Deferred:* background-thread pipeline run (Streamlit session_state is not thread-safe; spinner + 5MB warning is the pragmatic substitute). Mobile-responsive check.

### Day 12 — gold traces (user-written)
- **User task:** write 50 hand-crafted engineering Q&A pairs across categories:
  - "what's wrong with this bracket?"
  - "how to reduce stress concentration?"
  - "is wall thickness adequate for SLS printing?"
  - "explain the topology findings"
  - "what FEA mesh would you recommend?"
- Format: JSONL, one line per (STEP_path, question, expected_tool_calls, expected_answer_themes)
- Stored as `tests/data/gold_traces.jsonl`
- ~4–6 hrs user work

### Day 13 — apply prep (lite, not full README)
- Resume bullet draft (single sentence)
- Verify GitHub profile pin SimReady, repo set to public
- Final smoke test on demo path
- `git log` review — squash any noise commits

### Day 14 — apply
- Send resume to MecAgent (user handles channel)
- Tag commit `v0.4.0-apply` for reference
- Ship gate: clean test suite, working demo, deployed-style README intact (cosmetic polish deferred)

---

## Week 3 — Fine-tune Pipeline (days 15–21)

### Day 15 — synth trace generation ✅ SCRIPT DONE ✅ RUN DONE (2026-05-24)
- [x] `scripts/synth_tool_traces.py` — 50 question templates × 12 STEP files + 8 standards-only = 5000 seed pool. Supports `--dry-run`, `--count N`, `--model`, `--list-steps`, resume on re-run. Monkey-patches render+heal off (skips PNG/ShapeFix OCC overhead for bulk gen).
- [x] **Run done:** NIM endpoint (`https://integrate.api.nvidia.com/v1`), `--count 1500 --model meta/llama-3.1-8b-instruct`. Resumed 1368 → **1455 traces** (45 lost to 429 rate-limits; resume-safe, exit 0). 1455 ample for 3B QLoRA.
- Output: `data/fine_tune/traces.jsonl` (gitignored, resume-safe)
- Lesson: NIM free tier 429-storms on bursty concurrent calls. Pacing/backoff needed (added to eval, day 18).

### Day 16 — dataset prep ✅ SCRIPT DONE (run after day-15 traces land)
- [x] `scripts/prep_finetune_dataset.py` — converts OpenAI tool-call format → Qwen2.5 chatml (`<tool_call>` / `<tool_response>` blocks), 96/4 train/val split, token-estimate stats, `--max-tokens 2048` cap, `--preview` mode.
- [x] **Run done (2026-05-24):** `python scripts/prep_finetune_dataset.py --max-tokens 2048`. 1455 raw → 305 incomplete dropped → 160 over-2048 dropped → **951 train / 39 val**. Capped at 2048 because notebook `MAX_SEQ_LEN=2048` would truncate longer traces and lose their assistant target turn (harmful under `train_on_responses_only`). Fixed a cp1252-console crash in the stats print (Windows can't encode `→`) — script now forces utf-8 stdout.
- Gold traces stay at `tests/data/gold_traces.jsonl` — never mixed into train/val (eval-only)
- Output: `data/fine_tune/train.jsonl` + `data/fine_tune/val.jsonl` (both gitignored)

### Day 17 — Colab fine-tune ✅ NOTEBOOK DONE (run pending train.jsonl on Drive)
- [x] `notebooks/finetune_copilot.ipynb` — 11 sections, 28 cells.
  - GPU check → install unsloth/trl/peft → mount Drive → load dataset
  - Qwen2.5-3B-Instruct 4-bit via unsloth; LoRA r=16, alpha=32, all-linear, dropout 0.05
  - Manual chatml formatter (handles `tool` role that apply_chat_template may skip)
  - `train_on_responses_only` — only assistant turns in loss; system/user/tool masked
  - 3 epochs, batch 2 × grad-accum 8 = effective 16, lr 2e-4 cosine, ~2–3 hrs T4
  - Checkpoint every 200 steps to Drive (resume-safe); loss curve saved as PNG
  - Quick inference sanity cell; optional HF Hub push (set PUSH_TO_HUB=True)
- [ ] **Run:** upload train.jsonl + val.jsonl to `MyDrive/simready/`, open notebook in Colab, Runtime → T4, Run All

### Day 18 — eval base vs LoRA ✅ SCRIPT DONE (run after Day 17 adapter saved)
- [x] `scripts/eval_finetune.py` — scores gold (50) + val (up to 200) traces. Metrics: tool_call_exact/partial, tool_order_ok, format_ok, sections_ok, theme_hit_rate. Appends timestamped block to `docs/finetune_results.md`. Skips missing STEP files (grabcad). Dry-run verified. **+ pacing flags (2026-05-24):** `--request-delay`, `--max-retries`, `--initial-backoff` for rate-limited endpoints.
- [x] **Run 1 done** (reference ceiling, 2026-05-24): `--model-tag "Llama-70B-ref-full" --model meta/llama-3.3-70b-instruct --dataset gold --request-delay 4 --max-retries 6 --initial-backoff 4` → **n=50, errors=0**. tool_call_exact 0.760, partial 0.920, tool_order 0.780, format 0.780, sections 0.780, theme 0.678. (First un-paced attempt 429-stormed to n=15; pacing flags added, stale partial blocks purged.)
- [ ] **Run 2** (base 3B): run in Colab after Day 17 against unquantized Qwen2.5-3B
- [ ] **Run 3** (LoRA 3B): run in Colab Day 20 via local backend after adapter saved
- Note for runs 2–3: use the new pacing flags if going through NIM; format_ok 0.78 on the 70B ceiling means the Verdict-format contract is brittle — worth a prompt/regex look before reading too much into 3B format drift.

### Day 19 — gap analysis writeup ✅ TEMPLATE DONE (fill after Day 18 runs)
- [x] `docs/finetune_results.md` — metric definitions, 3-column comparison table, 8-bucket failure mode taxonomy, lessons-for-next-iteration checklist. Fill in numbers after eval runs complete.

### Day 20 — local inference path ✅ DONE (decision changed: serve, don't embed)
- **Decision (2026-05-24):** dropped the planned in-process `local_backend.py`.
  `CopilotAgent` + `eval_finetune.py` are already 100% `base_url`-driven, so the
  cleaner path is to **serve** the LoRA model behind vLLM's OpenAI endpoint and
  swap `OPENAI_BASE_URL`. vLLM's `--tool-call-parser hermes` converts Qwen2.5's
  `<tool_call>` text (the exact training format) back into structured
  `tool_calls`, so the agent/eval/UI run unchanged. An in-process transformers
  shim would re-implement that parser by hand (~150-200 brittle lines) and be
  CPU-unusable for a live 3B. Rejected.
- [x] `docs/serve_finetuned.md` — vLLM serve command (base + LoRA in one server),
  recommended eval topology (Colab GPU serves via cloudflared tunnel, local box
  runs `eval_finetune.py` with its pythonocc + STEP fixtures), honest-numbers note.
- [x] Streamlit `ui/copilot_app.py` — sidebar **Backend** selector
  (Environment default / Local fine-tuned vLLM / Custom). Rebuilds the agent
  against the chosen `base_url`+`model` with an `EMPTY` placeholder key for local
  endpoints. 12/12 UI tests + 160/160 full suite green.
- VRAM: ~6 GB to serve Qwen2.5-3B (4-bit) + LoRA for inference.

### Day 21 — wk-3 ship gate
- Commit: `feat: Path C wk-3 — QLoRA fine-tune pipeline + eval + local backend`
- Update README with "Fine-tune results" section
- Push

---

## Week 4 — Stretch + Polish (days 22–28)

Prioritized list (do as much as fits, in order):

1. **Real-CAD recall round 2** — if wk-2 recall fix landed <0.55, iterate: more degraded variants, smarter feature engineering, balance loss weights
2. **L2 modification scope** — pythonocc codegen tool (`emit_fix_code`) that returns runnable Python for a fix; user copy-pastes to apply
3. **More gold traces** — expand from 50 → 200 for richer eval
4. **Assembly support end-to-end test** — multi-solid STEP through pipeline + copilot
5. **README hero polish** — screenshots, GIF, arch diagram (NOW, not earlier)
6. **Cover letter + resume project section** (NOW, not earlier)
7. **Interview prep doc** — anticipated questions + answers + code walkthrough script
8. **HTML demo report** — copilot conversation persisted as shareable HTML

Ship gate: anything from list 1–3 minimum.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Recall fix wk-2 fails to lift >0.50 | Medium | High (demo looks bad) | Day-9 iteration loop budgeted; if still <0.40, demo emphasis shifts from "BRepSAGE quality" to "copilot reasoning quality" |
| Streamlit + stpyvista lag on >200-face STEPs | Medium | Medium | Built-in demos curated to <200 faces; upload widget shows warning above limit |
| Colab T4 session timeout mid-fine-tune | Low-Medium | Medium | Checkpoint every 500 steps to Drive; resumable training script |
| Paid API rate limits during synth gen | Low | Low | Exponential backoff in agent loop; spread gen over 2 days |
| Manual labeling drift (user-introduced inconsistency) | Medium | Low | Label schema doc + 5-STEP calibration round before scaling |
| Gold-trace circularity (user writes traces that match training distribution) | Medium | Medium | User writes traces BEFORE seeing fine-tuned outputs; agent task: evaluate blind |
| OpenAI-compatible SDK behavior diverges on non-OpenAI endpoints | Low | Low | Pin to OpenAI SDK, document base-url override pattern |

---

## File Map — what gets created

```
simready/copilot/
  __init__.py
  agent.py              # OpenAI-compatible tool-use loop
  tools.py              # 3 tool resolvers
  rag.py                # JSON + cosine search
  cli.py                # terminal entry
  local_backend.py      # wk-3: local Qwen2.5-3B+LoRA

ui/
  copilot_app.py        # Streamlit chat + 3D viz

scripts/
  scrape_fea_docs.py
  index_fea_docs.py
  scrape_grabcad.py
  manual_label_ui.py
  generate_degraded_steps.py
  synth_tool_traces.py
  eval_finetune.py

notebooks/
  finetune_copilot.ipynb

tests/
  test_copilot_agent.py
  test_copilot_tools.py
  test_copilot_rag.py
  data/
    grabcad_extended/   # gitignored, manually-labeled
    gold_traces.jsonl   # user-written
    fea_docs_index.json # gitignored

docs/
  copilot_dry_runs.md
  finetune_results.md
  exec-plans/
    path-c-4week.md     # this file
```

---

## Exit Criteria — when is Path C "done"

- Streamlit demo runs end-to-end on uploaded STEP without errors
- BRepSAGE real-CAD recall > 0.50 on held-out GrabCAD set
- Fine-tune pipeline reproducible from `notebooks/finetune_copilot.ipynb`
- Eval table comparing base Qwen2.5-3B vs LoRA on 250 traces (200 synth + 50 gold)
- All commits on main, all tests green
- Resume submitted to MecAgent by end of day 14
- Honest gap-analysis writeup in `docs/finetune_results.md`

---

## User-Owned Tasks (cannot delegate)

| Task | Day | Effort |
|------|-----|--------|
| ~~Confirm OpenAI-compatible API key in env~~ ✅ done — NIM key in `.env`, verified 2026-05-24 | Day 1 | 5 min |
| Provide MecAgent application channel decision | Day 14 | own choice |
| Manually label 20–30 scraped GrabCAD STEPs | Day 8–9 | ~1 day |
| Write 50 hand-crafted gold Q&A traces | Day 12 | 4–6 hrs |
| Submit application to MecAgent | Day 14 | own handling |
| Run `git push` after each commit (hook-blocked for assistant) | ongoing | trivial |
