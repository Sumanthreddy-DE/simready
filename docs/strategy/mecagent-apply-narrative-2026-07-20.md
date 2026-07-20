# MecAgent Application Narrative — 2026-07-20

**Role:** ML/AI Founding Engineer.
**Decision:** GO (Stream D item E, decided with user 2026-07-20). User sends; this doc is
the raw material — cover-note draft + talking points + claims ledger. Adapt tone, don't
paste blindly.

**Companion docs:** JD gap table + hiring-manager review:
`mecagent-gap-and-drift-2026-05-26.md` (section C = claims to NEVER make).

---

## 1. The one-paragraph pitch (cover-note core)

> I built SimReady, an AI copilot for FEA pre-processing: a multi-turn LLM agent over a
> pythonOCC B-Rep analysis pipeline that scores simulation-readiness, explains findings,
> and now *generates* geometry — the LLM emits a typed, Pydantic-validated CAD spec (never
> executable code) that a trusted executor builds into STEP and feeds back through the same
> analysis pipeline. The generate→analyze loop is evaluated live against two hosted models
> at 5/5 grammar-valid parts each. What I think distinguishes the project is its evaluation
> discipline: leakage-free source-grouped splits, a held-out real-CAD probe that documents
> where my own GNN fails (11/11 defect-head false positives on real McMaster parts — recorded
> as a negative result, with the root cause identified, instead of quietly dropped), and a
> test suite + CI that gate every claim in the README.

## 2. Why the honest negative is the lead, not the apology

MecAgent builds agentic CAD for engineers. Engineers distrust ML that overclaims. The
strongest signal a founding ML engineer can send is *calibration*: knowing exactly where the
model works, where it doesn't, and why.

- The README's Results section leads with the label-source column, not the accuracy column.
- The circular-label problem was found, named, and partially fixed (non-circular defect head
  on injected ground-truth tags) — and the remaining circularity is stated, not hidden.
- The augmentation attempt that *failed* to fix real-CAD false positives is written up with
  the mechanism (synthetic box/cyl grammar lacks the real surface-type vocabulary — B-splines,
  cones, tori) and the remaining levers. One retrain, honest conclusion, stop.
- Framing line: **"I can tell you every number in this repo that I don't trust, and why."**

## 3. JD bullet mapping (talking points)

| JD bullet | Evidence | One-liner |
|---|---|---|
| Geometry generation | `simready/gen/` DSL + trusted executor + `build_part` tool; live eval 5/5 + 5/5 (`docs/validation/geometry_gen_eval.md`) | "Constrained generation: the LLM emits a validated spec, not code — and a failure mode I observed (dropped final boolean) became a validator rule that bounces bad specs back into the agent loop." |
| Tool orchestration | 4-tool multi-turn agent, provider-swappable, retry/backoff, token-budgeted truncation (`simready/copilot/agent.py`) | "Found and worked around a NIM chat-template 500 on parallel tool calls — the kind of provider-edge bug you only meet running agents for real." |
| GNN / embeddings for CAD | B-Rep → face-adjacency graph, 12-dim features, 3-head GraphSAGE, dual-backend provenance | "BRepSAGE — a GraphSAGE over B-Rep face graphs. Infrastructure, not research novelty, and I say so." |
| Evaluation pipelines | 6-metric gold-set harness (n=50, held out of training), leakage-free splits, real-CAD gate, CI | "Random split says 0.975; the honest source-grouped split says 0.848/0.487. I ship the second number." |
| Fine-tune pipeline | QLoRA notebook + 1455 traces + eval harness; one run captured (numbers in `docs/finetune_results.md`) | Phrase as **pipeline** — harness survives even if the model result is unremarkable. |
| Production ML + CAD APIs | OCC pathology war stories: BOPAlgo hangs immune to Python watchdogs → killable-subprocess isolation; 12 h hang diagnosed to B-spline faces | "OCC C++ doesn't care about your GIL. I moved analysis into a terminate-able child at every entry point." |
| Bridge AI ↔ engineer workflows | Streamlit chat + colored per-face render + healed-STEP download; user's own Simufact/NX/Creo background | STEP-export pain is the personal credibility anchor — the user has lived this workflow. |

## 4. Numbers safe to cite (as of 2026-07-20)

- 227 tests passing (5 live-LLM opt-in), CI green (fast spec job + full micromamba OCC suite).
- Generation eval: GLM 5.2 5/5; Llama-3.3-70B 3/5 → 5/5 after the orphan-step rule.
- Defect head (non-circular label): 0.756 val accuracy on a leakage-free source-grouped split.
- Refinement head honest pair: 0.848 acc / 0.487 recall (leakage-free) vs 0.975 (leaky random) — cite both, in that order.
- Real-CAD probe: 11/12 parts analyzed, zero hangs; defect head 11/11 FP (the honest negative).
- Held-out fixtures recall 0.23 → 0.69 from degraded-data retrain.

**Do NOT cite** (strategy doc §C): standalone "100% precision", "97.5% accuracy" without the
split caveat, "implemented BRepNet", "fine-tuned model" as a result claim, any "real-CAD
validated" phrasing implying the ML head works on real parts.

## 5. Anticipated pushback + answers

- *"Your GNN doesn't work on real CAD."* — Correct, and the repo says so first. The defect
  head is trained on a synthetic grammar whose surface vocabulary can't cover real parts; I
  proved augmentation within that grammar can't close it, and listed the three levers that
  could (real-CAD labels, real negatives in training, grammar extension to revolved surfaces).
- *"Why a DSL instead of letting the LLM write CAD code?"* — ADR 0001: no LLM code execution,
  validation before build, failure modes become validator rules. Generation quality becomes a
  schema/prompt problem instead of a sandbox-security problem.
- *"What would you do first at MecAgent?"* — The refine loop: findings from analysis fed back
  into spec revision. The pipeline already produces machine-readable findings; closing the
  loop is the natural next step and maps to their product.

## 6. Send checklist

- [ ] All commits pushed; CI green on the pushed HEAD (README claims are checked against it)
- [ ] README render check on GitHub (tables, mermaid)
- [ ] Cover note adapted from §1 in user's own voice
- [ ] Record actual send (date + channel) in STATE.md — only after user confirms sent
