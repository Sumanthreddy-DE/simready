# Pre-processing startup idea: demand evidence (2026-11-18)

**Status:** active
**Last verified:** 2026-11-18

Question: is SimReady, or some other mechanical simulation pre-processing product, a
startup idea with real demand? Two cheap evidence passes, run before any customer
interviews. Neither pass is a market sample; both are lead lists for the interviews.

## 1. Job-ad corpus

Source: a private corpus of engineering and ML job ads collected in autumn 2026 (mostly
Germany and the EU) — 2,122 files, 1,526 unique ads after content dedupe. Filter: an ad counts as CAE when it names at least 2 distinct CAE terms
(FEM, FEA, CAE, CFD, Ansys, Abaqus, Nastran, HyperMesh, LS-DYNA, ...). 129 ads pass.
Script: regex counts, strict patterns, about 20 snippets read by hand (not all 129).

| Duty named in the ad | CAE ads (of 129) |
|---|---|
| Automation / scripting (Python, APDL) | 53 |
| Test correlation / validation | 35 |
| ML / surrogate / reduced-order models | 29 |
| Load cases / boundary conditions | 16 |
| Meshing (strict) | 5 |
| FE model build / Modellaufbau / pre-processing | 5 |
| Defeaturing / geometry cleanup / mid-surfacing | 0 |
| Weld / bolt / contact connection modelling | 0 |

A first loose pass counted meshing at 47; most hits were German "Vernetzung" in the
networking sense. The zero for geometry cleanup passed a positive control (the pattern
matches test sentences) and a broader raw grep.

Reading:
- Geometry cleanup is never a named hiring duty. It hides inside "model build with
  HyperMesh". Job ads cannot show its pain; only interviews can.
- Scripted automation of model build and evaluation is the largest named demand.
- At least one funded vendor (Neural Concept) describes "design change, automated meshing,
  solver configuration, job execution" as the pipeline it sells, in its own job ads.

Bias: the corpus was collected for AI/ML-leaning engineering roles, so pure CAE roles are
under-represented. Ads measure hiring, not tool spend.

## 2. Community discussion (last30days engine, 90 days)

Three angles, subreddits fea, CFD, MechanicalEngineering, engineering, AskEngineers,
plus Hacker News and GitHub. arXiv lane not configured. Eng-Tips and CFD Online have no
lane, so they are not covered. Raw engine output is kept outside this repo.

Result: thin. Angle 1 returned 6 items (1 relevant), angle 2 returned 5 items (1
relevant), angle 3 ("manual vs automatic meshing") returned only off-topic matches. Two
r/fea threads were read in full:

- *"Anyone using Physics AI tools like Vinci, Ansys SimAI, or Neural Concept?"*
  (r/fea, Nov 2026). Practitioners: Simcenter PhysicsAI comes bundled in Altair
  licenses; Ansys SimAI needs an extra license, so one team skips it; PhysicsAI has
  "a handful of useful production use cases (mainly CFD and crash)". Several people
  already drive their normal FE tools with general agents (Claude + FreeCAD/CalculiX
  over MCP, Claude in a VM running their packages, Codex + COMSOL: "good until it
  wasn't ... not knowing what to do when things go wrong"). One vendor (WebCAE)
  ships an MCP server for the full setup chain. Closing comment: "Simulation is
  getting faster. Validation remains the hard part."
- *"Important things not talked about in the FEA community"* (r/fea, Nov 2026).
  Contact-stress results are mesh-limited; analysts misread contact-patch stresses;
  replies push sanity checks, hand calcs and submodelling over brute-force runtime.

## What the two passes agree on

1. Pre-processing pain (cleanup, meshing) does not surface in public demand signals.
   It may be real but is either absorbed by existing pre-processors (ANSA,
   HyperMesh) or done as junior / outsourced work. Not evidence for or against;
   interviews must settle it.
2. AI surrogates are becoming a bundled feature of the big suites (Altair/Siemens
   PhysicsAI, Ansys SimAI), not a standalone product a newcomer can sell.
3. The live, unowned gap is **checking**: engineers now let general agents set up
   simulations, and both the job ads (validation 35/129) and the practitioners say
   validation is the hard part. A model checker that catches setup errors in an
   FE model built by a person or an agent (unconstrained bodies, unit mismatches,
   contact definitions, mesh quality at stress hot spots, load-case sanity versus
   hand calcs) matches SimReady's existing identity as a checker.

## Interview hypotheses to test (step 3, not run yet)

- H1: Engineers who let an agent set up a model would pay for an independent
  check before solve. Kill if fewer than 3 of 10–15 interviewees describe a
  setup error that cost them a run or a wrong decision in the last 3 months.
- H2: Geometry cleanup still costs hours per model despite ANSA/HyperMesh. Kill if
  interviewees say their pre-processor handles it.
- H3: Customers need on-prem or local models. Check in every interview.
