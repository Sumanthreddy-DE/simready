# ADR 0001 — Geometry-gen: JSON DSL over Sandboxed Codegen

- **Status:** Accepted (2026-05-28)
- **Owners:** SimReady / Path C
- **Supersedes:** N/A
- **Related:** `docs/exec-plans/geometry-gen-mvp.md`, `docs/strategy/mecagent-gap-and-drift-2026-05-26.md` (rank 5 + contrarian "do it constrained"), `BACKLOG.md` (S1 `geometry-gen-mvp`).

## Context

The MecAgent JD's first bullet is *geometry generation*. SimReady today is analysis-only. To close that gap, the LLM must turn a natural-language request into a runnable part. There are two reasonable architectures:

- **A — JSON DSL.** The LLM emits a Pydantic-validated `PartSpec` via a tool call. A trusted, repo-owned executor (`simready.gen.build.build_shape`) maps it to pythonOCC primitives (`BRepPrimAPI_MakeBox`, `BRepAlgoAPI_Cut`, …). No LLM-emitted code is ever exec'd.
- **B — Constrained codegen.** The LLM emits Python source over an allowlisted subset of pythonOCC. The host process exec's it inside an AST allowlist + restricted globals, ideally also inside a subprocess sandbox.

The strategy doc's contrarian note explicitly says: *"a half-working text→STEP loop that emits garbage parts is worse than no geometry generation — interviewer sees broken output live. Mitigation: constrain the LLM to the primitive+boolean grammar … do it constrained, not open-ended B-rep generation."* (`mecagent-gap-and-drift-2026-05-26.md` §5.)

## Decision

**Adopt A.** The LLM emits a typed `PartSpec` via the `build_part` tool. A trusted Python executor consumes that spec.

## Why A wins, for *this* grammar

The candidate grammar is exactly the vocab of `scripts/generate_parametric_steps.py`: `box`, `cyl`, `fuse`, `cut`, `translate`. That is **two primitives, two booleans, one transform** — five tokens. There is no Python expression a codegen-loop could write that a 4-op discriminated-union DSL cannot.

Given that, A dominates B on every axis we care about:

| Axis | A (DSL) | B (codegen) |
|---|---|---|
| Sandbox-escape attack surface | 0 (no exec) | non-zero (AST allowlist holes, restricted-globals escapes) |
| Schema validation | Pydantic at the JSON boundary | a custom AST walker we have to write and maintain |
| Test surface | unit-test the spec→shape map | unit-test the spec→shape map **and** the AST allowlist **and** the restricted exec **and** the failure modes of all three |
| Diagnosis when something breaks | exact spec is the LLM's tool-call payload | code string, plus AST trace, plus exec trace |
| Mapping to existing agent architecture | identical to `analyze_geometry`/`suggest_fixes` (structured tool call) | new exec primitive that doesn't fit the existing pattern |
| Demo / interview story | "typed DSL with contracts → trusted executor → BRepSAGE validates" | "sandboxed exec of LLM-emitted Python" (risk-taking for show) |

The only argument for B was *narrative*: "I built a codegen loop" sounds more impressive than "I built a tool-call schema." That argument loses to the contrarian warning above: if the codegen-loop ever emits garbage during a live interview, the show is over.

## Consequences

- Adding ops to v1 (e.g. rotate, sphere, fillet) is a Pydantic schema edit + an executor branch + a test. Bounded scope per addition.
- The persistent record of what the LLM generated is the spec JSON, which is small and diffable. Useful as conversation transcript artefact.
- We forfeit the ability to demo "the LLM wrote this Python." A `view-as-code` deterministic pretty-printer over the executed spec can fill that gap without re-introducing exec — explicitly deferred to a follow-up.
- If a future surface needs e.g. arbitrary parametric loops, we revisit B at that time. v1's tiny grammar does not need them; the LLM does the parameterization in its head and emits each unrolled step.

## Alternatives considered

- **C — Hybrid (A exec + read-only pretty-printed source artefact).** Cute, but the printer is an extra component that must not drift from the executor. A `view-as-code` toggle is enough for the interview optics; explicit follow-up.
- **B with subprocess-only sandbox, no AST allowlist.** Still requires hardening (resource limits, no network, no FS write outside tempdir), still leaves Python expression injection inside the subprocess. Same end state with more moving parts.
