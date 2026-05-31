# SimReady — Session Prompts

Kickoff prompts for upcoming work streams. Pick one when starting the next
session; paste it as the first message. Each prompt is self-contained — it
names every file the agent needs to read and every command it needs to run.

**Convention.** Add a new section per stream. Inside the section: a fenced
code block with the full prompt, plus a one-paragraph framing above it so a
human reader knows why it exists. When a stream is consumed (or rolls into
a new state), update the section's status line.

---

## Stream A — Geometry-gen v2: live-LLM E_grammar runner

- **Status:** Ready to paste (drafted 2026-05-31, after `fa581f0`).
- **Predecessor work:** session of 2026-05-31 shipped geometry-gen-mvp v1 (typed DSL + `build_part` tool + 31 tests, suite 198/198 sr green; commit `fa581f0`).
- **Why next:** the strategy doc's rank 5 (JD bullet #1, *geometry generation*) is the one true JD gap. v1 proved the build path; v2 proves the whole loop with a real model in it, which is what an interviewer cares about.
- **Out of scope:** v3 (`scripts/simready_gen.py` CLI + Streamlit gen panel) — kept as a fallback in the prompt.

```
Work on SimReady. Continuing geometry-gen-mvp from session of 2026-05-31
(commit fa581f0). v1 — typed DSL + build_part tool + 31 tests, full suite
198/198 sr green — is SHIPPED. v2 is the next deliverable: a live-LLM
E_grammar runner that proves the generate → analyze loop end-to-end on
5 hand-written prompts.

First read (in this order):
1. BACKLOG.md — S1 geometry-gen-mvp stamp (v1 SHIPPED, v2/v3 still Open) +
   open S2/S3 (don't touch unless v2 blocks)
2. docs/exec-plans/geometry-gen-mvp.md — full plan; v2 scope = the
   "## Test plan" → tests/test_gen_e2e.py block, and the
   "## Ship sequence" → Commit 2 row
3. docs/adr/0001-geometry-gen-dsl-over-codegen.md — exec-model decision
   (LLM emits a Pydantic PartSpec via the build_part tool call; no LLM
   code is ever exec'd; this is *not* negotiable for v2)
4. memory project_simready.md CURRENT STATE 2026-05-31 block
5. simready/copilot/agent.py — the multi-turn loop you'll reuse; pay
   attention to AgentResponse.messages round-trip + max_turns; openai-
   compat client w/ base_url swap (NIM / OpenRouter / local vLLM)
6. simready/copilot/tools.py — build_part schema + dispatch wiring
   (already shipped; do NOT re-write — just call dispatch_tool)
7. docs/validation/real_eval.md §1 — defect head is 100% FP on real CAD;
   v2 must NOT gate on it (advisory only)

v2 ship gate (E_grammar, locked):
- tests/data/gen_prompts.jsonl carries 5 hand-written prompts, one per
  generate_parametric_steps.py archetype (normal_box, thin_plate,
  l_bracket, bracket_with_hole, small_feature_box). Each has expect.faces
  range. CORRECTED ranges per tests/test_gen_build.py: single-box = [6,6],
  L-bracket fuse = [10,18], box-minus-through-cyl = [6,10]. The
  "[10,14]" shown in the original E_grammar preview was wrong.
- tests/test_gen_e2e.py runs simready/copilot/agent.py against each prompt
  with [build_part, analyze_geometry] as the tool set. Pass = final STEP
  exists + OCC valid + face count in expect range. pytest.mark.live_llm
  so default sr run skips. Test reads OPENAI_BASE_URL + OPENAI_API_KEY +
  OPENAI_MODEL from env.
- Writes docs/validation/geometry_gen_eval.md w/ per-prompt row (turns,
  final spec JSON, occ_valid, faces, score) and a 3-paragraph
  interpretation (same style as docs/validation/real_eval.md).

Implementation notes:
- Don't replace the agent system prompt; ADD a short instruction block
  when the test runner constructs the agent: "When the user asks you to
  CREATE a part, call build_part first; after it returns, call
  analyze_geometry on the step_path. Only describe the result after both
  calls succeed."
- max_turns = 6 is enough; the v2 prompts are deliberately specific so
  one build_part call should suffice. Refine semantics are a v2.1
  follow-up (deliberately not in v2).
- Subprocess overhead per build_part = ~5–10 s on Windows spawn.
  5 prompts × (~10 s build + ~3 s analyze + agent overhead) ≈ 90 s
  wall-clock. Acceptable. If a single prompt exceeds 60 s wall, that's
  a regression — flag in the eval doc.

Env (sr env, PowerShell tool — NOT Bash):
  $env:PYTHONPATH    = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady"
  $env:OPENAI_BASE_URL = "https://integrate.api.nvidia.com/v1"
  $env:OPENAI_MODEL    = "meta/llama-3.3-70b-instruct"
  # OPENAI_API_KEY from .env — never Read .env; use a redacted one-liner to verify
  & C:\mm\sr\python.exe -m pytest tests/test_gen_e2e.py -m live_llm -v

Wrap-up:
- BACKLOG sweep (move v2 to Done; S1 stamp now reads "v1 + v2 SHIPPED, v3
  CLI remaining")
- memory project_simready.md 1-line update with the 5/5 (or n/5) pass
  count and any honest failure modes
- commit; HAND THE PUSH TO USER ("! git -C ... push origin main" — hook
  blocks the agent)

Fallbacks if v2 hits unexpected blockers:
- v3 CLI first (scripts/simready_gen.py) — smaller scope, decouples
  build_part from agent-loop message shape concerns
- BACKLOG: S3 adr-backlog (write 2–3 ADRs for Path C decisions — agent-
  doable, low-stakes interview narrative bonus; do this if you have <30
  min budget remaining)

Caveman mode ON (chat terse; code/commits normal).
```

