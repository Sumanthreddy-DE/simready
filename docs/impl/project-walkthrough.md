# SimReady: start here

**Last verified:** Application source and generated map inspected on 2026-11-18 at `main` `aaecf6d` and SP1 worktree `27265f9`. Save-time status correction: another session subsequently published SP1 through `1e70789`; `STATE.md` now records checker-tag regrade → SP2 as next. The local graph still represents the earlier snapshot and needs refreshing.

## 1. The project in one sentence

**SimReady checks mechanical CAD geometry, lets an LLM explain or generate simple parts, and is evolving into a way to measure—and eventually train—AI CAD generators.**

It began as a portfolio project for MecAgent. The application was sent on October 5 and the GenCAD technical-test response on November 15, 2026, according to `BACKLOG.md`. The project now contains both a usable prototype and several research experiments. They share geometry tools, but they are not one finished AI model.

Three terms first:

- **STEP:** a file containing precise CAD geometry, such as a bracket or flange.
- **BRep:** the faces, edges and topology representing that geometry. A BRep is not a mesh.
- **FEA:** simulation performed downstream after meshing. SimReady neither meshes a part nor solves stress/thermal equations.

## 2. The three connected tracks

| Track | Input → output | Why it exists | Where it stands |
|---|---|---|---|
| Analysis + copilot | STEP → geometry findings, overall score, report and explanation | Help inspect a part before meshing | Implemented prototype on `main` |
| GenCAD experiment | Image → generated CadQuery program → solid | Test whether fine-tuning improves image-to-CAD generation | Qwen experiment and evaluation completed; optional second model |
| SP1 benchmark → SP2 → SP3 | Text request → construction recipe → part → constraint grades | Measure generation quality, then explore learning from checker feedback | SP1 published on main; checker-version regrade next, then SP2 |

The connecting idea is **generate → measure → improve**. The strongest connection so far is measurement: the geometry checker finds defects that visual similarity metrics can miss. Checker-reward post-training is a future stage, not an achieved result.

## 3. Follow a STEP file through the application

```text
CLI or Streamlit
  → analyze_file_safe                         pipeline.py
    → separate, killable Python process       pipeline_worker.py
      → load STEP and validate BRep           validator.py
      → OCC ShapeFix healing                  healer.py
      → count faces/edges/solids, bounding box parser.py
      → run geometry checks                   checks.py
      → extract face-adjacency graph          ml/graph_extractor.py
      → BRepSAGE or reported heuristic         ml/brepnet.py
      → combine findings and face scores      ml/combiner.py
      → split/report bodies if multiple       splitter.py
      → structured report                     report.py
  → terminal / JSON / HTML / UI
```

This order comes from `_analyze_file_inner`, not the older glossary's abbreviated pipeline description. Whole-part analysis happens before per-body reports.

**What the rules inspect:** degenerate geometry, non-manifold edges, open boundaries, short edges, thin walls/solids, small features/fillets, duplicate-body/face heuristics, orientation, sharp edges and self-intersection. The current dispatcher lists **13 check calls**. Some are heuristics; expensive self-intersection cases can be skipped explicitly.

**Why separate processes?** Native CAD-kernel operations can hang in a way a Python thread timeout cannot interrupt. The safe entry point lets the parent terminate the child.

**What does 85/100 mean?** A hand-designed summary: critical findings drive the overall score to zero; otherwise major/minor findings deduct points, and loaded ML face scores can add a penalty. It is not an 85% probability of meshing successfully. Labels such as `SimulationReady` are application labels, not downstream meshing evidence.

## 4. What the LLM actually does

The copilot is a tool-using conversation loop in `simready/copilot/agent.py`:

```text
Your message → model chooses a tool → Python executes it
            ← model sees tool result ←
            → another tool or final explanation
```

Its four tools in `simready/copilot/tools.py`:

| Tool | Actual job |
|---|---|
| `analyze_geometry` | Call the analysis pipeline and return a compact summary |
| `suggest_fixes` | Rank templated recommendations from findings |
| `lookup_standard` | Search locally indexed engineering-reference passages |
| `build_part` | Build a new STEP from a validated construction recipe |

