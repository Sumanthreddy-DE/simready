# SimReady workspace organization — proposal and Claude Code handoff

> Handoff update, 2026-10-21: both reports have now been preserved in the original `Mech/SimReady/docs/validation/`. Read the local copies; the temporary clone is no longer required. Statements below about reports existing only in the fresh clone describe their original drafting location. No workspace consolidation has occurred. Git advanced during the session: `sp1-bench` was `22c5a16` at save time after the fresh-clone audit backlog item was added elsewhere; recheck ancestry before acting on earlier snapshot SHAs.

**Status:** proposed — no cleanup authorized or performed  
**Last verified:** 2026-10-21  
**Scope:** the two folders under `C:\Users\suman\Desktop\Docs\Job\Projects\Mech`  
**Companion:** `hiring-engineer-readme-audit.md` in this directory

## User decisions

- Only `SimReady` and `SimReady-gencad` are in scope for consolidation.
- No other agent is currently working in either folder (user confirmed).
- Prefer one everyday SimReady workspace; additional worktrees only when necessary.
- This session may inspect and write suggestions, not move/delete files, switch branches, or perform cleanup.
- This report is deliberately saved in the separate fresh clone beside the audit. It is not installed in the original repository.

## Recommendation

Use `Mech/SimReady` as the canonical everyday workspace, normally on `main`. Preserve `sp1-bench` as a paused branch. Retire the linked `SimReady-gencad` worktree only after preserving and verifying all unique local artifacts. Keep the fresh clone as an acceptance-test checkout until the demo fixes are verified.

Do not merge unfinished SP1 work into main merely to simplify the folder tree. Do not delete `SimReady-gencad` through Explorer or move its entire directory into Archive: it is a registered Git worktree with shared repository metadata.

The problem is not primarily the source-code directory layout. It is unclear workspace ownership, distributed local assets, and contradictory live documentation. A broad source-code rearrangement would add path/import breakage without solving those problems.

## Verified current map

| Location | Role and Git state | Important local contents |
|---|---|---|
| `Mech/SimReady` | Main repository; `sp1-bench` at `2ff45dc`; tracked/untracked working tree clean | `.env`, training datasets and labels, real-CAD samples, generated artifacts, chat-SFT adapter, local planning state |
| `Mech/SimReady-gencad` | Registered linked worktree; `gencad` at `91247b0` | Untracked vision adapter and ZIP; ignored GenCAD caches and private `.local` notes |
| `Desktop/simready-fresh` | Separate clone used for onboarding audit | The two handoff reports; not the daily development workspace |

At inspection, local `main` and `gencad` both pointed to `91247b0`; `git rev-list --left-right --count main...gencad` returned `0 0`. Remote-tracking refs also pointed there, but no fetch was performed: this is not a claim that the server is current.

`git diff --stat main...sp1-bench` reports eight files, 390 insertions and one deletion: benchmark schema/loader, concepts, tests, plan changes, and ignore rules. Preserve that branch independently of worktree retirement.

## Local assets that must be preserved before retirement

### In SimReady-gencad

| Path | Disposition proposed | Verification needed |
|---|---|---|
| `qwen_lora_adapter/qwen_lora_adapter/` | Consolidate under an approved, model-specific directory inside the main workspace's existing `weights/` | Read adapter configuration, identify base model/task, hash source and destination; never overwrite chat adapter |
| `qwen_lora_adapter-20261007T064434Z-1-001.zip` | Preserve original download in an approved local-only Archive location after extraction comparison | Verify ZIP contents against extracted files; do not infer duplication from names |
| `data/gencad/gt_hundred.json` | Preserve under main workspace `data/gencad/` | Check collision, hash, and script path expectations |
| `data/gencad/test-00000-of-00001.parquet` | Preserve as reference dataset cache | Record origin/version and hash |
| `data/gencad/mecagent_metrics/` | Preserve metric source/version | Record revision/hash used in published evaluation |
| `data/gencad/scaled_generated_steps/` | Preserve until reproducibility and regeneration are established | Record scale convention and corresponding run |
| `.local/LESSONS.md` and `.local/dlab_report_2026-10-06/` | Preserve as private local material, outside published docs | Agree destination and ignore coverage before moving; review old workflow advice |

The `.local/LESSONS.md` explicitly states that it exists only in the GenCAD worktree. Its old Git workflow advice describes pushing a side branch to main; that should not become the new everyday workflow by accident.

### In SimReady

Keep these in place during consolidation:

