# ADR 0004 — Multi-Turn: Stateless Agent + `AgentResponse.messages` Round-Trip

- **Status:** Accepted (retro-documented 2026-07-20; decision made 2026-05-17, wk-2 day 10)
- **Related:** `simready/copilot/agent.py`, `ui/copilot_app.py`

## Context

Multi-turn chat needs conversation state to live somewhere. Options: a stateful agent
object holding history, a server-side session store, or a stateless agent where the
caller owns history. The primary UI is Streamlit, which re-runs the whole script on
every interaction — any in-object state is rebuilt from scratch each rerun.

## Decision

`CopilotAgent.run()` is stateless per call: it accepts prior messages, returns an
`AgentResponse` carrying the full updated `messages` list (system, user, assistant,
tool turns), and the caller round-trips that list into the next call. Streamlit keeps
it in `st.session_state`; the CLI keeps it in a local variable; per-session JSON
persistence is a straight dump of the same list.

## Consequences

- One history representation serves chat UI, CLI, JSON session persistence, and the
  fine-tune trace format — traces are literally saved message lists, which is why the
  QLoRA dataset prep is a filter+format pass, not a transformation layer.
- Fits Streamlit's rerun model with no hidden state; a rerun replays from
  `session_state` and the agent neither knows nor cares.
- Cost: history grows per turn and rides every request. Mitigated by the token-budgeted
  tool-result truncation (drop per-face blobs → ML internals → cap findings, in that
  order). A summarization pass is the escape hatch if conversations ever get long
  enough to blow the context window; not needed at current demo lengths.
