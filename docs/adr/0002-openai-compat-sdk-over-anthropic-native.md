# ADR 0002 — Copilot: OpenAI-Compatible SDK over Anthropic-Native

- **Status:** Accepted (retro-documented 2026-07-20; decision made 2026-05-13, Path C wk-1)
- **Related:** `simready/copilot/agent.py`, `docs/exec-plans/completed/path-c-4week.md`

## Context

The copilot agent needs one LLM client. Anthropic's native SDK has richer tool-use
ergonomics, but every serving stack this project actually touches — NVIDIA NIM,
OpenRouter, local Ollama, llama-server, vLLM — speaks the OpenAI chat-completions
dialect. The project runs on NIM free-tier keys and must survive provider churn
(models appearing/disappearing per account, see kimi-k2.6 404s).

## Decision

Use the `openai` SDK exclusively; the provider is a single `OPENAI_BASE_URL` env swap.
No provider-specific branches in agent code.

## Consequences

- Provider portability is one env var — the same agent ran against NIM Llama-70B,
  GLM 5.2, and (planned) a local llama-server GGUF with zero code change. This is what
  made the dual-model gen eval and the local fine-tune eval cheap.
- We inherit the dialect's least common denominator: per-provider quirks surface at
  runtime, not compile time. Two live examples: Llama on NIM ignores
  `tool_choice="none"`, and NIM's Llama template 500s on multi-tool_call assistant
  messages (fixed via `parallel_tool_calls=False`, commit `8304c1b`). These are handled
  once in the agent, not papered over with per-provider branches.
- We forfeit Anthropic-native features (e.g. server-side tool orchestration). Nothing
  in the current tool loop needs them; revisit only if a feature demands it.
