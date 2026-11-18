# SimReady Backlog

Living list of open issues, deferred work, and known caveats. Updated each session.

---

## Triage 2026-07-19 — wave plan (current strategic context)

**NEXT SESSION START HERE (2026-10-25):** work in `Mech/SimReady`, branch `main`. Audit remediation integrated (`f1b6e31`, `1433900`): CLI truthfulness, preserved local assets, fresh-clone demos/results and strengthened generation gate done. Start with GenCAD walkthrough examples (idx 400, one truncation failure, idx 5699, idx 4836), then `gencad-stop-problem`, `gencad-strong-baseline`, and Gemma. SP1 stays paused (`sp1-resume`). Original worktree/assets remain; no archive or retirement without explicit approval.

**UPDATE 2026-10-05: application SENT.** Open commitments = the `apply-*` items in S1/S2. Mapping to the documents: `docs/jobs/2026-10-05-application-commitments.md` (local only). History below kept as written.

**HISTORICAL 2026-07-19 — superseded by the 2026-10-05 sent confirmation above:**
Application to MecAgent had not been sent (`v0.4.0-apply` = prep tag; older lines below/in
Archived claiming otherwise were corrected at that time). Goal then: make the project substantial,
then apply. Repo was idle 2026-05-31 → 2026-07-18; this triage restarted it.

**Wave 1 — hygiene (DONE 2026-07-19, see Done this session):** truth sweep (3-head /
4-tool docstrings + `build_part` in system prompt + README scope/counts),
`render.py`→`png_render.py` rename, repo-root path anchoring (gen output + RAG index),
committed seed RAG index (`lookup_standard` now live on fresh clones), CI
(spec-fast job + micromamba full job), this truth pass.

**Wave 2 — substance (next sessions, in order):**
1. ~~`geometry-gen-mvp` v2~~ **DONE 2026-07-19** — dual-model E_grammar eval on NIM:
   GLM 5.2 5/5, Llama-70B 3/5 (Kimi K2.6 blocked by NIM account 404 → S3; all
   "options" keys turned out to be NIM catalog models under one `nvapi-` key, not
   separate providers). See Done this session + `docs/validation/geometry_gen_eval.md`.
2. `analyze-file-occ-hang-per-check` (S2) — demo killer; per-check precheck +
   subprocess isolation at UI entry points.
3. `defect-head-real-cad-augmentation` (S2) — hardest, highest ML value.

**Wave 3 — user-gated / decisions:**
- `finish-or-relabel-finetune` — DECIDED 2026-07-19: RUN one Colab QLoRA collaboratively
  (user + assistant), then stop investing regardless of result.
- `real-eval-set-grow` (S3) — user downloads 20–30 STEPs.
- `gmsh-calibration` (S2) — DECIDED 2026-07-20: deferred to interview prep, off the active backlog.
- **HISTORICAL APPLY DECISION 2026-07-20: GO** — README refreshed + narrative drafted same day. Still unsent as of 2026-08-04; superseded by the confirmed 2026-10-05 application above.
- NIM key: rotated (user confirmed 2026-07-19).
- [x] **S3 · ci-full-suite-promote** — CLOSED same day. First run: env resolved on
  linux-64, 190 passed / 2 failed / 4 skipped in 14.6 s. Both failures were
  `tests/test_copilot_ui.py` demo-step tests asserting on gitignored local data
  (`data/parametric_degraded/`, `tests/data/grabcad/`) — now skip-if-absent.
  `continue-on-error` dropped. *Opened + closed 2026-07-19.*

---

## Strategic Context (wk-3, updated 2026-05-19 — HISTORICAL, superseded by Triage 2026-07-19 above)

**Three critical demo credibility gaps (from contrarian review, end of wk-2):**
1. `lookup_standard` returns `no_index` always — third copilot tool is dead in every live demo. Fix: populate RAG corpus.
2. BRepSAGE real-CAD recall is ~0.23. UI gives no warning. Engineers get silently unreliable ML scores on real parts (>200 faces). Fix: ML confidence banner.
3. Text-only fix suggestions are useless to engineers in NX/SolidWorks. Fix: auto-heal + return STEP download.
4. `check_self_intersection` silently skips above 150 faces — most important check is invisible on production geometry. Fix: surface skip warning explicitly.

**Gaps vs JD (MecAgent ML/AI Founding Engineer):**

| JD Requirement | SimReady State | Gap |
|---|---|---|
| Geometry generation | Not built | Hard gap — analysis only |
| Tool orchestration | 3 tools, multi-turn | Thin — LLM is mostly a prose wrapper |
| GNN / embeddings | BRepSAGE trained, real-CAD recall 0.23 | Recall gap on non-parametric geometry |
| Model fine-tune pipeline | Not done yet | Clear JD requirement, wk-3 task |
| Production ML + CAD APIs | pythonocc + Streamlit demo | No deployment, no mesher hook |
| Bridge AI + real workflows | Upload → chat → colored PNG | No healed STEP output, no mesher integration |

**Wk-3 priority order (decided 2026-05-19):**
1. Fix broken demo (S1 RAG corpus + S2 self-intersection warning + S2 ML confidence banner) — ~2.5 days
2. Heal + return STEP (S2) — closes biggest ME frustration, demonstrates OCC depth — ~2 days
3. Fine-tune pipeline (exec plan days 15-17) — clear JD requirement — remaining days
4. Param-CAD generation — wk-4 stretch only (risky, deferred)

---

**Severity rubric**
- **S1** — blocker / data loss / broken demo. Fix before next ship.
- **S2** — UX gap, missing polish recruiters will notice, deferred decision.
- **S3** — tech debt, deprecations, low-impact polish, dead code.

**Conventions**
- New issue → append to correct severity section.
- Mention by short slug in commit body (e.g. "Closes: multi-turn-history").
- On close → move to **Done this session** with commit SHA.
- End of session → user sweeps **Done** → **Archived** (one-line compress).
- Last swept: **2026-11-18** (cockpit tags, prompt splits, `gen-streamlit-panel` moved to Parked). Prior sweep 2026-07-20 (wave 3 — apply GO, item A shipped, QLoRA launched).

---

## Open — S1 (blocker / broken demo)

