# MecAgent Gap Analysis, Drift Diagnosis & Re-Prioritization

**Date:** 2026-05-26
**Trigger:** Hiring-manager-lens review of the whole repo (MecAgent ML/AI Founding Engineer JD), followed by a strategy discussion.
**Status:** Decisions below supersede the wk-3 fine-tune emphasis. The 4-week plan
(`docs/exec-plans/path-c-4week.md`) is now partially redirected — see "Re-prioritized plan".

This file is the **canonical** record. Memory holds only a pointer
(`project_simready.md`, `project_simready-contrarian.md`).

---

## 1. The drift diagnosis (most important section)

The project's own contrarian memory, written day 1 (2026-05-13), already ranked the work correctly:

- **Deepen the GNN side over the LLM layer** for *this* team specifically — *do not pitch SimReady as "a RAG bot for CAD."* (`project_simready-contrarian.md` item #3)
- **Geometry generation is the open JD gap**; the LLM→pythonOCC→validate loop closes it in ~1 week (item #7).
- The JD's **first bullet is geometry generation**.

What wk-3 (`a719db0`, the last ~2 weeks) actually produced:

- An **LLM fine-tune pipeline** — the lower-signal direction — **that was never run** (`notebooks/finetune_copilot.ipynb` has 0 executed output cells).
- Day-9 GNN recall fix → **not started**.
- Geometry generation → **not started**.

**Conclusion:** we wrote down the right priority, then spent two weeks on the secondary one.

**Mechanism (so it doesn't repeat):** the high-value work was *user-gated* (needs data
download / labeling); the low-value work was *assistant-automatable* (write scripts, generate
traces overnight). We optimized for "what can we ship code on tonight," not "what moves the
JD needle." Path of least resistance won. This was a **process failure, not a knowledge
failure** — the knowledge was already in memory.

**Correction (2026-05-26):** the user is now available for gated tasks, AND the highest-value
GNN work turns out to be self-unblockable anyway (see pointer #2 and #3 below). The drift
excuse is gone in both directions.

---

## 2. New pointers — not previously in any memory file

1. **The headline model artifact is invisible to anyone who clones the repo.**
   `weights/brepnet.pt` + `weights/brepnet_meta.json` are **gitignored**. The "97.5% val
   accuracy / 100% precision" number lives *only* in an untracked file. A MecAgent reviewer
   opening the GitHub repo sees no model and no metrics — only the fallback heuristic. The
   contrarian memory worried whether the number was *honest*; it never noticed the number is
   *absent*. Fix: commit a small tracked checkpoint + a tracked `metrics.json`.

2. **The circular-label fix is already in the repo, unwired.**
   `scripts/generate_degraded_steps.py:206-216` writes ground-truth `defect_tags` per degraded
   variant — a label *independent* of the rule layer. But `scripts/auto_label.py:74` ignores
   them and derives the GNN refinement label from `rule_per_face > 0.5` — i.e. the model is
   trained to re-learn a deterministic rule on the same OCC features it ingests. Wiring the
   tags into the label breaks the circularity that contrarian #2 calls a ceiling. **Needs zero
   external data.**

3. **The recall fix is NOT actually blocked on GrabCAD.**
   `grabcad-scrape-blocked` was treated as the blocker for day-9. But contrarian #1 and
   `docs/validation/grabcad.md` both say "auto-degrade parametric solids" is a valid recall
   lift, and the generator exists. It was run to **15** variants; the plan targets **200**.
   Generate 200 from the 500 parametric solids, label by injected tag (pointer #2), retrain.
   No download, no manual labeling. The "blocked" label was a drift excuse. GrabCAD/SimJEB
   real STEPs are now only needed as a **held-out real-CAD eval set**, not as training data.

4. **"BRepNet" naming is an interview landmine.**
   The model is a 2-layer GraphSAGE (`simready/ml/model.py:36-72`), but the file is
   `brepnet.py` and the README says "BRepNet inference scaffold." BRepNet (Lambourne et al.)
   is a different, specific architecture. Claiming "I implemented BRepNet" to someone who knows
   the literature ends badly. Narrative fix: "BRepSAGE — a GraphSAGE encoder over B-Rep face
   graphs."

---

## 3. Re-prioritized plan (for the JD, not for shippability)

The user keeps the FEA-preprocessor as the project's base (it predates the MecAgent framing
and is the genuine interest). The plan deepens the preprocessor's ML credibility first, then
adds the generation loop.

| Rank | Work | JD bullet | Gated on user? | Est | Owner |
|---|---|---|---|---|---|
| 1 | **Break the circular label + retrain + commit tracked weights** — wire `.tags.json` into `auto_label`, generate 200 degraded, retrain on parametric+degraded, eval, commit checkpoint + `metrics.json` | domain-specific AI for CAD, data strategy, production ML *visible* | No | 3-4 d | assistant |
| 2 | **Held-out real-CAD eval** — user downloads 5-10 SimJEB/GrabCAD STEPs (label-free generalization probe); assistant wires the eval | "no held-out real test" gap (review D1) | download only | 0.5 d | user + assistant |
| 3 | **Finish ONE honest QLoRA run** — fill the fine-tune table, then stop investing | evaluation pipelines (keep the harness) | Colab run | ≤1 d | user + assistant |
| 4 | **Repo self-demonstration** — README leads with agent + GNN + (later) gen; tracked numbers; arch diagram | turns hidden work into seen work | No | 1 d | assistant |
| 5 | **Geometry-generation MVP** — LLM emits *constrained* pythonOCC param code (box/cyl/boolean vocab) → execute sandboxed → SimReady pipeline → BRepSAGE validates → refine loop. **Plan deliberately (brainstorm first), don't impulse-build.** | "geometry generation" (JD bullet #1, currently zero coverage) | No | ~1 wk | assistant |

Ranks 1, 4, 5 are self-unblockable. Ranks 2, 3 are the user's parallel tasks.

---

## 4. Division of labor

**Assistant (no gate, start now):** rank 1 (circular-label fix → 200 degraded → retrain →
commit tracked weights + metrics). Then rank 4, then plan rank 5.

**User (parallel, own pace):**
- **Task A — real eval set:** download 5-10 real STEPs. Prefer **SimJEB**
  (`scripts/download_simjeb.py`, real engineering brackets, no anti-bot wall) over GrabCAD.
  Place in `tests/data/real_eval/`. Do NOT hand-label (optional if wanted). Assistant wires a
  generalization-probe eval.
- **Task B — QLoRA run:** upload `data/fine_tune/train.jsonl` + `val.jsonl` to Drive
  `MyDrive/simready/`, open `notebooks/finetune_copilot.ipynb` in Colab, set runtime to T4,
  Run All, download the adapter. Assistant supplies click-by-click steps on request.

---

## 5. Contrarian takes (kept honest, including against the ranking above)

- **Against rank 5:** a half-working text→STEP loop that emits garbage parts is *worse* than no
  geometry generation — interviewer sees broken output live. Mitigation: constrain the LLM to
  the primitive+boolean grammar `generate_parametric_steps.py` already uses by hand. Codegen
  within a tiny safe grammar — low garbage risk, and the pipeline+BRepSAGE validation step
  *catching* bad output is itself the demo. Do it constrained, not open-ended B-rep generation.
- **On the fine-tune:** not wasted, but only the **eval harness** survives (6 deterministic
  metrics, tool-call exactness) — that maps to "evaluation pipelines." Drop the fine-tuned
  *model* as an ambition unless Colab runs in an afternoon. Don't let sunk cost pull another week.
- **On the GNN, hardest truth:** even after breaking the circular label, the model predicts a
  rule-shaped target. It is *infrastructure* (training loop, dual-backend provenance, data
  pipeline), not research novelty. Frame it that way in interview. The generation loop is the
  smart part, and it isn't built yet.
- **Blunt:** if there were only one week before an interview, skip the GNN retrain and build the
  generation MVP — "I built a generate-validate-refine CAD loop" beats "I lifted recall on a
  rule-shaped label" for *this* company. Recall is defense; generation is their offense. The
  user's available time changes this calculus (both tracks are now affordable), so we do GNN
  first (cheap, strengthens the base) then generation.

---

## Appendix — Hiring-manager review (verbatim, reusable for interview prep)

Persona: senior ME + strong ML engineer hiring an ML/AI Founding Engineer for an agentic-CAD
product. Evidence cited as `file:line` against the repo at commit `a719db0`.

### A — Recruiter magnets

1. **LLM tool-use agent over a real CAD pipeline** — multi-turn, provider-swappable
   (OpenAI/NIM/OpenRouter/local), retry/backoff, token-budgeted tool-result truncation.
   `simready/copilot/agent.py:120-289`, `:291-324`, `:352-391`, `:148-154`;
   `simready/copilot/tools.py:27-125`, `:132-341`.
2. **Custom B-Rep → graph encoder feeding a GNN** — OCC topology → 12-dim per-face features
   (surface-type one-hot + log-area + normal mag + mean curvature + UV extents).
   `simready/ml/graph_extractor.py:1-45`; `simready/ml/model.py:22-23, 75-98`, `:36-72`.
3. **Honest dual-backend inference with provenance** (`weights_loaded`/`score_source`/
   `model_name`). `simready/ml/brepnet.py:248-255`, `:50-59`, `:232-245`, `:127-165`.
4. **QLoRA fine-tune pipeline + 6-metric eval** — 1,455 teacher traces, 951/39 ChatML split.
   `data/fine_tune/traces.jsonl`; `scripts/prep_finetune_dataset.py`;
   `scripts/eval_finetune.py`; `docs/finetune_results.md:33-43`. (Phrase as *pipeline*, not result.)
5. **Eval-first data discipline** — 50 hand-written gold traces, never mixed into train.
   `tests/data/gold_traces.jsonl`; `docs/exec-plans/path-c-4week.md:181`.
6. **Real-CAD validation gate that honestly exposes the model's failure** — ML aggregate
   0.30-0.34 vs rule 0.67-0.88. `docs/validation/grabcad.md:16-18`, `:66-83`.
7. **CAD robustness under OCC pathologies** — self-intersection check hardened >10 min → 6.3 s
   via face-count guard + 30 s watchdog. `docs/validation/grabcad.md:55-64`.
8. **RAG-lite with correct sizing judgment** — JSON + cosine over sentence-transformers.
   `simready/copilot/rag.py`; `simready/copilot/tools.py:311-341`.

### B — Honest metric ledger

| # | Claim | Where | Split | Type | n | Baseline? |
|---|---|---|---|---|---|---|
| 1 | val acc **0.9746**, precision **1.000**, recall **0.870** | `weights/brepnet_meta.json:218-226` | random 80/20 of 500 parametric (`simready/ml/dataset.py:88-99`) | in-distribution val, **gitignored** | 100 graphs / 154 pos faces | none |
| 2 | acc **0.608**, precision **1.000**, recall **0.231**, f1 **0.375** | `weights/eval_fixtures.json:6-14` | `data/labels_fixtures` | held-out fixtures, same rule label, **gitignored** | 7 graphs / 51 faces | none |
| 3 | ML agg **0.30-0.34**; scores **38.3/38.9/68.5** | `docs/validation/grabcad.md:16-18` | 3 real GrabCAD | real, **no labels** → pipeline outputs | 3 | vs rule 0.67-0.88 |
| 4 | scores **81.9-90.8** | `docs/validation/realistic_brackets.md:13-17` | 5 synthetic harder | no labels → outputs | 5 | none |
| 5 | tool_call_exact **0.760**, partial 0.920, order 0.780, format 0.780, sections 0.780, theme 0.678 | `docs/finetune_results.md:100-109` | 50 gold | held-out, **70B teacher only** | 50 | none (base/LoRA cols empty `:49-57`) |
| 6 | 500 parametric / 1,455 traces / 951+39 / 50 gold / **15** degraded | disk + `README.md:107,190` | — | — | — | 15 on disk vs 200 claimed |
| 7 | latency 9.07/3.85/6.31 s; train 5.2 s/10 epochs | `grabcad.md:16-18`, `brepnet_meta.json:4` | — | wall-clock | — | none |

**"97.5% / 100% precision" audit:** random 80/20 of 500 fully-synthetic parametric STEPs
(`scripts/generate_parametric_steps.py:1-12`); train 400 / val 100 graphs; ~20% positive
(imbalanced); label = `rule_per_face > 0.5` (circular). Does **not** generalize — same model
scores acc 0.608 / recall 0.231 on real-ish fixtures and ML-agg 0.30-0.34 on real GrabCAD.
"100% precision" = threshold artifact (6 positive predictions on 51 faces, all right, 20/26 missed).

### C — Do not put on the CV

- "97.5% val acc / 100% precision GNN" — circular label, in-distribution synthetic split,
  weights not in repo, collapses to 0.23 recall on real fixtures.
- Any standalone "100% precision" — threshold artifact; invites the recall question.
- "Fine-tuned Qwen2.5-3B" — never trained (notebook 0 outputs; table columns empty).
- "Implemented BRepNet" — it's GraphSAGE; naming trap.
- "200 degraded-synthetic STEPs" — only 15 exist.
- "Real-CAD validated" — 3 GrabCAD + 5 synthetic, <200 faces, no labels.
- "160 tests passing" as ML-quality signal — LLM tests are mocked.

### D — Gaps (to-do, not bullets)

1. No held-out real-CAD labeled test; recall 0.23 vs exit-criterion >0.50.
2. Fine-tune unfinished: no LoRA weights, empty comparison table, empty gap analysis.
3. Repo not self-demonstrating — weights + metrics gitignored.
4. No benchmark table / architecture diagram in README; README still Phase-3-framed.
5. No deployment run; no mesher (Gmsh) hook.
6. No CI; ML tests mock the LLM.
7. Geometry *generation* entirely absent (JD bullet #1).
8. Circular-label design needs an external label source.
