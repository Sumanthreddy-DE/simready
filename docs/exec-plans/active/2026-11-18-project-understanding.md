# Project-local Understand-Anything and SimReady walkthrough

**Status:** done
**Last verified:** 2026-11-18

**Goal:** Download Understand-Anything only for SimReady and provide an accurate beginner's map of its structure, achievements, and direction.
**Architecture:** Use a local upstream checkout under `.opencode/`, project-scoped skills, and `.ua/` output. Trace main's working application and inspect the separate SP1 worktree without changing it.
**Tech stack:** Existing Node 22, project-local package tooling, Understand-Anything, Python source inspection.
**Spec:** User request in this session; explicit approval for `.opencode/` and `.ua/`, local and untracked.

## Constraints and review focus
- Keep download, dependency/cache writes, skills, and generated graph inside this repository. Never run the upstream global installer or enable auto-update hooks.
- Preserve existing work and branches; no commits, pushes, or paid model calls.
- Distinguish code on main from SP1-only code, measured results from plans, and geometry checks from actual meshing/FEA.
- Review graph references and viewer response; label any deliberately scoped analysis.

## Task 1: Project-local tool
- [x] Download upstream to `.opencode/understand-anything`; record its commit.
- [x] Register upstream skills at project scope and install/build only the required local tooling.
- [x] Exclude `.opencode/` and `.ua/` with `.git/info/exclude`; verify scope and restart requirements.

## Task 2: Source-grounded map
- [x] Inspect application entry points, analysis, generation, copilot, ML, research scripts, and SP1 worktree.
- [x] Generate a navigable map and ordered beginner's tour with source-grounded descriptions.
- [x] Record a walkthrough in existing `docs/impl/`, including branch boundaries and evidence links.

## Task 3: Verification and explanation
- [x] Validate graph structure and source paths, and smoke-check the local viewer if build tooling permits.
- [x] Explain the project in plain language: purpose, input/output paths, accomplishments, caveats, next milestones, and reading order.
- [x] Mark this plan done with verification evidence and disclose any incomplete tool features.

## Execution record

- Upstream 2.9.8 at `bb70fdb0489f8839ce55bf99dae0125ea067f712`. Node 22 already installed; Corepack/pnpm download, cache, store and dependencies kept under `.opencode/`.
- Dependency resolution/install succeeded; root prepare expected global `pnpm` and failed. Explicit `corepack pnpm --filter @understand-anything/core build` and dashboard build passed. No global pnpm shim was installed.
- Ruling: use upstream deterministic scanner, Python AST import/definition extraction and curated explanations/tour instead of the full multi-agent skill. The user wants an understandable onboarding view; the standing rules prohibit unrequested subagents. Cost: this is a scoped map, not upstream full semantic/call analysis or an incremental baseline. Scope disclosed in the guide and session.
- Ruling: keep SP1 code outside the main graph and explain it in the guide, because it lives on another branch/worktree. Cost: SP1 files are not clickable in this main-root viewer.
- Kept the ledger in this plan and local scratch in the approved `.ua/` rather than establishing another top-level workspace convention. No application code edits or project test-suite rerun were necessary.
- Scanner: 73 files. Graph: 280 nodes, 288 edges, 7 layers, 8 tour stops. Verified 50 SP1 concepts / 37 in vocabulary from actual JSONL.
- `node .ua/verify-onboarding.mjs`: PASS — upstream schema, all source paths, edge/layer/tour references, local skills path, dashboard HTML/data/source/lesson endpoints, missing-token rejection, and invalid-schema negative control.
- Dashboard running at loopback port 5173; tokenized URL in `.ua/dashboard.log`. No installed browser/Playwright available for visual inspection; HTTP/structural checks do not claim visual sign-off.
- Final self-review: source order and three-head model checked against implementation; measured versus planned results and branch boundaries explicit; guide links checked against disk. No subagent review or model API calls.
- Deliverable: `docs/impl/project-walkthrough.md`. Tool output excluded locally; guide and this plan left untracked for user review. No commit or push.
- Save Lite follow-up: another session published SP1 while this session was active. Corrected the guide to the new STATE record before committing; graph remains the older snapshot and needs refresh. Dedicated-key laptop SSH tunnel supplied after publickey rejection; user success unverified. Save Lite commits supersede the earlier untracked/no-commit statement.