The LLM is the coordinator and explainer. OpenCascade computes geometry; the rule code measures it. Fix recommendations do not automatically implement arbitrary repairs. ShapeFix is a separate, narrower healing operation.

`rag.py` uses sentence embeddings and cosine similarity over JSON, with a committed seed index when the larger local index is absent. This is small reference retrieval, not an online standards service.

## 5. How text becomes CAD

The production generation path uses a **DSL**: a small construction language represented as JSON. It does not execute arbitrary Python generated by the LLM.

For example, a plate with a hole is three operations:

1. Make a box, 80 × 60 × 10 mm.
2. Make a vertical cylinder, radius 5 mm, at the plate centre.
3. Subtract the cylinder from the box.

```text
scripts/simready_gen.py
  → simready/gen/cli.py
    → copilot → build_part(spec)
      → gen/spec.py validates PartSpec
      → gen/build.py executes box / cyl / fuse / cut
      → STEP file
    → gen/verify.py selects and analyzes the exact final artifact
```

Current limits: 1–16 operations; axis-aligned boxes; cylinders along +Z; union/subtraction; bounded dimensions; booleans refer to earlier operations; every nonfinal operation must be used. General sketches, rotations, fillets and arbitrary CAD feature trees are outside this grammar.

A successful generation command means a valid final artifact was produced and analyzed. Its analysis can still report `NotReady` or other problems. That is different from proving the design meets every engineering requirement.

The architectural choice is recorded in [ADR 0001](../adr/0001-geometry-gen-dsl-over-codegen.md). Follow `gen/spec.py` for the exact current grammar; the ADR contains historical discussion.

## 6. Where the GNN fits—and its limits

Think of the GNN as a learned extra inspector:

```text
CAD faces → nodes with surface/geometric features
shared boundaries → graph adjacency
  → BRepSAGE (2 GraphSAGE layers, hidden width 32)
    → face refinement classification
    → face complexity regression
    → whole-part defect classification
```

- `graph_extractor.py` builds the input.
- `model.py` defines the three-head network.
- `dataset.py` loads training graphs.
- `scripts/train.py` trains it.
- `brepnet.py` runs inference. Its filename is historical: the model is **BRepSAGE**, not the research BRepNet architecture.
- `weights/` contains the checkpoint and recorded metrics.

**Important:** the refinement head learns labels derived from rules. Agreement with those rules does not demonstrate discovery of independent defects. The defect head learns injected defect tags, but it generalizes poorly to real CAD.

The real-CAD probe flagged a synthetic-defect class on all 11 analyzed parts; those were presumed clean, not an independently verified 11-part clean holdout. A later strict inspection admitted only two verified-clean parts. Fitting on one and testing on the other did not fix the false positive and damaged synthetic defect recognition. The candidate was rejected.

Evidence: [real-CAD probe](../validation/real_eval_v2.md), [defect classifier](../validation/defect_classifier.md). The later negative experiment report is on branch `experiment/defect-real-clean` at `docs/validation/defect_head_real_clean_v1.md`, not in this `main` checkout.

**Assessment:** useful ML experimentation and failure analysis; not a demonstrated reliable real-world defect detector.

## 7. What the GenCAD work accomplished

This is a separate vision-language experiment. Training happens in `notebooks/gencad_train_qwen.ipynb`; generation/scoring uses `notebooks/gencad_baseline.ipynb`. The model outputs **CadQuery Python**, unlike the application's small JSON DSL.

Recorded results on the dataset's 100-row `hundred_subset`:

| Setup | Programs producing solids | Shape similarity |
|---|---:|---|
| Untuned Qwen2.5-VL-3B | 0/100 | 0 with invalid outputs counted as zero |
| Untuned + one example | 1/100 | Copies the example on 99 rows |
| QLoRA, 6k training examples / 1 epoch | 88/100 | Mean surface IoU 0.256 on the 88 valid outputs |
| Same saved outputs + stopping-rule repair | 100/100 | Mean surface IoU 0.230 over all 100 |

These two IoU averages have different denominators. On the common all-100 basis, the stopping rule changes mean IoU from 0.225 to 0.230. It mainly repairs execution; it does not solve reconstruction quality.

