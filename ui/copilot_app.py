"""Streamlit chat UI for SimReady Copilot (Path C day 10).

Per-message single-turn agent run (no cross-message history yet — multi-turn
context refactor planned for day 11). Each user message spawns a fresh
``CopilotAgent.run`` that may internally chain multiple tool calls.

Run:
    PYTHONPATH=. streamlit run ui/copilot_app.py

Requires ``OPENAI_API_KEY`` (and optionally ``OPENAI_BASE_URL``,
``OPENAI_MODEL``) in the environment or a ``.env`` file at the repo root.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover — dotenv is optional
    pass

from simready.copilot.agent import AgentResponse, CopilotAgent


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIRS = (
    REPO_ROOT / "data" / "parametric_degraded",
    REPO_ROOT / "tests" / "data" / "grabcad",
)
TOOL_PREVIEW_CHAR_LIMIT = 2000


st.set_page_config(page_title="SimReady Copilot", page_icon="🤖", layout="wide")
st.title("SimReady Copilot")
st.caption(
    "Tool-augmented assistant for FEA pre-processing. "
    "Ask about a CAD file and the agent will run SimReady checks, rank fixes, "
    "and cite FEA standards."
)


def _list_demo_steps() -> list[Path]:
    """Return STEP files under DEMO_DIRS, deduped (Windows globs are
    case-insensitive so ``*.step`` and ``*.STEP`` would otherwise both match)."""
    seen: set[Path] = set()
    out: list[Path] = []
    for d in DEMO_DIRS:
        if not d.exists():
            continue
        for p in sorted(list(d.glob("*.step")) + list(d.glob("*.STEP"))):
            resolved = p.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            out.append(p)
    return out


def _init_state() -> None:
    if "chat" not in st.session_state:
        st.session_state.chat = []  # display history: list[dict]
    if "_pending_user_msg" not in st.session_state:
        st.session_state._pending_user_msg = None
    if "_llm_history" not in st.session_state:
        # LLM-side message list (system + user + assistant + tool messages),
        # passed back into ``CopilotAgent.run(..., history=...)`` on each turn
        # so the agent has full conversational context.
        st.session_state._llm_history = []
    if "last_analysis" not in st.session_state:
        # Most-recent ``analyze_geometry`` tool result; surfaced in sidebar.
        st.session_state.last_analysis = None


def _make_agent() -> CopilotAgent | None:
    if not os.environ.get("OPENAI_API_KEY"):
        st.error(
            "OPENAI_API_KEY not set. Create a `.env` from `.env.example` "
            "with OPENAI_API_KEY, OPENAI_BASE_URL, and OPENAI_MODEL, then "
            "restart Streamlit."
        )
        return None
    try:
        return CopilotAgent()
    except (RuntimeError, ImportError) as exc:
        st.error(f"Agent init failed: {type(exc).__name__}: {exc}")
        return None


def _render_tool_events(events: list[dict[str, Any]]) -> None:
    """Render tool_call + tool_result pairs as expandable panels."""
    calls = [e for e in events if e.get("type") == "tool_call"]
    results = [e for e in events if e.get("type") == "tool_result"]
    if not calls:
        return
    with st.expander(f"Tool activity ({len(calls)} call{'s' if len(calls) != 1 else ''})"):
        for call, result in zip(calls, results):
            st.markdown(f"**`{call['name']}`** — iteration {call['iteration']}")
            args = call.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    pass
            st.code(json.dumps(args, indent=2, default=str), language="json")
            payload = result.get("result", {})
            text = json.dumps(payload, indent=2, default=str)
            if len(text) > TOOL_PREVIEW_CHAR_LIMIT:
                text = text[:TOOL_PREVIEW_CHAR_LIMIT] + "\n...[truncated]"
            st.code(text, language="json")


def _render_citations(events: list[dict[str, Any]]) -> None:
    """Surface lookup_standard hits as a citation footer, if any."""
    hits: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("type") != "tool_result" or ev.get("name") != "lookup_standard":
            continue
        payload = ev.get("result", {})
        for h in payload.get("hits", []) or []:
            hits.append(h)
    if not hits:
        return
    with st.expander(f"Citations ({len(hits)})"):
        for h in hits:
            src = h.get("source") or h.get("filename") or "unknown"
            page = h.get("page")
            score = h.get("score")
            head = f"**{src}**" + (f" — p.{page}" if page is not None else "")
            if score is not None:
                head += f"  (similarity {score:.2f})"
            st.markdown(head)
            snippet = h.get("text") or h.get("snippet") or ""
            if snippet:
                st.markdown(f"> {snippet[:600]}")


def _render_chat() -> None:
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] != "assistant":
                continue
            events = msg.get("events") or []
            _render_tool_events(events)
            _render_citations(events)
            meta = []
            if msg.get("iterations"):
                meta.append(f"{msg['iterations']} iter")
            usage = msg.get("usage") or {}
            if usage.get("total_tokens"):
                meta.append(f"{usage['total_tokens']} tokens")
            if meta:
                st.caption(" · ".join(meta))


def _run_agent_turn(user_text: str) -> None:
    """Run one CopilotAgent.run for the given user message, append the result.

    Passes the prior LLM message history back in so the agent sees the full
    conversation. Captures the most-recent ``analyze_geometry`` tool result
    into ``st.session_state.last_analysis`` for the sidebar score badge.
    """
    agent = _make_agent()
    if agent is None:
        st.session_state.chat.append({
            "role": "assistant",
            "content": "Cannot run: OPENAI_API_KEY missing.",
            "events": [],
        })
        return

    events: list[dict[str, Any]] = []

    def on_event(ev: dict[str, Any]) -> None:
        events.append(ev)
        if ev.get("type") == "tool_result" and ev.get("name") == "analyze_geometry":
            result = ev.get("result") or {}
            if isinstance(result, dict) and "error" not in result:
                st.session_state.last_analysis = result

    history = st.session_state._llm_history or None
    with st.spinner(f"Calling {agent.model}…"):
        try:
            response: AgentResponse = agent.run(
                user_text, on_event=on_event, history=history
            )
        except Exception as exc:  # surface any provider/transport error
            st.session_state.chat.append({
                "role": "assistant",
                "content": f"Agent failed: `{type(exc).__name__}: {exc}`",
                "events": events,
            })
            return

    st.session_state._llm_history = response.messages
    text = response.final_text or "_(agent returned no final text — hit max_iterations)_"
    st.session_state.chat.append({
        "role": "assistant",
        "content": text,
        "events": events,
        "usage": response.usage,
        "iterations": response.iterations,
    })


_init_state()


STATUS_COLOR = {
    "SimulationReady": "#22c55e",
    "ReviewRecommended": "#eab308",
    "NeedsAttention": "#f97316",
    "NotReady": "#ef4444",
    "InvalidInput": "#ef4444",
}


def _render_last_analysis(slot) -> None:
    """Render a compact score/status/findings block from the most recent
    ``analyze_geometry`` tool result."""
    a = st.session_state.last_analysis
    if not a:
        slot.caption("No analysis yet — pick a STEP from the dropdown.")
        return
    score = (a.get("score") or {}).get("overall")
    status = a.get("status", "Unknown")
    geom = a.get("geometry") or {}
    sev = a.get("severity_counts") or {}
    color = STATUS_COLOR.get(status, "#9ca3af")
    slot.markdown(
        f"<div style='font-weight:700;color:{color};'>{status}</div>",
        unsafe_allow_html=True,
    )
    if isinstance(score, (int, float)):
        slot.metric("Score", f"{score:.1f}/100")
    cols = slot.columns(3)
    cols[0].metric("Faces", geom.get("face_count", "—"))
    cols[1].metric("Edges", geom.get("edge_count", "—"))
    cols[2].metric("Findings", a.get("findings_total", "—"))
    sev_parts = [f"{k[0]}:{sev.get(k, 0)}" for k in ("Critical", "Major", "Minor", "Info")]
    slot.caption("Severity: " + " · ".join(sev_parts))
    complexity = a.get("complexity") or {}
    if complexity:
        tier = complexity.get("tier") or complexity.get("label") or complexity
        slot.caption(f"Complexity: {tier}")


# ─────────────────── Sidebar ───────────────────
with st.sidebar:
    st.header("Last analysis")
    _render_last_analysis(st.sidebar)
    st.divider()

    st.header("Demo CAD")
    demo_steps = _list_demo_steps()
    if demo_steps:
        labels = [str(p.relative_to(REPO_ROOT)).replace("\\", "/") for p in demo_steps]
        pick_idx = st.selectbox(
            "Pick a sample STEP",
            options=range(len(labels)),
            format_func=lambda i: labels[i],
            key="demo_pick",
        )
        if st.button("Analyze selected STEP", key="use_step_btn"):
            picked = str(demo_steps[pick_idx])
            st.session_state._pending_user_msg = (
                f"Analyze {picked} and tell me what's wrong + how to fix it."
            )
            st.rerun()
    else:
        st.info(
            "No demo STEPs found. Run "
            "`python scripts/generate_degraded_steps.py "
            "--input data/parametric --output data/parametric_degraded --max-inputs 5`."
        )

    st.divider()
    st.header("Config")
    st.text(f"Model:    {os.environ.get('OPENAI_MODEL', '(unset)')}")
    st.text(f"Base URL: {os.environ.get('OPENAI_BASE_URL', '(unset)')}")
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    st.text(f"API key:  {'set' if has_key else 'MISSING'}")
    if not has_key:
        st.warning("Set OPENAI_API_KEY in `.env` to talk to a real LLM.")

    st.divider()
    if st.button("Clear chat", type="secondary"):
        st.session_state.chat = []
        st.session_state._pending_user_msg = None
        st.session_state._llm_history = []
        st.session_state.last_analysis = None
        st.rerun()


# ─────────────────── Main pane ───────────────────
if not st.session_state.chat:
    st.info(
        "Try the sidebar **Analyze selected STEP** button, or type a question like "
        "`What's wrong with data/parametric_degraded/bracket_with_hole_0000__open_shell.step?`"
    )

_render_chat()

# Handle a sidebar-queued user message (must process after _render_chat so the
# user bubble shows in the same rerun pass).
if st.session_state._pending_user_msg:
    pending = st.session_state._pending_user_msg
    st.session_state._pending_user_msg = None
    st.session_state.chat.append({"role": "user", "content": pending})
    with st.chat_message("user"):
        st.markdown(pending)
    _run_agent_turn(pending)
    st.rerun()

user_input = st.chat_input("Ask SimReady about a CAD file…")
if user_input:
    st.session_state.chat.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    _run_agent_turn(user_input)
    st.rerun()