- `weights/qlora/`: chat-SFT adapters, checkpoints, ZIPs, loss plot and train/validation traces. This is a different task from the GenCAD vision adapter; do not conflate them.
- `data/labels*`, `data/parametric*`: training/evaluation inputs, including v1 and v2 variants. Different versions may support different published results.
- `data/gen_eval/`: local raw generation evidence missing from the fresh clone.
- `tests/data/grabcad/`, `tests/data/real_eval/`: local real-CAD evaluation inputs.
- `data/fea_docs/`, `data/fea_docs_index.json`: local RAG sources/index.
- `.superpowers/`: SP1 local progress; inspect and preserve resume information before retiring any metadata.
- `.env`, `.claude/`, `docs/jobs/`: local configuration/private material. Do not copy into public reports or read credential values as part of cleanup.

This inventory is directory-level, not an exhaustive hash/size audit. No claim of safe duplicate deletion is made.

## Proposed target layout

Use the existing top-level layout. New model subfolders or private-note destinations below are proposals requiring approval before creation.

```text
Mech/
  SimReady/                      everyday workspace; main when idle
    simready/                    application and model code
    ui/                          Streamlit entry points
    scripts/                     data, training, evaluation, demo utilities
    tests/                       tests and committed fixtures
    notebooks/                   training/evaluation notebooks
    weights/                     checkpoint assets; distinguish chat vs vision adapters
    data/                        local input caches and generated working data
    docs/
      adr/                       durable decisions
      impl/                      implementation and setup references
      validation/                experiment evidence and reproduction instructions
      exec-plans/active/         active or explicitly paused plans
      exec-plans/completed/      completed implementation plans
      strategy/                  strategy records, explicitly current or historical
    Archive/                     superseded material, indexed; not live dependencies
    README.md                    public setup/demo/claims
    STATE.md                     concise current focus, branch, next action
    BACKLOG.md                   open work; compact completed history
    CONTEXT.md                   current vocabulary and domain semantics
    SESSION-END.md               handoff and synchronization checks
```

`SimReady-gencad` disappears from the everyday layout only after preservation and explicit approval of worktree retirement. Retaining/deleting the branch is a separate decision; no need to delete it during consolidation.

## What is stale or unclear now

| Location | Observed problem | Proposed action |
|---|---|---|
| `STATE.md` resume section | Launch in main folder, edit another folder because of memory routing | Replace after consolidation with one launch/edit location; verify harness routing separately |
| `BACKLOG.md` opening | Current-looking July triage includes “NEVER sent” and “not yet sent” while October update says application sent | Keep current truth at top; clearly isolate historical snapshots |
| `BACKLOG.md` completed sections | Multiple “Done this session” sections spanning months | Compress/index completed history; preserve issue IDs and commits |
| `BACKLOG.md` `finish-or-relabel-finetune` | Still asks to recover loss numbers that STATE and finetune results say were recovered | Verify primary results, remove completed subtasks, leave real remaining eval work |
| `CONTEXT.md` | Three tools, two-head description, empty RAG corpus, 160-test environment statement and old application timing | Reconcile with live code and current evidence; remove volatile test counts from glossary |
| `STATE.md` | Mixes historical 202-test and later 227-test summaries | Date/version historical counts or replace with test-command pointer; do not invent a new count |
| SP1 implementation plan | `Status: active` while STATE/BACKLOG say paused | Mark paused with accurate resume checkpoint; retain branch and plan |
| `Archive/README.md` | “Current plan” points at old non-completed path; live status/session pointers use old memory locations | Point current status to repo STATE/BACKLOG; confirm harness-specific paths separately |
| `README.md` and metrics | GNN table does not match cited current records | Handle via companion audit; organizing folders alone does not fix evidence drift |
| `.local/LESSONS.md` | Contains prior multi-worktree/branch workaround | Label historical or replace only after new workflow is verified |

These findings establish that the setup is **not fully up to date**. They do not establish every file is stale; a full link/reference and script-path sweep remains necessary during implementation.

## Archive candidates versus material to keep live

### Candidates after content/reference checks

- Historical triage narratives and long completed backlog sections: move to the existing archive structure or compress with links, retaining decisions and commit references.
- Original adapter ZIPs: archive only after extraction/hash comparison and confirming a recoverable canonical adapter.
- Superseded session/strategy instructions: archive or explicitly mark historical only after preserving active decisions and checking incoming references.
- Old renders, healed exports and generated demo parts: review by purpose/run ownership before retention decisions. File age is not enough.