- [ ] **S1 · audit-reports-followup** [later · you] — October audit remediated on `main` (`f1b6e31`, `1433900`); remaining items are gated archive decisions and optional fresh-env/training rebuild checks (`docs/validation/reproduce-results.md`). *(found 2026-10-21; remediated 2026-10-25)*
  Prompt:
    REMEDIATED ON MAIN 2026-10-25 (`f1b6e31`, `1433900`). CLI false-success fixed; 14 approved local files hash-preserved with sources retained; README setup/demo/results and generation gates remediated; full suite: `main` at `6cb1193` collects 238 in a clean clone (255 = the laptop working copy on `fix/audit-remediation`: 249 clean-clone tests + 6 extra GrabCAD cases from 3 gitignored STEPs in `tests/data/grabcad/`; re-collected 2026-11-04); browser chat/build/analyze and tracked-only clean-checkout acceptance verified; strengthened GLM 5.3 gate 5/5. Evidence: `docs/validation/reproduce-results.md`, `generation_gate_2026-10-24.json`, `docs/impl/workspace-artifacts.md`. Worktree decisions done 2026-11-12; archive decisions remain separately gated. Evidence gaps: fresh environment-manager install, full training rebuild, fresh GenCAD inference, additional hosted models; verdict prose can overstate mesh readiness. Do not repeat the completed audit.

- [ ] **S1 · apply-gencad-vlm-track** [week · claude] — Image→CadQuery on `CADCODER/GenCAD-Code`: Qwen2.5-VL-3B done (QLoRA VSR 88/100, IoU 0.256); remaining leg is Gemma-3-4B on Kaggle GPU after Sumanth accepts the Gemma license. *(found 2026-10-04, promoted 2026-10-05)*
  Prompt:
    Branch: `gencad`, cut from `main` (SP1 bench commits stay on `sp1-bench`). Qwen2.5-VL-3B: untuned VSR 0/100 → QLoRA VSR 88/100, IoU_best 0.256 (MecAgent, surface voxels) / 0.563 (filled voxels); 6k training examples, 1 epoch, 3 h 35 min T4. Full record + reproduce steps: `docs/validation/gencad_eval.md`; notebooks `notebooks/gencad_baseline.ipynb`, `notebooks/gencad_train_qwen.ipynb`; adapter on Google Drive (`MyDrive/gencad/qwen_lora_adapter`). Remaining: Gemma-3-4B with the same two notebooks (swap BASE; check Unsloth model id first; run via Kaggle CLI).

---

## Open — S2 (UX gap, polish, deferred decisions)

- [ ] **S2 · fixture-eval-not-reproducible** [later · you] — README's fresh inference command (`scripts/evaluate.py data/labels_fixtures_v2 weights/brepnet.pt`) fails on a clone because `data/labels_fixtures_v2/` is gitignored (9.0 MB, 27 parts). Decide: commit the 27 fixture graphs (check McMaster terms) or state in README that datasets are local. *(found 2026-11-03, VPS fresh-clone test)*
- [ ] **S2 · defect-head-real-cad-augmentation** [later · claude] — Defect head false-positives on 11/11 real McMaster parts (synthetic and 1-part real-negative attempts exhausted); needs a larger independently verified real-CAD dataset plus an interference feature for `self_intersection`. *(found 2026-05-28; updated 2026-10-25)*
  Prompt:
    Non-circular defect head still false-positives on 11/11 analyzed real McMaster parts after combined-v2 retrain (2272 graphs; open_shell 0.571→0.856, real-CAD FP unchanged). Gap is surface-type vocabulary (box/cyl grammar lacks B-splines/cones/tori/revolves). Remaining levers: (a) small hand-labelled real-CAD positive set, (b) clean real parts as negatives in training, (c) grammar extension to revolved/swept surfaces; self_intersection class (0.212) needs an interference feature. 2026-10-25 real-negative attempt FAILED (`experiment/defect-real-clean`, `f39fe93`, `docs/validation/defect_head_real_clean_v1.md`): only 2/12 parts passed inspection; do not tune on one part. See `docs/validation/defect_classifier.md` v2 + `real_eval_v2.md`.
- [ ] **S2 · finish-or-relabel-finetune** [later · you] — Training & loss recovery done (`docs/finetune_results.md`); remaining: export `lora_adapter/` to GGUF q8_0, run gold-set eval once via local `llama-server` (base + LoRA), then close regardless of result. *(found 2026-05-26)*
  Prompt:
    (a) GGUF export from `lora_adapter` (`FastLanguageModel.from_pretrained("<Drive>/lora_adapter", load_in_4bit=True)` then section 9b — original cell assumed model in memory); (b) download GGUF, gold-set eval twice through local llama-server (recipe in `docs/finetune_results.md` — base + LoRA columns), then CLOSE regardless of result per 2026-07-19 run-once decision.
- [ ] **S2 · grabcad-scrape-blocked** [later · claude] — `download_grabcad_samples.py` is blocked by anti-bot walls; downgraded 2026-05-26 because GrabCAD/SimJEB STEPs are now only needed for `real-eval-set-grow`. *(found 2026-05-14)*

---

- [ ] **S2 · sp1-resume** [later · you] — SP1 benchmark Tasks 1–10 and reference-pair headroom done on `sp1-bench`; next is Task 11 hash freeze once `sp1-concepts-proofread` and `vultr-budget` are cleared (`docs/exec-plans/active/2026-10-04-sp1-bench-implementation.md`). *(found 2026-10-05; updated 2026-11-17)*
  Prompt:
    Branch `sp1-bench` (use a separate worktree if another session shares the repo). Completed: Task 1 (`84e7820`), Task 2 review (`e6193ea`..`58a6906`, 37/37 ref specs pass 111/111), Task 3 (`ca9f861`), Task 4 (`5f830db`), Task 5 (`b36c625`, tag `v0.5.0` `5f995ff`), Task 6-code (`a0593c5`) & Task 6-live (`8c37b67`: Vultr `glm-5.3` and `deepseek-v4.1-flash-1017` with substitution guard), Task 7 (`32be790`), Task 8 (`077da0c`), Task 9 (`892d23c`), Task 10 (`d6c4e22`..`a8b902a`: 16-step cap stated in `build_part`, GLM `max_tokens` 16384, smoke pass@1 GLM 83.3% / DeepSeek 91.7%), reference ceiling pair (`63cccc3`, `6bec0f8`: Gemini 94.6% / GPT 95.5%), and `grader-spawn-fail-fast` (`efe3f15`). Next: Task 11 hash freeze after `sp1-concepts-proofread` and `vultr-budget`.
- [ ] **S2 · sp1-concepts-proofread** [week · you] — Proofread `simready/bench/prompts/concepts_v1.jsonl` on `sp1-bench` (realism, engineer ranges vs standard, weak intent checks) before freezing hashes in SP1 Task 11. *(found 2026-11-12)*
  Prompt:
    Pointers in `docs/exec-plans/active/2026-11-12-sp1-task2-review.md` § Point (c): re-read fixed lines c017/c020/c030/c031/c045; weak intent checks c010 (blank plate passes), c023 (any 30 mm block passes), c048 (no gradable check), c047 (axial-hole fake passes; a volume check would separate it); c034 bore 6.6-8.0 vs c044 6H band; c033/c042 intent names a length but has no length check; c030 explicit prompt still uses 10.03/16.035/9.9 (plain 10 x 16 x 10 now passes). Must finish before the hash freeze in Task 11.
