# SimReady — Session-End Checklist

Read this when wrapping up any working session. Keeps `BACKLOG.md`, the memory dir, and git history aligned. Run top-to-bottom; skip steps that genuinely don't apply.

---

## 1. BACKLOG sweep

In `BACKLOG.md`:

- [ ] For every item closed this session, check it has a commit SHA (or SHA range) recorded.
- [ ] Move closed items from **`## Done this session`** to **`## Archived`** as one-line compressed entries.
  - Compression pattern: `**YYYY-MM-DD · short topic** (N items) — see commits SHA1..SHAN. one-line scope summary.`
- [ ] Make sure `## Done this session` ends the session empty.
- [ ] Update the **`Last swept:`** date line at the top to today.
- [ ] If any new issues were discovered (and not fixed), add them to the right S1/S2/S3 section with an `*Opened YYYY-MM-DD.*` tag.

## 2. Memory: live one-line state

In `~/.claude/projects/C--Users-suman-Desktop-Docs-Job-Projects-Mech-SimReady/memory/project_simready-roadmap.md`:

- [ ] Update the **`## One-line state`** paragraph: which day shipped, which day is next, current commit-ahead count vs `origin/main`.

That's the only memory file that needs touching most sessions. Skip the others unless material project state changed (new env, new top-level module, test count jumped). When in doubt, leave them.

## 3. Memory: bigger refresh (rare — only when state actually shifted)

Touch `project_simready.md` ONLY if one of these is true:

- A new top-level module / package landed (e.g. new `simready/<thing>/` folder).
- Test count moved by more than a handful (note the new total).
- Env changed (new conda env, new Python version, new core dep).
- A phase boundary just crossed (e.g. wk-2 → wk-3).

If none apply: do not touch it. Stale claims are worse than missing ones.

## 4. Plan progress

In `docs/exec-plans/path-c-4week.md`:

- [ ] Tick the right `[ ]` → `[x]` for any day that shipped.
- [ ] Update the **`Status:`** line at the top if the wk-by-wk position moved.

## 5. Commit + push

- [ ] One end-of-session commit: `chore: end-of-session sweep — Day N archived, plan progress recorded` (or similar).
- [ ] `git push origin main`. Hook may block; if so, resolve and push again. **Do not skip hooks.**

## 6. Save session

- [ ] Run `/save-session` (or invoke the `save-session` skill).
  Writes to `~/.claude/projects/C--Users-suman-Desktop-Docs-Job-Projects-Mech-SimReady/sessions/YYYY-MM-DD-<topic>-session.tmp`.
  NOT to `~/.claude/session-data/` — that path is from an older skill version; ignore.

## 7. Optional: open-questions for next session

If anything came up that needs a decision from you (the user) before next session:

- [ ] Append it as a one-line bullet to the bottom of `project_simready-roadmap.md` under a **`## Pending for next session`** heading (create if missing). Keep it short — full discussion belongs in `BACKLOG.md` once the issue is concrete.

---

## What this file is NOT

- Not a hook. Nothing enforces it. Manual discipline.
- Not loaded by any tool. You (or me, when prompted "wrap up the session") read it.
- Not exhaustive. Trust judgement on whether a step adds value this session.

## How to invoke

End of session, say: **"wrap up the session"** or **"end-of-session sweep, follow `SESSION-END.md`"**. I'll walk the checklist with you.
