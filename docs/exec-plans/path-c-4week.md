# Path C — 4-Week Execution Plan

**Author:** SimReady team
**Created:** 2026-05-13
**Status:** Active — wk-1 shipped (`7212e52..d8fcc1f`), wk-2 day 10 + 11 shipped (`056a746..c3df6c0`), wk-2 day 12 (gold traces) next
**Target:** MecAgent ML/AI Founding Engineer application + interview-ready demo

## Progress

- [x] **Wk 1 days 1–7** — copilot core, 3 tools, RAG-lite, terminal CLI, degraded-STEP generator. Commits `7212e52..d8fcc1f`.
- [x] **Wk 2 day 8 (partial)** — GrabCAD scrape blocked by anti-bot; pivoted to curated set, tracked in BACKLOG (`grabcad-scrape-blocked`).
- [ ] **Wk 2 day 9** — combined-dataset BRepSAGE retrain (not started; pending GrabCAD curated set).
- [x] **Wk 2 day 10** — Streamlit copilot UI + multi-turn history + Verdict format + real-LLM smoke (`056a746..69539ef`). 4 dropdown duplicates, sidebar score badge, verdict format, multi-turn coverage all closed.
- [x] **Wk 2 day 11** — Static colored-face PNG (option C, PIL painter's algo), ThinSolid detector + drop broken zero-length-edge synth, STEP uploader, typed error chips, dropdown grouping (synth/real), session persist (`636d140..c3df6c0`). 160/160 tests pass.
- [ ] **Wk 2 day 12** — Gold traces (50 hand-crafted Q&A, ~4–6h user work). User task.
- [ ] **Wk 2 day 13** — Apply prep (lite).
- [ ] **Wk 2 day 14** — Apply.

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

### Day 15 — synth trace generation
- `scripts/synth_tool_traces.py` — paid LLM (GPT-4o-mini) generates tool-call traces:
  - Seed with random STEP + random question category
  - Capture: messages, tool calls, tool results, final answer
  - 5000 traces target
- Output: `data/fine_tune/traces.jsonl`
- Cost estimate: $5–15 for 5000 traces at 4o-mini pricing

### Day 16 — dataset prep
- Format traces for ShareGPT / Alpaca / chatml schema (Qwen2.5 prefers chatml)
- Train/val split: 4800/200
- Hold out 50 gold traces (from day 12) as separate test set — never seen during train
- Sanity check: load one trace into tokenizer, verify length distribution (<2048 tokens preferred)

### Day 17 — Colab fine-tune
- `notebooks/finetune_copilot.ipynb`:
  - Install: unsloth (fastest QLoRA on T4), trl, peft, transformers
  - Load Qwen2.5-3B-Instruct in 4-bit
  - LoRA config: r=16, alpha=32, target_modules=all-linear
  - Train: 3 epochs, batch 2 + grad-accum 8, lr 2e-4, ~2–3 hrs
  - Push LoRA adapter to HuggingFace Hub (private repo) or save to Google Drive

### Day 18 — eval base vs LoRA
- `scripts/eval_finetune.py`:
  - Run 200 held-out synth traces through base Qwen2.5-3B and LoRA model
  - Run 50 gold traces through both
  - Metrics: tool-call accuracy (correct tool name + arg shape), final-answer alignment (judged by GPT-4 as eval LLM, or manual rubric)
- Output: `docs/finetune_results.md` with side-by-side table

### Day 19 — gap analysis writeup
- Honest documentation: where 3B+LoRA matches paid model, where it fails, why
- Failure mode taxonomy: 5–10 categories with example traces
- Lessons for next iteration: more data? bigger base? different tool schema?

### Day 20 — local inference path
- `simready/copilot/local_backend.py` — load Qwen2.5-3B+LoRA via vLLM or transformers
- Swap into agent loop via config flag: `--backend openai|local`
- Streamlit settings panel: toggle backend
- Document VRAM requirement (~5GB inference)

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
| Confirm OpenAI-compatible API key in env | Day 1 | 5 min |
| Provide MecAgent application channel decision | Day 14 | own choice |
| Manually label 20–30 scraped GrabCAD STEPs | Day 8–9 | ~1 day |
| Write 50 hand-crafted gold Q&A traces | Day 12 | 4–6 hrs |
| Submit application to MecAgent | Day 14 | own handling |
| Run `git push` after each commit (hook-blocked for assistant) | ongoing | trivial |