### Do not archive merely because old

- SP1 plans and code: paused, not abandoned.
- v1/v2 training labels, checkpoints and metric records: may be required to reproduce historical claims.
- Raw GenCAD and generation evaluation records: evidence, not generic clutter.
- Committed fixtures, ADRs and completed plans with useful provenance.
- Existing `Archive/gencad-colab-download-2026-10-07/`: already intentionally archived; its index says the canonical results are in `docs/validation/gencad/`. Reverify before any further duplicate action.

### Low-value clutter

`.worktrees/` and `docs/planning/` in the main workspace were empty. They do not justify a major cleanup. `__pycache__/` and `.pytest_cache/` are generated caches, not historical documents; exclude them from navigation rather than filling Archive with them. No cache deletion is authorized by this proposal.

## Documentation ownership to prevent recurrence

1. README owns public installation/demo commands and high-level verified results.
2. STATE owns current focus, workspace/branch, next action and blockers; keep it short.
3. BACKLOG owns open issue status; avoid another parallel roadmap in its preamble.
4. CONTEXT owns vocabulary and stable domain meaning, not test totals or application dates.
5. Validation docs own experiment-specific datasets, checkpoint identity, commands and raw-output links.
6. Archive index owns historical-material navigation, not live instructions.

Propose one compact workspace/artifact map under existing `docs/impl/`, linked from STATE and README. It should list each local artifact's task, canonical path, tracked/ignored status, provenance, and recovery command. Do not duplicate its full contents across documents.

## Suggested implementation sequence — not executed

1. Re-read both reports and refresh Git/worktree status. Confirm no concurrent agent session.
2. Inventory ignored and untracked files in both workspaces. Present a source/destination/size/hash manifest and collision report. Do not expose secrets.
3. Obtain explicit approval for new subdirectory conventions and each move/retirement batch.
4. Preserve local GenCAD assets in approved locations in the main workspace. Verify hashes, ZIP contents, ignore coverage, and script references. Retain source copies until verification and user approval.
5. Preserve `sp1-bench` unchanged. Switch the canonical workspace to `main` only after clean-state checks and approval. Keep work branches available for later sequential use.
6. Retire the linked worktree through Git only after its local files are accounted for. Do not force removal to bypass untracked/ignored assets. Follow the project's folder-move/harness registry procedure if applicable; user performs folder moves under the standing policy.
7. Reconcile live docs and archive approved historical material with an updated index and repaired links. No broad code-directory redesign.
8. Address companion audit defects on a dedicated branch in the canonical workspace. Run fresh-clone acceptance checks afterward.

Remote currency was not checked in this proposal. Before any future integration decision, fetch with approval as appropriate and inspect ancestry; do not assume cached remote refs are fresh.

## Acceptance criteria

- One unambiguous everyday launch/edit path: `Mech/SimReady`.
- Paused SP1 work remains recoverable on its branch, with a correct resume checkpoint.
- Every unique GenCAD local asset has a verified destination and provenance; no private files accidentally tracked.
- Worktree registration matches actual folders after any approved retirement.
- Current instructions no longer direct users/agents to a retired worktree.
- Current vs historical claims are explicitly distinguished; README results map to specific experiments.
- A newcomer can identify code, inputs, generated outputs, model weights, evidence and archives without reading a long backlog history.
- Fresh-clone demo failures are fixed and retested; local caches are not used to conceal missing setup instructions.

## Prompt to give Claude Code

Read both reports in `C:\Users\suman\Desktop\simready-fresh\docs\validation\`:

- `hiring-engineer-readme-audit.md`
- `simready-workspace-organization-proposal.md`

The target project is `C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady`; `SimReady-gencad` is its linked worktree. The user wants one everyday workspace, temporary worktrees only when needed, and preservation of paused SP1 work and all unique local assets.

Start read-only. Verify the reports against current disk/Git state, inspect ignored as well as untracked assets, and present a concrete migration manifest and proposed document changes. Do not move/delete files, switch branches, remove worktrees, change harness configuration, or start implementing fixes until the user approves that batch. Do not treat this proposal as permission to delete anything. Keep private artifacts private and do not read credential values.

After approval, implement the agreed consolidation and documentation reconciliation, then the README/demo fixes from the first report. Use fresh execution evidence for every completion claim and report remaining unverified claims separately. The two reports are handoffs in the fresh clone, not yet canonical documents in the original repo; ask before copying them into the target project.
