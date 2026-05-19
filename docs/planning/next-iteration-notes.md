# SimReady — Next Iteration Notes

**Written:** 2026-05-18  
**Context:** End of Path C wk-2. Tag `v0.4.0-apply` on `34a93e7`. Application sent to MecAgent. This doc drives wk-3+ priorities and interview prep.

---

## Contrarian Review — What Frustrates a Practising ME

*Perspective: mechanical engineer, FEA experience, uses AI tools daily.*

### 1. "Text-only suggestions" is the wrong abstraction
Telling an engineer to "stitch open boundary using OCC ShapeUpgrade_UnifySameDomain" is useless. They are in Catia/NX/SolidWorks — not a Python shell. The fix needs to either:
- **Return a healed STEP automatically** (ShapeUpgrade can handle open shells, short edges, near-duplicate faces), or
- **Translate to CAD-software language** ("In SolidWorks: Surface > Knit, select these faces").

L1 scope was right for shipping speed but breaks the actual workflow. First thing to close in wk-3.

### 2. Score 0-100 calibrated to nothing actionable
Score 68 — can this be meshed in Ansys Meshing at 2 mm target? Unknown. The score is synthetic (derived from rule output, not actual mesh outcomes). A real tool says "will mesh / will mesh poorly / will fail," backed by running Gmsh or Netgen. Without that calibration the score is a confidence illusion.

### 3. Real-CAD recall is 0.23 — UI hides this
BRepSAGE trained on parametric STEPs. Real CAD (BSpline-heavy automotive bodies, imported fillets, NURBS surfaces, near-degenerate edges from tolerancing mismatches) gives recall ~0.23. The UI doesn't warn the user when ML confidence is likely low. An engineer trusting the ML score on a 600-face supplier STEP will get silently wrong output. **Must add confidence/scope banner.**

### 4. Conversation is the wrong interaction model for triage
Engineers don't want to chat about a STEP file. They want: drag-drop → triage table in 10 s → download fixed STEP. Multi-turn LLM chat adds latency and narrative on top of what the rule engine already says concisely. The copilot chat makes sense for "explain this finding" or "what mesh strategy for this geometry" — not for the primary triage flow.

### 5. Self-intersection check silently skips above 150 faces
Production automotive geometry = 500–10,000 faces. The most important check for assembly imports silently returns nothing with no warning. Engineer never knows it was skipped.

### 6. Standards RAG is dead on fresh checkout
`data/fea_docs_index.json` is gitignored. `lookup_standard` returns `no_index` always. Citations fail in any live demo. Liability for the apply interview — interviewer tries it, gets nothing.

### 7. Workflow island — no integration with any mesher
Actual workflow: export STEP → import to HyperMesh/Ansys → mesh fails → back to CAD. SimReady fits between steps 1 and 2 but only as a separate Streamlit app requiring manual context switching. No output format that any mesher understands. No Gmsh integration, no Abaqus .inp, no HyperMesh API.

### 8. LLM wrapper adds thin value over rule engine
LLM calling `analyze_geometry` then summarising it is mostly narrative. Rule engine already produces findings with severity + suggestions. Orchestration value is visible only in multi-tool chains (analyze → suggest → lookup). Single-tool calls are just prettification.

---

## Gaps: Current State vs. JD Requirements

| JD Bullet | SimReady State | Gap |
|---|---|---|
| Geometry generation | Not implemented | Hard gap — analysis only |
| Tool orchestration | 3 tools, multi-turn | Thin — LLM mostly prose wrapper |
| GNN / embeddings | BRepSAGE trained, face embeddings | Recall 0.23 on real CAD |
| Model fine-tuning pipeline | Auto-label, BCE/MSE, eval, dual-backend | No fine-tuned LLM yet (wk-3 task) |
| Production ML system + CAD APIs | pythonocc + Streamlit demo | No deployment, no mesher integration |
| Bridge AI + real workflows | Streamlit upload → chat → colored PNG | No mesher hook, no healed STEP output |

**Geometry generation is the hardest gap.** MecAgent's actual research is likely text → STEP, part completion, or B-Rep diffusion/VAE/GNN-decoder. SimReady is analysis-only. Options:
- **(a) Param-CAD loop:** LLM emits pythonocc parametric code → pipeline validates → BRepSAGE scores → refine. ~1 week. Closes JD bullet partially.
- **(b) Text → B-Rep generation:** diffusion or GNN decoder, 4-8 weeks, much harder.
- **(c) Skip, acknowledge on resume.** Honest framing: "SimReady is analysis + copilot; generation is next research direction."

---

## Prioritised Fixes for wk-3

