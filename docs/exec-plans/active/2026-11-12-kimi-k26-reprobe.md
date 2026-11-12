# kimi-k26-nim-404 — re-probe Kimi K2.6 on NVIDIA NIM — task brief

**Status:** active
**Last verified:** 2026-11-12

BACKLOG S3 `kimi-k26-nim-404`. Written for an agent on the VPS in opencode. Claude reviews;
you stop after the last commit.

## Background

`moonshotai/kimi-k2.6` is listed in the account's NIM `/v1/models` catalog, but on 2026-07-19
every call (plain completion included, 3 retries) returned
`404 Function '23d4f03a-…' not found for account`. GLM 5.2 replaced it as the second eval leg.
The key is an NVIDIA `nvapi-` key stored as `KIMI_API_KEY`, not a Moonshot key.

## Environment

```bash
PY=/home/sumanth/simready-fresh/mamba/root/envs/simready-fix/bin/python
cd /home/sumanth/projects/Mech/SimReady
```

No installs, no code changes in the repo, no worktree needed.

## Secrets

Never read, print or `cat` `.env`. Never echo a key, not even a prefix. Load keys only with
`dotenv_values(".env").get("KIMI_API_KEY")` inside Python and print booleans or HTTP status codes.

## Steps

1. Key check: print only `bool(dotenv_values(".env").get("KIMI_API_KEY"))`. If `False`, write
   "blocked: no KIMI_API_KEY in the VPS .env" into `## Result`, commit it, stop.
2. Probe script in `/tmp/kimi-probe/probe.py` (outside the repo), base URL
   `https://integrate.api.nvidia.com/v1`, the `openai` client already in the env:
   - a. `GET /v1/models` — is `moonshotai/kimi-k2.6` listed?
   - b. Plain chat completion, `max_tokens` 16, prompt "Reply with OK." — status / first error line.
   - c. One completion with a single trivial tool defined and `tool_choice="auto"` — status, and
     whether a tool call came back with JSON-parseable arguments.
   Run each call twice, 30 s apart. Print a table: call, attempt, status, short result.
3. If a, b and c all succeed: run the live gate once, 30-minute timeout:
   `OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1 OPENAI_MODEL=moonshotai/kimi-k2.6 OPENAI_API_KEY_VAR=KIMI_API_KEY $PY -m pytest tests/test_gen_e2e.py -m live_llm -v`.
   The explicit env vars win over `.env` (which points at D Labs). Report per prompt:
   pass/fail, wall seconds, and the record it appended to `data/gen_eval/` (gitignored, do not commit).
4. If anything in step 2 still fails: no live run. Record the exact error text (first line,
   function id redacted to its first 8 characters) and the date.
5. Fill `## Result` with the step 2 table, step 3 or 4 outcome, and one line: "awake" or
   "still 404". Set `**Status:** done`. Commit only this file:
   `docs: record kimi-k2.6 NIM re-probe`. Stop.

## Rules

- Never edit `BACKLOG.md`, `STATE.md`, `README.md`, `docs/validation/`, code or tests.
  Claude updates the eval doc and backlog from your Result.
- No `/save-session`. No push. No AI attribution in commits.

## Result

_(agent fills this in)_