**Three different questions:**

1. Does the program run and produce a solid? **VSR**.
2. Does its shape resemble the reference? **IoU**.
3. Does its geometry have concerning defects? **SimReady checker**.

The test's IoU compares surface voxels and normalizes scale. A wrong-size plate can score 1.0. A visually similar part can self-intersect. That is why the checker bridge matters—but the overall analysis score also does not measure image fidelity.

Read [the GenCAD result](../validation/gencad_eval.md), then [four illustrated examples](../validation/gencad_examples.md). These are a better starting point than the raw notebooks.

## 8. SP1: the published benchmark

**Snapshot boundary:** when the map was generated, `main` did not contain `simready/bench/`; the code was inspected in `/tmp/simready-sp1-review` at `27265f9`. Another session subsequently merged and published SP1 on main through `1e70789`. The older graph omits that newly merged code; refresh it before using it as a complete current-code map.

SP1 is an exam for text-to-CAD models:

- 50 part concepts, each phrased explicitly, engineer-style and intent-only: 150 prompts.
- 37 concepts have current-DSL reference constructions; other concepts probe vocabulary limits separately.
- Grade solid validity and selected requirements: dimensions, volume, hole counts/diameters/patterns, bores and bosses.
- Log attempts so parts can be rebuilt and grades replayed without paying for another generation.

SP1's **constraint checker is distinct from the application's readiness score**. It runs a smaller validity/measurement path and does not use the full GNN-assisted report as its pass/fail answer.

| SP1 module | Responsibility |
|---|---|
| `concepts.py`, `prompts/concepts_v1.jsonl` | Typed prompts, ranges, reference constructions |
| `geometry.py` | Measure solid validity, extents, cylindrical features and fingerprints |
| `checker.py` | Compare measured features to the concept's requirements |
| `attempt.py` | Parse/validate a reply, build/grade in a subprocess, classify failures |
| `providers.py`, `prompting.py` | Model access and consistent generation instructions |
| `runner.py`, `runlog.py` | Schedule/resume attempts and record evidence |
| `replay.py` | Rebuild/regrade saved attempts |
| `report.py`, `__main__.py` | Metrics and command-line entry points |
| `simready/occ_compat.py` | Compatibility bridge between pythonocc and pip-installable OCP |

Tasks 1–10 are recorded complete. Current code includes backend/process failure exclusions, provider-argument contamination handling and malformed-JSON guards. Infrastructure errors must not count as model failures.

**Completed since the source walkthrough:** proofread, freeze, official runs, report/log publication and clean-clone reproduction are recorded complete in `STATE.md`. Official results there are GPT-6.1 Sol 96.2% pass@1 / 98.2% pass@5 and Gemini-4-Argon 95.5% / 97.3%, with 750 attempts each. These figures were not independently rechecked during Save Lite. The next gate is regrading the official logs under `1e70789`, because the checker changed after the official run while its stated version remained 1.0.0.

The reference pair is Gemini-4-Argon and GPT-6.1 Sol on D Labs. Earlier k=1 headroom figures (94.6% and 95.5%) are preliminary results, distinct from the official figures above. Do not claim the models are separable from those preliminary figures.

Use the published `docs/validation/bench_v1.md` for results and reproduction. Completed SP1 plans were moved to `docs/exec-plans/completed/`; use `STATE.md` for the current checker-version follow-up.

**Release state changed during this session:** the early inspection found a local `v0.5.1` preparation tag at `aaecf6d`. That is historical: `STATE.md` now records both `v0.5.1` and `bench-checker-1.0.0` published at `1e70789`. Tag targets were not independently rechecked during Save Lite; the checker-tag regrade remains the recorded open follow-up.

## 9. Where this is heading

```text
DONE: STEP analysis + copilot + limited text-to-STEP
DONE: GenCAD fine-tune, metric investigation and checker bridge
DONE: SP1 — benchmark, frozen prompts and replayable results published
NOW:  Regrade official logs under the subsequently changed checker
NEXT: SP2 — expand generation vocabulary where SP1 exposes limits
LATER:SP3 — test whether checker-based training improves a small generator
```