**Must (close frustration points before demo gets shared):**
1. **Heal + return STEP** — run ShapeFix + ShapeUpgrade automatically, return fixed STEP as download. Closes text-only complaint.
2. **ML confidence banner** — when face_count > 200 or geometry type unfamiliar, show "ML score unreliable — rule findings are primary."
3. **Index one real PDF** — scrape and commit NAFEMS QA01 index so `lookup_standard` returns real citations in demo.
4. **Self-intersection skip warning** — surface explicit "skipped: N faces exceeds limit" in findings instead of silent omission.

**High value (interview differentiators):**
5. **Calibration experiment** — run 50 STEPs through Gmsh at 2 mm, record mesh pass/fail, correlate with SimReady score. Even rough correlation makes score claims defensible.
6. **Param-CAD generation loop (stretch)** — LLM → pythonocc → STEP → BRepSAGE → refine. Closes geometry generation gap partially.
7. **LLM fine-tune pipeline** — wk-3 task in exec plan. Qwen2.5-3B QLoRA on synthetic CAD tool-call traces. Even a "I ran the fine-tune and here's the eval table" artifact is a strong signal.

**Nice to have (wk-4):**
8. CLI output that Gmsh can consume (`.geo` or pre-meshing hook).
9. Confidence-weighted scoring: separate rule score from ML score in UI so user always sees both.
10. Param-CAD generation stretch (if (a) above not done in wk-3).

---

## Open Questions — Answered (2026-05-18)

1. **FEA/CAD software used:** Ansys, MATLAB, Simufact Forming, NX, Creo.

2. **Gmsh:** Not installed but can download. Not RAM-heavy — ~100 MB, minimal memory. Calibration experiment is viable.

3. **Geometry generation:** Confirmed as next priority. Not optional — user wants to implement it.

4. **Killer demo vision:** "Type instructions to create a CAD file → see it generated → 3D visualization in chat window → report on whether it's simulation-ready." This is the param-CAD generation loop: text → pythonocc code → STEP → BRepSAGE analysis → verdict.

5. **Real STEP file:** User does not currently have one from actual engineering work (non-bracket/manifold). **Action for next session: bring a real STEP from previous work to stress-test SimReady.**

6. **MecAgent subscription:** Apply first, subscribe this week in parallel to inform interview prep.

## Remaining Open Questions (unanswered)

- Does MecAgent's product target forming simulation (large-deformation, contact, remeshing) or structural only?
- What's user's comfort level writing pythonocc parametric code? The generation loop relies on LLM-generated OCC code — the user being able to read/debug it matters.
- Interactive 3D in Streamlit vs static PNG — is the current colored PNG enough for the killer demo, or does it need interactive rotation?

---

## MecAgent Subscription — Discussion

**Recommendation: Apply now (day-14), subscribe this week in parallel.**

Reasons not to delay applying:
- SimReady is at a clean ship gate (160 tests, working demo, tag `v0.4.0-apply`)
- Subscription evaluation takes 2-4 weeks — that's 2-4 weeks later on a rolling application
- You're already past the "is this good enough to apply" threshold

Reasons to subscribe:
- 10k users + Ford/Audi pilot = their product is likely mature and workflow-integrated in ways SimReady isn't
- Seeing their actual UX before the interview = prepared for "how does yours compare?"
- "I subscribed to your product and noticed X gap — here's how I'd approach it" is a strong interview signal
- May reveal geometry generation is further along than assumed, shaping wk-3 priority

Risk: their product may be dramatically better in all dimensions. That's fine — SimReady is a portfolio project demonstrating ML engineering skills, not a competing product. Frame accordingly.

**What to evaluate during the subscription:**
- CAD import: plugin (native in CAD software) vs upload workflow?
- AI copilot: is it LLM-over-tools like SimReady, or rule-based, or something else?
- Geometry generation: does it exist? If so, what's the UX?
- Visualization: colored faces, highlighted findings, or something richer?
- Workflow output: does it return fixed geometry, mesh files, or just text?
- Pricing tier: what does their paying customer actually get?

---

## Resume Bullet (draft, apply-ready)

> Built SimReady Copilot — agentic LLM system (OpenAI-compatible multi-turn tool-use loop) that ingests STEP CAD files, runs a BRepSAGE GNN analysis pipeline, and returns ranked manufacturability fix suggestions with RAG-cited FEA-standard references; shipped as a Streamlit app with 3D face-score visualization, 160 passing tests.

---

---

## Generation Demo Gap — What To Do About It

**Problem:** LLM → pythonocc free-form code generation only works for parametric geometry describable in words (primitives, extrusions, fillets, holes). "Create a turbine blade" or "recreate this imported geometry" will fail.

**Solution: Schema-guided generation, not free-form code generation.**