- [ ] **S2 · cad-rl-env-ownership** [later · claude] — SimReady items (1)–(4) and infra fix `efe3f15` on `sp1-bench` are complete; approve/tag `v0.5.1` when ready and keep open until `cad-rl-env` Phase B/C delivery finishes (`cad-rl-env/docs/exec-plans/active/2026-11-14-cad-rl-env-design.md`). *(found 2026-11-14)*
  Prompt:
    SimReady owns check types, checker, geometry module, `concepts_v1`, and DSL; `cad-rl-env` owns the Prime Intellect verifiers v1 wrapper, train generator, red-team suite, and Hub packaging (imports SimReady via pinned git tag, never copies checker; reward runs on OCP). Done on `sp1-bench`: (1) OCC/OCP shim + Task 3 (`ca9f861`, `28afebe`), (2) Task 4 (`5f830db`), (3) `pyproject.toml` `simready[bench]` (`c255c60`), (4) `v0.5.0` (`5f995ff`) + infra repair `efe3f15` (proposed `v0.5.1` tag gated on Sumanth's approval; `bench-checker-1.0.0` waits for Task 11 freeze).
- [ ] **S2 · sp1-repair-mode** [later · claude] — Deferred from SP1 (design D6): after single-shot benchmark runs, add an offline 2-retry repair pass starting from logged failed attempts ("feedback loop lifts pass rate X → Y"). *(found 2026-09-25)*
- [ ] **S2 · sp3-base-model-choice** [later · you] — When writing the SP3 spec, decide whether GRPO post-trains text-only Qwen2.5-3B (SP1 prompts) or the GenCAD vision-language model, and whether reward combines IoU with the OCP checker. *(found 2026-10-04, claude-lab session)*
- [ ] **S2 · gencad-iou-metric-note** [later · you] — MecAgent's `best_iou.py` voxelizes surfaces only (`voxelized()` without `.fill()`, verified 2026-10-07: idx 4836 tube 0.010 vs 0.588 filled). Decide call framing: report their metric as headline, filled as second column. *(found 2026-10-07)*
- [ ] **S2 · session-dumps-in-public-history** [threat · you] — Four April 2026 session dumps (`Archive/sessions/2026-04-2*.tmp`) were untracked on `main` (`6e0a938`) but remain readable in public git history. Decide: rewrite history to purge them (coordinating `sp1-bench` and `gencad` rebases) or accept and close. *(found 2026-10-10, Sumanthreddy-DE session)*
- [ ] **S2 · eval-integrity-trial** [later · claude] — Trial the probationary `eval-integrity` Citadel skill on `docs/validation/gencad_eval.md` (+ notebooks + MecAgent `dc94ef8`), verify findings by hand, then decide keep vs delete and log in `claude-lab/LOG.md`. *(found 2026-11-18, claude-lab session)*
  Prompt:
    Run the `eval-integrity` skill (global Citadel skill, on probation since 2026-11-18; ported from oh-my-openagent) on the GenCAD headline in `docs/validation/gencad_eval.md` (Qwen2.5-VL-3B QLoRA VSR 88/100, mean IoU 0.256 on `hundred_subset` vs 0/100 untuned and 1/100 one-shot), giving it that doc, the two notebooks, and MecAgent metric code (`dc94ef8`). Check each finding by hand against the record. Keep if it finds at least one unrecorded real gap or passes with traceable checks; remove (`citadel/harness/skills/eval-integrity/`, re-render) if it only restates the doc. Record verdict here and in claude-lab `LOG.md`.
- [ ] **S2 · attempt-malformed-json-guards** [week · claude] — Port `cad-rl-env`'s pre-build guards (`isinstance(s["op"], Hashable)` in `classify_spec` and `RecursionError` catch in `_as_spec` / `_spec_in_text`) into `simready/bench/attempt.py` on `sp1-bench` before tagging `v0.5.1` so SP1's runner cannot crash on nested JSON or list/dict `"op"` values. *(found 2026-11-18, cad-rl-env session)*

### cad-rl-env handoff verification — 2026-11-17

- **Infrastructure repair committed; dependency publication pending.** The old readiness check missed backend/child faults scoring as model failures. `grader-spawn-fail-fast` is fixed in `efe3f15cf7ce92fd2ad8bc85ef402c28091e8b50` on `sp1-bench`; cad-rl-env must consume that corrected attempt API rather than v0.5.0. User push, version bump and proposed v0.5.1 release remain gated. SP1 official runs and SP2 are not prerequisites for this patch release.
- Fresh VPS OCP verification: **99 passed in 16.11 s** across `test_occ_compat.py` and the bench geometry, checker, reference-spec, attempt, concepts and concepts-file tests. The tested dependency files and tests have no diff between `v0.5.0` and `sp1-bench` at `6d5fb47`. This audit did not repeat the clean-wheel installation check.
- Remote rechecked 2026-11-17: `v0.5.0` peels to `5f995ff07b16afebc4a8e0b4b6b3d123905a8dba`; it contains the classification defects. Proposed replacement dependency tag `v0.5.1` is absent locally/remotely at inspection; creation/publication gated on approval. Keep `simready[bench]`, not stale `[ocp]` / `bench-api-0.1`. `bench-checker-1.0.0` still requires the separate Task 11 proofread/hash/version freeze.
- Packaging merge `c255c60` is already in `sp1-bench`; the packaging worktree is removed. The old delegation card's merge/cleanup commands should not be rerun.
- **User confirmed the cad-rl-env kickoff prompt is running in another session.** That session owns its plan reconciliation, Phase B implementation and eventual Phase C publishing gates. Leave the ownership item open until environment delivery; do not repeat Phase A here.

## Open — S3 (tech debt, deprecations, low-impact polish)

- [ ] **S3 · sp1-dlab-gpt-model-id** [later · model] — `python -m simready.bench smoke --model gpt-6.1-sol` prints `configured id present: False` (`models.list` names `gpt-6-1-sol` while accepting `gpt-6.1-sol`). Before Task 11 freeze, align `model` to `gpt-6-1-sol` and re-smoke, or note the alias in plan Task 6-live. *(found 2026-11-17, SimReady session)*
- [ ] **S3 · laptop-wheel-build-unconfirmed** [later · you] — Re-run `pip wheel --no-deps . -w C:\mm\whl` in the laptop `sr` env (Python 3.10, pythonocc) and record `Successfully built simready` (or the error). *(found 2026-11-16, SimReady session)*
- [ ] **S3 · sp1-review-worktree** [later · you] — `/tmp/simready-sp1-review` is a clean `sp1-bench` worktree in `/tmp` (wiped on VPS reboot). Decide: keep while finishing SP1 or `git worktree remove /tmp/simready-sp1-review`. *(found 2026-11-12)*
- [ ] **S3 · real-eval-set-grow** [later · you] — `n=7` real-CAD parts is too small for a defensible held-out metric; add 20–30 more real STEPs and report defect-head FP-rate (`docs/validation/real_eval.md` §4). *(found 2026-05-28)*
- [ ] **S3 · vultr-budget** [later · you] — Official SP1 run (750 attempts/model) is re-estimated at ~$11 for GLM-5.3 + ~$0.50 for DeepSeek vs $5 recorded on 2026-10-05; check/top up Vultr balance (or lower `k`) before SP1 Task 11. *(found 2026-10-05; updated 2026-11-16)*
- [ ] **S3 · cv-generic-simready-entry** [later · claude] — Fix `Myself/CV/EN/content/resume.json` before the next generic English application so SimReady's GNN bullet does not oversell real-CAD recall. *(found 2026-10-05)*

---

## Parked

- [ ] **S3 · gen-streamlit-panel** [parked · you] — Optional Streamlit panel showing the generation loop step by step; parked because `ui/copilot_app.py` chat already runs prompt → `build_part` → analyze. *(found 2026-11-03, claude-lab review)*

---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session

- [x] **S3 · bench-provider-key-guard** — Merged into `sp1-bench` as `0ea126e` (2026-11-18). Known tool-envelope/spec-root `reason` contamination, including replacement of `steps`, is `infra_error` / `provider_arguments` with null scoring fields; independent model defects remain scored. Regrade preserves provider exclusions while backend infra can recover. Attempt/replay 106 passed; bench 216 passed / 1 deselected (worker verification). Coordinator post-merge full command: 342 passed / 20 failed / 27 skipped / 6 deselected; same 20 failure identities as unchanged base (273 passed). Report on `sp1-bench`: `docs/exec-plans/active/2026-11-18-provider-key-guard-report.md`. Not pushed.

- [x] **S1 · grader-spawn-fail-fast** — Fixed 2026-11-17 in `efe3f15cf7ce92fd2ad8bc85ef402c28091e8b50` (`sp1-bench`, user-approved commit). Missing/broken backend and child startup/exit → `infra_error`; checker/executor bugs → `checker_error`; excluded `partial`/`passed` null. Genuine running timeout F8 and native kernel build failure F4 retained. Atomic mailbox avoids queue partial-frame hangs; children reaped including kill escalation. Runner counts/excludes/retries; replay raises explicit errors. Final bench/OCP/spec check 175 passed / 1 deselected; available full suite same 20 baseline failures, 273 passed; normal collection blocked by missing torch. Exact evidence/limitations: `docs/exec-plans/active/2026-11-17-attempt-infrastructure-errors.md` on SP1. Dependency handoff can pin corrected SHA after user push; new immutable `v0.5.1` version bump/tag/publication awaits approval. Do not move v0.5.0 or claim checker freeze. *(opened S3 2026-11-16; promoted/fixed S1 2026-11-17)*

- [x] **S2 · sp1-typed-tool-schema** — decided 2026-11-17 (user): no typed schema; `build_part`'s `spec` stays a prose grammar (spec D8). Reasons: 0 `F2_schema` in about 300 headroom attempts by the reference pair (the 3/12 failures were DeepSeek, not a reference model, and not valid JSON); a typed schema can be compiled into a decoding grammar by some servers (llama-server believed to, unverified), so the SP3 baseline and the API ceiling would measure different things; schema errors are a reward signal for SP3. Fixed instead: the description now states every `PartSpec` bound (dimensions (0, 1000] mm, radius (0, 500] mm, `at` in [-10000, 10000] mm), generated from `simready/gen/spec.py` constants; `6d5fb47` on `sp1-bench`. New `system_prompt_sha256` `3dd19661...`; D Labs re-smoke passed on both reference models.
- [x] **S2 · sp1-reference-models** — decided 2026-11-17 (user): Gemini-4-Argon + GPT-6.1 Sol on D Labs, as a ceiling pair. Provider fixed the injected `reason` key; re-checked 0/12 repro calls and 0/36 bench attempts. Headroom k=1 over 150 prompts: in-vocab pass@1 Gemini 94.6% [90.1, 98.2], GPT 95.5% [91.9, 99.1], not separable, accepted. Spec D5 and plan Tasks 11-12 updated in `63cccc3`; provider entries `6bec0f8` (`sp1-bench`). D Labs DeepSeek not chosen (about 2.5x fewer tokens than Vultr, 3/12 unparseable).
- [x] **S2 · sp1-task3-bbox-gap** — closed 2026-11-15 on `sp1-bench` (merge of `gpt/sp1-task3-geometry` + `ca9f861`; VPS Orca opencode worker, GPT-6.1 Sol). Task 3 `simready/bench/geometry.py` + 14 tests, written against new `simready/occ_compat.py` (pythonocc first, else pip `cadquery-ocp`; OCP `_s` statics adapted behind pythonocc spelling). `occ_utils.py`, `gen/build.py` and the import block of `validator.py` moved to the shim. Fix: `sorted_extents` uses `brepbndlib.AddOptimal(shape, box, False, False)` (d20 cylinder 20.0, 2 mm plate 2.0; `Add` gave 20.0000002 / 2.0000002); `shape_bounding_box` keeps its gap and now reads `CornerMin`/`CornerMax` (OCP 8 cannot marshal `Bnd_Box.Get()`). Plan + spec deviations 5–6. OCP venv `~/.venvs/simready-ocp` (cadquery-ocp 8.0.1.1): targeted 32 passed; full suite 27 failed / 112 passed → 20 failed / 151 passed, no lost pass. Laptop `sr` env (pythonocc 7.9, Python 3.10) at `28afebe`: the three files 31 passed / 1 skipped (OCP fallback test, no OCP there); the first run caught a test-only `Extent()` call (pythonocc has `Size()`), fixed in `28afebe`.
- [x] **S1 · apply-submit-mecagent-test** — sent 2026-11-15 by email reply to Alexandre Senet (alexandre@mecagent.com) in the 2026-10-05 thread. The hiring site returned Railway 404 "Application not found" on 11-14 and 11-15 (no Wayback copy), so the task was answered as written in `good_luck.ipynb`; page restructured first (`c1ded3a`, `c831b42`). The first email's link was a google.com/url redirect; a follow-up at 10:28 UTC sent the direct link and asked whether the site wanted anything more. Logged in career-ops `applications/005-mecagent/sent-messages.txt`, tracker row 5 and follow-ups (2027-03-15) in `9c75636`. If Senet names extra questions, answer them as a new section in `docs/validation/gencad_eval.md`.
- [x] **S2 · gencad-strong-baseline** — closed 2026-11-15 (`c76b4bf`). One-shot prompted untuned Qwen2.5-VL-3B on `hundred_subset`: VSR 1/100 (idx 1446, IoU 0.027), IoU (invalid=0) 0.0003. 99 rows are the one-shot example's program (train idx 87) with its first `)))` cut to `))`, failing `'(' was never closed`; 2 distinct outputs. So the QLoRA gain is not only format. Scores + hash-only example file in `docs/validation/gencad/`; raw generations local only (`Archive/gencad-oneshot-2026-11-15/`, training program text, no dataset license). Record: `docs/validation/gencad_eval.md` § Prompted baseline.
- [x] **S2 · gencad-stop-problem** — closed 2026-11-12 (merge `b3e3fae`; `e2b3451`, `9b3436d`, VPS opencode GPT). Offline on the committed greedy generations, MecAgent metric `dc94ef8`, positive control reproduced 88/100 (max IoU diff 3.3e-4). R1 trim-to-last-complete-`solid=`: VSR 88 → 100, IoU invalid=0 0.225 → 0.230 (12 recovered parts average 0.038). R2 repeat-stop removed duplicate sketches from 22 valid programs with zero IoU change. Repetition penalty untested (GPU). `docs/validation/gencad_eval.md` § Stop rules.
- [x] **S2 · sp1-resume, Task 2 review** — done 2026-11-12 on `sp1-bench` (`e6193ea`, `bd50c0d`, `6933318`, `58a6906`; pushed through `6933318`, `58a6906` not yet pushed). Fixes: c020 engineer gland hole 16.1-16.3 (Lapp T21 16.3 −0.2), c017 source line, c031 thickness 1.95-2.0 (DIN 988); point (b) applied to c030/c045. `.gitattributes` LF for `*.jsonl`/`*.sha256`. Bench tests 11 passed before and after. The parent item stays open (proofread, Task 3 onward).
- [x] **S3 · kimi-k26-nim-404** — closed 2026-11-12: K2.6 dropped by the owner; replaced by `kimi-k3` on D Labs (existing `OPENAI_*` key). v2.3 gate **4/5** (thin_plate fails); every prompt lost a call to an injected `reason` key in tool arguments, the 2026-10-05 D Labs signature, so the leg is labelled provider-noisy. `docs/validation/geometry_gen_eval.md` v2.4.
- [x] **S3 · gen-eval-latency** — closed 2026-11-12 (merge `ee3f1db`; `4b72ae5`, `a1e7aa7`, VPS opencode GPT). Offline timing (`scripts/time_gen_eval.py`, 5 gate specs × 3 rounds, no LLM): build ~1.2 s, `analyze_file_safe` ~9.0 s (≥3.9 s of it is child start-up + imports), PNG 0.03 s, heal 0.02 s. Local work is ~20 s of a 40–143 s prompt; the rest is LLM round-trips. Render/heal slim mode not worth it (~0.06 s); verifier now skips the healed STEP (`heal_step=False`). Only remaining lever is a persistent analyze worker (≤ ~8 s/prompt, would rework the hang guard) — not pursued. Record: `docs/exec-plans/completed/2026-11-12-gen-eval-latency.md`.
- [x] **S3 · copilot-tools-midfile-importorskip** — closed 2026-11-11 (opencode VPS run, merged): OCC test moved to `tests/test_copilot_tools_occ.py`; the 21 pure tests now run without pythonocc.
- [x] **S3 · base-vs-env-marker-split** — closed 2026-11-04 (merge `00de34d`, VPS opencode GPT-6.1 Sol). `occ` marker: `pytest -m "occ and not live_llm"` / `-m "not occ and not live_llm"` (README). Laptop review: occ 104 passed, not-occ 134 passed in sr; with every OCC import blocked, not-occ 134 passed / 0 failed. `test_copilot_tools.py` stays whole-module occ (its importorskip sits mid-file, as before).
- [x] **S3 · test-count-claim-255** — closed 2026-11-04 (merge `00de34d`). 255 = laptop working copy on `fix/audit-remediation`: 249 clean (238 main + 11 SP1 bench) + 6 GrabCAD cases from gitignored STEPs. STATE.md and the S1 line corrected. Quote test counts from a clean clone.
- [x] **S1 · geometry-gen-mvp** — closed 2026-11-03 (merge `a79596f`; `bbd3d85`, README `9bdf8bf`, handoff `30f1f65`). v3: `python scripts/simready_gen.py "<prompt>" [--json] [--model] [--timeout]` → copilot → `build_part` → final STEP (`select_final_build`, no fallback) → `analyze_generated_part` on that exact file; exit 0 = OCC-valid + analysed (rating in `analysis_status`, e.g. a thin plate is NotReady), 1 = failure, 2 = no key. 8 offline tests; VPS live 6/6 via DLab gpt-6-1-sol (~50 s each); laptop live `--json` via Vultr glm-5.3: exit 0, 7 faces, ReviewRecommended 88.7, stdout one JSON object. Review fix: the msvcrt buffered-output test is skipped on Windows (UCRT), `a79596f` parent. Laptop suite 254 passed / 1 skipped / 5 deselected. Streamlit gen panel not built — the copilot chat already generates; see S3 `gen-streamlit-panel`.
- [x] **S1 · apply-call-walkthrough** — closed 2026-11-03 (merge `83ae012`). Last part done: `docs/validation/gencad_examples.md`, four cases with measured bbox/face counts and shaded paired renders (idx 400 IoU 1.0 but generated plate 2× the reference size — IoU normalises scale; idx 350 truncated at 1825 tokens, 3 vs 8 sketches; idx 5699 IoU .830/.893 yet self-intersecting — its 4 holes cut into the corner rounds and the centre hole is missing; idx 4836 tube shell .010 vs filled .588). No dataset images or reference programs committed (GenCAD-Code declares no license). Built on the VPS by opencode GPT-6.1 Sol; first renders were flat silhouettes (brief said one grey) — shading fixed on review (`1ea06ca`), images checked on the laptop. Walkthrough package now complete → next step is `apply-submit-mecagent-test`.
- [x] **S2 · readme-linux-commands**, **S3 · brepnet-dead-import**, **S3 · graph-extractor-dup-face-iter**, **S3 · report-schema-unused** — closed 2026-11-03 (merge `5c17d6a`; `149c181`, `27c9bb0`, `fe28d3d`, `939079c`, handoff `8b48f36`). README: Bash build→analyze block, `cp .env.example .env`, `part.step` → `tests/data/smoke_box.step`, both `PYTHONPATH` forms (laptop re-ran the Bash build line: OK). Dead import deleted. `graph_extractor._iter_faces` now wraps `occ_utils.iter_faces` + parity test. `report_schema.json` kept and validated against a real smoke-box report (no schema change needed; positive control: a report missing `status` is rejected). Laptop 247 passed / 5 deselected. Built on the VPS in worktree `SimReady-readme-s3` by opencode GPT-6.1 Sol, in parallel with `fix/fresh-install-deps`.
- [x] **S1 · fresh-install-copilot-crash** — closed 2026-11-03 (merge `57a105e`; `66382a6`, handoff `3b118ca`). `requirements.txt` `openai>=1.40,<3`; a second fresh Linux env resolved openai 2.54.0 + httpx 0.28.1 (no brotli bound needed) and both README copilot commands answered via DLab gpt-6-1-sol, the plate prompt calling `build_part` → STEP → analyze. VPS suite 229 passed / 10 skipped / 5 deselected. Laptop env (openai 2.36.0) inside the bound: 245 passed / 5 deselected, `pip check` clean. Note: BACKLOG/STATE record "255 passed" for 2026-10-25, but `main` collects 250 (245 + 5 deselected) today — recorded figure not re-derived here.
- [x] **S2 · cli-json-extra-document** — closed 2026-11-03 as **not a SimReady bug** (`226f67f`). `{"log_history": []}` is printed by `micromamba run` 2.10.0 itself when the command line ends in `--json` (libmamba `output.cpp` `print_json_output`; even `micromamba run … python -c pass --json`). The fresh-clone test used `micromamba run` only because the brief forbade shell activation; README users activate the env and never hit it. Kept: a real-subprocess test that `analyze --json` stdout parses as one document.
- [x] **S2 · gpt-fresh-clone-test** — closed 2026-11-03. VPS run, opencode GPT-6.1 Sol `--pure`, `main` @ `9242a7d`, self-contained `~/simready-fresh`. Setup works on Linux (env 71 s + pip 52 s, import smoke OK); analyze, `gen.build` → analyze, HTML/healed export, `test_gen_verify` 10 passed, both Streamlit apps serve. Blockers filed as S1 `fresh-install-copilot-crash`, S2 `fixture-eval-not-reproducible`, S2 `cli-json-extra-document`, S2 `readme-linux-commands`. Report: claude-lab `docs/exec-plans/completed/2026-11-03-simready-fresh-clone-report.md`.
- [x] **S3 · gencad-results-duplicate** — closed 2026-10-13. Untracked `gencad_results/` in the `Mech/SimReady` checkout was the raw Colab download of the first GenCAD eval; verified identical to `docs/validation/gencad/` (JSON equal, 88/88 STEPs equal ignoring CRLF), moved to `Archive/gencad-colab-download-2026-10-07/` (local only, `.git/info/exclude`), indexed in `Archive/README.md`. *(found 2026-10-13, SimReady session)*
- [x] **S2 · branch-state-divergence** — closed 2026-10-13. `sp1-bench` carried STATE.md / BACKLOG.md from 2026-10-05 ("cherry-pick to main pending") while `main` had the 10-07 and 10-13 versions, and the SessionStart dashboard reads whatever branch is checked out in `Mech/SimReady`. Fixed by merging `main` into `sp1-bench` (STATE, BACKLOG, README taken from `main`; the two `sp1-bench`-only backlog edits `ab6229a` and `01ad739` re-applied) and fast-forwarding `gencad` to `main`. Rule from here: STATE.md and BACKLOG.md are edited on `main` (or merged into it the same session); side branches merge `main` before their next session. *(found 2026-10-13, SimReady session)*
- [x] **S2 · apply-readme-cv-alignment** — closed 2026-10-13. Models part `b30e212`; CV part 2026-10-05 (Myself `5f144eb` + `9429da8`: EN and DE CVs name GLM 5.3 / DeepSeek V4.1 Flash and credit the real-part failure to the defect head); README part `58fe9b5` on `main` (Direction section, GenCAD results, SP1-SP3 roadmap).
- [x] **S1 · apply-readme-on-main** — closed 2026-10-13. `main` carries the gen-eval v2.2 README (`bc564f7`) and the GenCAD work (pushed as `gencad:main`); README rewritten on `main` the same day: Direction section, GenCAD results, SP1-SP3 roadmap. Rule stays: every later README/eval change made on a side branch reaches `main` before it is linked.
- [x] **S1 · apply-gencad-checker-bridge** — closed 2026-10-07 (this commit). Ran locally (sr env), not on Colab: STEPs exported in Colab, scaled to 100 mm (checker thresholds are mm; GenCAD parts ~1.5 units), `analyze_file_safe` on 88 generated + 88 reference parts. Generated mean 86.9 vs reference 84.9 (simpler parts, not better parts); model-introduced defects: 1 invalid solid, 3 self-intersections, 6 thin walls; idx 5699 IoU 0.89 filled but self-intersecting. `scripts/gencad_checker_bridge.py`, `docs/validation/gencad/checker_*.jsonl`. Original text: — Score every GenCAD-generated part with SimReady's own checker as a third measure next to VSR and IoU. Today the checker runs on STEP (`analyze_file_safe`), not CadQuery: CadQuery program → execute → export STEP → `analyze_file_safe` → checker verdict/score column. Decide where it runs (pythonOCC on Colab, or export STEPs and score locally). Couples with `sp3-base-model-choice` (same scorer can become the reward). *Opened 2026-10-05.*
- [x] **S1 · apply-gen-eval-glm53-deepseek** — closed 2026-10-05, `b3f7cc4` (eval doc v2.2) + `b30e212` (README table). GLM 5.3 **5/5**, DeepSeek V4.1 Flash **5/5**, both on Vultr (`api.vultrinference.com/v1`), one run each, no retries; specs hand-checked (holes centred). D Labs not used: it corrupts tool-call arguments for every model (provider facts in memory `reference_llm-providers.md`). **Llama leg impossible: NIM retired `meta/llama-3.3-70b-instruct` on 2026-08-26 (410 Gone).** Finding: the 5-prompt gate is saturated (all models 5/5) — SP1 is the discriminating benchmark. Copilot default in `.env` moved to Vultr `glm-5.3` (old NIM key kept as `NIM_API_KEY`); demo smoke-tested (build → analyze → verdict, 21 s).

---

## Done this session (2026-05-28)

- **real-cad-eval-set** (S2) — 12 real McMaster STEPs (brackets / flanges / bearings / housings) placed in `tests/data/real_eval/`. `scripts/eval_real_cad.py` hardened: cheap `count_shapes(shape, TopAbs_FACE)` precheck, `--max-faces 800` skip-list, smallest-first sort, and a spawn-subprocess + `.terminate()` hard timeout per part (`--analyze-timeout 60`) — required because the first run hung 12 h on a 58-face cast flange (OCC C++ in `analyze_file`; Python thread timeouts cannot kill it). Held-out result: 7/12 analyzed, 1 skipped (854 f), 4 timeout-killed (flange / bearing NURBS pathology); **7/7 analyzed parts false-positive on the defect head** (median conf > 0.95); `rule_face_mean = 0.0` on every part but `ml_aggregate ∈ [0.30, 0.59]` — quantifies the OOD gap previously inferred from the leaky synthetic val. Full interpretation: `docs/validation/real_eval.md`. *(SHA: `849449a`)*

## Done this session (2026-05-26 → 27)

- **env-example-secret-leak** (S2) — replaced live `nvapi-` key in `.env.example:6` with `<your-api-key>` placeholder (regex rewrite, secret never echoed). **NOTE: key remains in git history → user must rotate it on the NVIDIA dashboard; this commit does not rewrite history.** *(SHA: `90b90cb`)*
- **evaluate-py-defect-metric** (S2) — `scripts/evaluate.py` now passes `batch=batch.batch` (graph-level defect head pools per graph) and reports defect accuracy + per-class acc when the dataset has `graph_label` (guarded for label-less sets). Parity with `train.py`. Smoke: combined 1100-set `defect_acc=0.739` (clean 0.84 / open_shell 0.565 / sliver 1.0 / self_int 0.40). *(SHA: `90b90cb`)*
- **grabcad-doc-stale** (S3) — refreshed `docs/validation/grabcad.md` to the 3-head leakage-free checkpoint (`a29e150`): banner + model-dependent cells (Overall 37.5/36.6/61.0, ML agg 0.37-0.45, latency) from `weights/metrics.json`; rule/geometry cells unchanged; honest recall framing (0.487 leakage-free vs leaky 0.870); dropped Combined-mean column. *(SHA: `90b90cb`)*

- **break-circular-label** (S2) — added a non-circular graph-level **defect-classification head** trained on injected `defect_tags` (not the rule layer). `auto_label.py` now reads `.tags.json` → `graph_label`; `model.py` gains `defect_head` (global-mean-pool → 4-class); `dataset.py` loads `graph_label`; `train.py` adds CE loss + per-class defect accuracy. Wired into `brepnet.py` inference (`predicted_defect`/`defect_confidence`/`defect_probs`). *(SHA: `a29e150`)*
- **degraded-to-200-retrain** (S2) — generated 600 degraded (200 each: open_shell/sliver_face/self_intersection), labeled 1100 combined, retrained on a **source-grouped (leakage-free) split**. Headline non-circular metric: **defect acc 0.756** (n_val=205); per-class clean 0.87 / sliver 1.0 / open_shell 0.571 / self_int 0.371. Old circular head on the honest split drops to acc 0.848 / recall 0.487 (was 0.975/0.870 on the leaky random split). Results: `docs/validation/defect_classifier.md`. *(SHA: `a29e150`)*
- **commit-tracked-weights** (S2) — `.gitignore` now tracks `weights/metrics.json` + `eval_fixtures.json` (+ existing brepnet.pt/meta negations); wrote slim honest `weights/metrics.json`; committed the checkpoint so a cloner gets a model + numbers. *(SHA: `a29e150`)*
- **167/167 tests green** (sr env; +7 in `tests/test_defect_head.py`). No regressions across the touched files.
- **readme-polish** (S2) + **brepnet-naming-fix** (S3) — full honest README rewrite for the recruiter lens: leads with capabilities (agent / GNN / eval discipline), 3-head model described accurately, **BRepSAGE/GraphSAGE naming fixed** (no more "BRepNet"), circular-refinement vs non-circular-defect caveat surfaced, Results tables w/ provenance + leakage-free-split framing, Mermaid arch diagram, scope=analysis-only, latency, test count 160→**167**. Changed every claim the code didn't support. *(SHA: this session's docs commit — see `git log`.)*
- **self-demo / repo-not-empty** — refreshed `weights/eval_fixtures.json` against the new 3-head checkpoint (acc 0.725 / recall 0.692, up from 0.23); `docs/sample_output/smoke_box.{json,html}` (checkpoint-backed CLI bundle, zero-setup proof); `docs/img/streamlit-analysis.png` + reproducible `scripts/ui_screenshots.py` (Playwright driver). Closes the "weights + metrics gitignored → clone is empty" gap (strategy doc pointer #1). *(SHA: docs commit.)*

## Done (2026-05-24)

- **trace-gen-restart** (S2) — resumed 1368 → **1455 traces** (8B, NIM; 45 lost to 429s, resume-safe, exit 0). Ample for 3B QLoRA.
- **gold-eval-incomplete** (S2) — full **70B gold baseline n=50, errors=0** (`tool_call_exact 0.760`, `partial 0.920`, `tool_order 0.780`, `format 0.780`, `theme 0.678`). Added `--request-delay`/`--max-retries`/`--initial-backoff` to `eval_finetune.py` to survive NIM 429s; purged 3 stale partial gold blocks from `finetune_results.md`, filled the summary table's Llama-70B column.
- **brepbndlib-deprecation** (S3) — `brepbndlib_Add` → `brepbndlib.Add` static in `scripts/generate_degraded_steps.py`; verified no DeprecationWarning under `-W error`.
- **chore** — `logs/` added to `.gitignore`; refreshed `path-c-4week.md` (wk-3 run ticks, day-15/18-run-1 done) and `project_simready.md` memory; **reconciled apply status** — confirmed applied 2026-05-18 (`v0.4.0-apply`), corrected a mid-session mis-conclusion that it hadn't been sent.
- *(SHA: this session's commit — see `git log`.)*

---

## Archived (older sweeps, compressed)

- **2026-07-20 · wave 3 — apply GO + orphan-step rule + QLoRA launch** (3 items) — see commits `8304c1b..d94cc25`. gen-spec-orphan-step-rule closed (`8304c1b`: `_check_orphans` validator + tool-description rule + `parallel_tool_calls=False` NIM fix; live Llama 3/5→5/5; suite 220→227; verdict-prose hallucination persists — gate scores artifacts, not prose); gmsh-calibration deferred to interview prep (recipe: `gmsh part.step -3 -clmax 2` on 10-15 tests/data STEPs, correlate quality w/ score); adr-backlog closed (`d94cc25`: ADRs 0002-0004 — SDK choice, RAG-lite sizing, stateless agent). Same session: **APPLY DECISION = GO** (README wave-2/3 refresh + `docs/strategy/mecagent-apply-narrative-2026-07-20.md`, `d88ec31`); QLoRA Colab run launched after live debugging (notebook fixes `1732f0a`/`614e632`/`cd992cf`/`93248c5`); GGUF+llama-server eval recipe (`f1e489d`).
- **2026-07-19 · wave 2 — gen v2 + OCC-hang fix + augmentation attempt** (3 items) — see commits `b62fc9e..2e04391` (+`a331efb` Stream D). geometry-gen v2 E_grammar live eval (GLM 5.2 5/5, Llama-70B 3/5 dropped-boolean; Kimi K2.6 NIM-404 → S3); analyze-file-occ-hang CLOSED (BOPAlgo-on-B-spline culprit, GIL-inert watchdogs proven, freeform precheck + `analyze_file_safe` subprocess worker at all entry points, real-eval coverage 7→11/12); defect-head augmentation attempt = honest negative (combined-v2 2272 graphs, val 0.686 harder-val, real-CAD FP still 11/11 — item stays Open w/ findings). Suite 202→220 sr; pytest.ini default-deselects live_llm. Docs: `geometry_gen_eval.md`, `occ_hang_diagnosis.md`, `defect_classifier.md` v2, `real_eval_v2.md`.
- **2026-07-19 · wave 1 — hygiene batch** (6 items) — see commits `1d5a80a..b5d4070`. Truth sweep (build_part into system prompt, README, docstrings, counts), render→png_render rename, repo-root path anchoring, committed seed RAG index (lookup_standard live on clones), CI (spec-fast + micromamba full suite, both green), never-applied correction + wave-plan triage.
- **2026-05-31 · geometry-gen-mvp v1** — `fa581f0`. Typed Pydantic DSL (`simready/gen/spec.py`) + trusted executor w/ spawn-subprocess hang protection (`simready/gen/build.py`) + `build_part` tool in `simready/copilot/tools.py`; ADR 0001 locks DSL-over-codegen; defect head advisory-only; 31 new tests, 198/198 sr. v2 (live-LLM E_grammar) + v3 (CLI/Streamlit) remain Open under the S1 stamp.

- **2026-05-21 · wk-3 days 15-19 scaffolding** — `4e74ff0` (7 files / 1670 ins): `synth_tool_traces.py`, `prep_finetune_dataset.py`, `finetune_copilot.ipynb` (Colab T4 QLoRA on Qwen2.5-3B), `eval_finetune.py` (6 metrics), `finetune_results.md` template, gitignore `data/fine_tune/`. `trace-format-rot` closed by design. `project_api-key-todo` memory opened. 160/160 tests, no prod-code changes.
- **2026-05-19→20 · contrarian-review demo fixes** — `71ccacf` + `dd45eef`. Closed the 4 demo-credibility gaps: `fea-rag-corpus-empty` (rag.py API-rename + OpenBLAS-crash fixes, index rebuilt), `heal-return-step` (auto ShapeFix/ShapeUpgrade → healed-STEP download), `ml-confidence-banner` (unreliable-score banner when `face_count>200`), `self-intersection-skip-warning` (explicit "skipped N faces" finding above 150).

- **2026-05-18 · apply-timeline-tight** — CORRECTED 2026-07-19: application was NEVER sent; `v0.4.0-apply` (`34a93e7`) tagged the prep snapshot only. (The 2026-05-24 "reconciliation" that concluded it was sent is also wrong.) Apply deferred until project substantial — user decision 2026-07-19.
- **2026-05-13 · Phase 2A bug-fix sweep** (5 items) — see commits `b689b71`..`ec4f33a`. SelfIntersection false-positive, face index 0/1 mismatch, ML weights-loaded lying, GrabCAD manifold hang guard, rule_face_count rename.
- **2026-05-14 · Path C wk-1 ship** (6 days of work) — see commits `7212e52`..`d8fcc1f`. Copilot stack, 3 tools, RAG-lite, multi-turn loop, terminal UI, degraded-STEP generator.
- **2026-05-16 · Wk-1 Q1/Q6/Q8 resolved** — light real-LLM smoke (`563ab6c`) validated LLM loop end-to-end on NIM Llama. No tool_choice gotcha. Slim summary respected. Day-10 sub-decisions D1=b, D2=a, D3=mock-then-smoke locked.
- **2026-05-17 · Path C wk-2 day 10 ship** (4 items) — `056a746`..`69539ef`. Streamlit chat UI + dropdown dedupe, sidebar score badge, multi-turn history via `AgentResponse.messages` round-trip, Verdict-with-score format. Real-LLM smoke gained a turn-2 follow-up (10/10 NIM checks).
- **2026-05-17 · Path C wk-2 day 11 ship** (7 items) — `636d140`..`c3df6c0`. Static colored-face PNG via OCC tess + PIL painter's-algo (replaces deferred pyvista; matplotlib also broken in sr OCC env on Win); `check_thin_solid` detector + drop broken `zero_length_edge` synth; STEP file uploader + 5MB warn; typed `_classify_agent_exception` chips (RateLimit/Timeout/ConnError/Auth/BadRequest); `[synth]`/`[real]` dropdown grouping; per-session JSON persist under `data/copilot_sessions/`. 160/160 tests in sr env (+15 from session start).
- **2026-05-17 · Memory + archive cleanup sweep** — see commits `32fd451..5a917d4`. Phase 1/2/3 plans + designs + brainstorming + deep-research + stale memory + old `~/.claude/session-data/` .tmp files moved into `Archive/{phase-1,phase-2,phase-3,brainstorming,memory,sessions}/` (move-only, never deleted). Added `CONTEXT.md` (FEA/BRep/copilot domain glossary + avoid-terms + example dialogue) and `SESSION-END.md` (7-step manual end-of-session checklist). Memory dir refreshed: `project_simready.md` rewritten to current Path-C-wk2-day11 state, `project_simready-roadmap.md` collapsed to pointer-only (real plan lives at `docs/exec-plans/completed/path-c-4week.md`), `project_open-questions-wk2.md` moved to `Archive/memory/`. Global `~/.claude/CLAUDE.md` extended w/ BACKLOG/SESSION-END/Archive harness rules, memory-vs-repo duplication rule, /save-session-path gotcha, and two-trigger new-project harness check (session-start + memory-folder creation). `~/.claude/templates/new-project/` seeded w/ BACKLOG.md + SESSION-END.md + Archive/README.md so `new-project-init.sh` scaffolds them. Opened: `adr-backlog` (S3, write 2-3 ADRs for Path C decisions, defer wk-3).