The separate `cad-rl-env` project owns the training-environment wrapper and packaging around SimReady's checker. SimReady owns the construction language and geometry/checking primitives. That environment is not another module secretly inside this repository.

**My recommendation:** understand the published SP1 result and resolve its checker-version regrade before expanding model experiments. Check quality matters: a model can exploit a weak check and receive a passing grade for the wrong design. A trusted measurement loop is more valuable now than another model run.

Optional/deferred items include a Gemma comparison, larger independently verified real-CAD datasets and the older text-only copilot fine-tune evaluation. They are not all required to reach the next SP1 milestone.

## 10. Folder map: scaffolding versus working logic

```text
simready/            Reusable application logic: analysis, copilot, generation, ML
ui/                  Streamlit frontends and UI helpers
scripts/             Thin entry points plus data/training/evaluation experiments
tests/               Unit/integration/CLI tests and small committed CAD fixtures
notebooks/           GPU-oriented experiments, especially GenCAD fine-tuning
weights/             Checkpoint + metrics (not every experiment artifact)
data/                Local/generated inputs, indexes and outputs; many are ignored
docs/impl/           Implementation explanations, artifact provenance, this guide
docs/validation/     Measured results, limitations, examples and reproduction notes
docs/adr/            Why architectural choices were made
docs/exec-plans/     Detailed plans; check branch and status before treating as current
Archive/             Preserved historical material
.github/workflows/   CI setup
environment.yml      Native CAD/PyTorch conda environment
requirements.txt     Additional Python packages
pytest.ini           Test markers/configuration
STATE.md             Status summary; verify specifics against code and evidence
BACKLOG.md           Open work, decisions, and historical completion records
```

This is principally a **Python package with thin CLIs and Streamlit frontends**, not a distributed backend/frontend/database platform. Python imports connect most components; subprocesses contain risky native CAD operations. Training/evaluation scripts are not services needed to launch the application.

## 11. Your first learning session

1. Read sections 1–5 above. You should be able to explain a STEP's path and a prompt's path.
2. Open [GenCAD examples](../validation/gencad_examples.md). Compare execution, fidelity and geometry defects.
3. In the Understand-Anything dashboard, choose **Learn** and follow the eight-stop tour. Click `pipeline.py`, `tools.py`, `spec.py`, then `model.py`.
4. Read sections 6–9. Explain which claims are demonstrated and which remain experiments.
5. Open the SP1 concepts in its worktree. Review one explicit/engineer/intent triplet and ask whether the checks would reject a plausible wrong answer.

You do not need to read every training script or historical session to understand the architecture.

## 12. Project-local Understand-Anything setup

- Upstream **2.9.8**, checkout `bb70fdb0489f8839ce55bf99dae0125ea067f712` under `.opencode/understand-anything/`.
- Project-only registration: `.opencode/opencode.json` points at the upstream skills. Quit and restart OpenCode from SimReady to load them.
- No global skill registration or auto-update hook. Tool checkout, package caches and `.ua/` are locally excluded with `.git/info/exclude`.
- `.ua/knowledge-graph.json`: 73 scanned files, 280 nodes, 288 edges, seven layers, eight tour stops at the earlier `aaecf6d` snapshot. Refresh after the SP1 merge; its final tour stop describes the earlier branch-only status.
- Generation used **Understand-Anything's scanner + Python AST imports/definitions + curated summaries/tour**, not its full multi-agent `/understand` pipeline. Imports include lazy imports but do not prove execution; dynamic dispatch/calls are not inferred. Notebooks, tests, historical docs and SP1 branch-only code are outside this graph.
- `.ua/build-onboarding-map.py` rebuilds this curated map from the existing scan. It is not an upstream incremental-analysis baseline.
- The built dashboard runs locally on the VPS. The session reply supplies the tokenized URL and laptop tunnel instructions.
- Verification passed for the upstream graph schema, source paths, references and dashboard HTML/data/source/lesson endpoints. Browser rendering has not been visually inspected on this VPS.

After restarting, the installed `understand`, `understand-dashboard`, `understand-explain`, `understand-chat` and other skills are available. A future full analysis is a separate, more expensive pass; the curated map already supports source navigation and the beginner tour.