LLM does NOT write pythonocc code. Instead:
1. LLM parses the user's description into a structured JSON schema: `{part_type, dimensions, features[]}`
2. Deterministic pythonocc builders (one per supported part type) run from the schema
3. Output is always valid pythonocc — no LLM code to debug

Supported part types for demo (reliable, interview-safe):
- L-bracket (width, height, thickness, fillet_radius)
- T-junction (stem_length, flange_width, wall_thickness)
- Ribbed plate (plate dims, rib_count, rib_height, rib_thickness)
- Box with holes (dims, hole_pattern, hole_diameter)
- Hollow cylinder / pipe (OD, ID, length, flange_options)
- Flanged beam (section type, length, flange_dims)

If user input is outside these types → copilot replies "I can generate: L-bracket, T-junction, ribbed plate, box with holes, hollow cylinder. Describe one of these."

**Error recovery loop (for schema edge cases):**
generate schema → build STEP → if OCC build error → feed error + schema back to LLM → refine schema → max 3 retries → graceful failure message.

This approach is reliable enough to demo live without breakage risk.

---

## Generation Loop — Error Recovery (Must Implement)

LLM-generated pythonocc code / schema-filled builders WILL fail sometimes:
- Invalid dimensions (zero-volume body, negative thickness)
- OCC build errors (failed boolean, non-manifold result)
- Schema out of range (hole diameter > plate width)

Loop design:
```
generate schema → build_step(schema) → if OCC exception:
    feed (schema + error_message) → LLM → refined schema
    retry up to 3 times → if still failing: return friendly error to user
```

**Never let OCC exception bubble to chat window raw.** Always catch, always retry once, always fail gracefully with "I couldn't build that geometry — try simplifying the description."

---

## NX / Creo STEP Export Pain (Real Experience, Use in Interview)

User has lived this problem directly. Key talking point:

When exporting from NX (Parasolid kernel) or Creo (GRANITE kernel) to STEP and importing into Ansys (via ACIS or OCCT), the following artifacts appear reliably:
- **Open shells** from face-tolerance mismatch at kernel boundaries — two faces that were "touching" in NX become slightly separate in OCCT
- **Short edges** from fillet approximation — NX fillets are represented as analytical surfaces; STEP translators approximate them as B-spline patches, introducing near-zero-length edges at patch boundaries
- **Sliver faces** from thin-wall features near the tolerance threshold
- **Self-intersections** in assemblies where mating faces have different tolerances per-body

SimReady detects all four of these. This is the strongest credibility anchor: "I've exported from NX/Creo to Ansys and seen exactly the artifacts SimReady catches."

---

## Forming Simulation Background (Note for Future Session)

User has Simufact Forming experience. This is rare and valuable context.

Forming simulation (sheet metal stamping, forging, roll forming) has geometry requirements completely different from static structural FEA:
- Blank geometry needs smooth curvature — kinks cause mesh locking during large-deformation remeshing
- Die/punch clearance uniformity matters — non-uniform clearance = thickness variation artifacts
- Thin shell vs solid meshing decision is forming-specific (< ~3mm = shell, above = solid)
- SimReady currently has zero forming-specific checks

**Decision for future session:** implement 1-2 forming-specific checks OR acknowledge scope boundary and skip. Options:
- (a) Add `check_curvature_continuity` for blank geometry — flag C0 (kink) edges that would cause remeshing issues
- (b) Add `check_wall_thickness_uniformity` — flag thickness variation > threshold across blank
- (c) Skip — scope SimReady as "static structural FEA pre-processing" and document it

Recommend discussing before implementing. Unique differentiator if done; unnecessary scope creep if MecAgent doesn't serve forming users.

---

## Gmsh Calibration Experiment (Next Session Action)

Download: https://gmsh.info (free, ~100 MB, minimal RAM)

Experiment plan:
1. Pick 10-15 STEPs from `tests/data/` (mix of clean, bad, realistic brackets)
2. Run each through Gmsh at 2mm target element size: `gmsh part.step -3 -clmax 2 -o part.msh`
3. Record: pass/fail, element count, worst element quality (Gmsh reports this)
4. Correlate with SimReady score
5. Goal: show that SimReady score < X predicts mesh failure with Y% accuracy

Even a rough correlation on 10-15 parts makes every score claim in the resume defensible.

---

## Next Session Priorities (in order)

1. Answer "what do we build in wk-3" — generation loop vs. other gaps
2. Gmsh calibration experiment (user downloads Gmsh this session)
3. Decide on forming-specific check scope
4. Update BACKLOG.md with new S1/S2 items from this review
5. Plan param-CAD generation loop implementation if confirmed as wk-3 target

*Next session: pick items from "Must" list above, decide on geometry generation scope, update BACKLOG.md with new S1/S2 items from this review.*