---

<!-- Append new streams below this line. -->

## Stream B — Sibling-session mid-turn pickup (CONSUMED)

- **Status:** CONSUMED 2026-05-31 — produced commits `849449a` (real-CAD OOD eval + `eval_real_cad.py` hang-proofing) and `fa581f0` (geometry-gen-mvp v1). All "still open" items in the prompt below are now done.
- **Why kept on file:** historical record of the kickoff message that drove this session's heaviest work. Useful when a future session wants to see how a mid-turn pickup was framed (sibling-context summary + non-overlap audit + scoping question handoff). DO NOT re-execute — the work is shipped.
- **Predecessor:** sibling session of 2026-05-28 (commits `90b90cb` + `0b76c61`, three S2/S3 quick-win closes).
- **Successor:** Stream A above (geometry-gen v2 live-LLM E_grammar runner).

```
Work on SimReady. Sibling session shipped 2 commits today (2026-05-28) and paused.
DO NOT redo this work — read the artifacts and continue from where the brainstorm stopped.

What the sibling session did:

1. Verified push state at start — 3 commits unpushed (58dd47f, a29e150, a719db0). User to push.
2. Commit 90b90cb — closed 3 backlog items:
   - env-example-secret-leak (S2): replaced live nvapi- key in .env.example:6 with
     <your-api-key> placeholder (regex rewrite, secret never echoed by the agent).
     NOTE: key still in git history — user must rotate on the NVIDIA dashboard
     separately; this commit does NOT rewrite history.
   - evaluate-py-defect-metric (S2): scripts/evaluate.py now passes batch=batch.batch
     and reports defect_accuracy + per_class_acc when the dataset has graph_label
     (guarded for older label-less sets). Smoke on data/labels_combined (1100-set):
     defect_acc=0.739 (clean 0.84 / open_shell 0.565 / sliver 1.0 / self_int 0.40).
   - grabcad-doc-stale (S3): refreshed docs/validation/grabcad.md to the 3-head
     leakage-free checkpoint (a29e150). Banner + Overall 37.5/36.6/61.0 + ML agg
     0.37-0.45 + latency now sourced from weights/metrics.json. Rule/geometry cells
     unchanged (model-independent). Combined-mean column dropped (not captured for
     the 3-head run).
3. Commit 0b76c61 — BACKLOG bookkeeping: moved those 3 items Open -> Done-this-session.
4. 167/167 sr tests green after the evaluate.py change.

Repo state right now:
- Branch main, 5 commits ahead of origin/main:
  58dd47f, a29e150, a719db0, 90b90cb, 0b76c61. User must push.
- Working tree clean EXCEPT still-untracked scripts/eval_real_cad.py and
  tests/data/real_eval/ — those are the user's parallel real-cad-eval-set work,
  DO NOT touch.

What the sibling session STARTED but did NOT finish:
- geometry-gen-mvp (S1) — brainstorming only, NO building.
- Per the rulebook + strategy doc rank 5 + contrarian "do it constrained, not
  open-ended" warning, the rule is: LLM emits param code over the box/cyl/boolean
  grammar from scripts/generate_parametric_steps.py.
- Brainstorm stopped at the first scoping question: how the LLM's output becomes
  OCC geometry. Three options on the table:
    A. JSON DSL (Pydantic-validated) -> trusted build_shape(spec). No LLM code ever
       exec'd. Recommended for safety; cleanest claim to "geometry generation."
    B. Constrained Python codegen -> sandboxed AST-allowlisted exec. Strongest
       codegen-loop narrative, residual exec-escape risk.
    C. Hybrid — DSL exec (A) + pretty-printed pythonOCC source shown as a
       read-only artifact (no exec).
- The user declined that question and paused both sessions before scoping further.
  No design spec written, no MVP code touched.
- Pick up the brainstorm from that exec-model question.

Quick wins still open in BACKLOG (S2/S3 — do not duplicate the closed three):
- S2 real-cad-eval-set (user-gated download; user's parallel work in progress)
- S2 finish-or-relabel-finetune (user-gated Colab)
- S2 grabcad-scrape-blocked (downgraded — only for held-out eval now)
- S2 gmsh-calibration (user task)
- S3 base-vs-env-marker-split
- S3 adr-backlog

Before anything else: read BACKLOG.md (S1 first), docs/exec-plans/path-c-4week.md,
memory project_simready.md CURRENT STATE block, and
docs/strategy/mecagent-gap-and-drift-2026-05-26.md (rank 5 + contrarian "do it
constrained" warning) for the geometry-gen scoping context.

sr env = C:\mm\sr\python.exe; set PYTHONPATH first.
Caveman mode on (chat terse; code/commits normal).
```

### Post-mortem (what this prompt actually produced)

- Exec-model question resolved as **A** (JSON DSL → trusted `build_shape`). ADR `docs/adr/0001-geometry-gen-dsl-over-codegen.md` captures the rationale.
- Additional scoping locked in same session: refine-loop **R1**, DSL surface **G1**, ship gate **E_grammar**, module layout **T1**, plus three unilateral build-side decisions (subprocess-by-default, minimal return shape, advisory defect head).
- Built and shipped geometry-gen-mvp v1 (commit `fa581f0`): `simready/gen/{spec,build}.py` + `build_part` agent tool + 31 new tests; full sr suite 198/198 green.
- v1 untracked files mentioned in the prompt (`scripts/eval_real_cad.py`, `tests/data/real_eval/`) became commit `849449a`: real-CAD OOD held-out eval (12 McMaster STEPs, 7/7 false-positive on the defect head, 4 OCC C++ timeouts hard-killed by a spawn-subprocess `Process.terminate()`).
- Memory + BACKLOG updated through both commits. Both commits pushed.

<!-- Append new streams below this line. -->

