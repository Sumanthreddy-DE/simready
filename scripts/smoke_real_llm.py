"""Day-4 / Day-11 smoke (light): real LLM + canned analyze_file payload.

Validates against the real provider (NIM Llama 3.3 70B per env):
  * tool-call argument shape on a multi-tool chain
  * Verdict / Issues / Fixes / Citations format
  * severity_counts surfaced correctly
  * lookup_standard graceful fallback on no_index (RAG corpus empty)
  * max_iterations not silently hit
  * Day-11 add: multi-turn history — turn-2 follow-up answers without
    re-pasting the STEP path (validates AgentResponse.messages round-trip).

OCC pipeline is stubbed so we can run without a conda env. Tool *result*
is canned but loop, prompts, retries, truncation are real.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Stub analyze_file_safe BEFORE the agent imports it — module-global swap.
import simready.copilot.tools as tools

CANNED_REPORT: dict[str, Any] = {
    "status": "ReviewRecommended",
    "complexity": "moderate",
    "score": {"overall": 68.5, "label": "Yellow"},
    "geometry": {
        "face_count": 142,
        "edge_count": 384,
        "solid_count": 1,
        "bounding_box": [-25.0, -15.0, -5.0, 25.0, 15.0, 12.0],
    },
    "bodies": [{"face_count": 142, "label": "Solid_1"}],
    "findings": [
        {
            "check": "SelfIntersection",
            "severity": "Critical",
            "detail": "Body intersects itself near rib at y=-10.",
            "suggestion": "Remodel rib; current geometry will fail meshing.",
        },
        {
            "check": "OpenBoundaries",
            "severity": "Major",
            "detail": "3 free edges on top flange — shell not stitched.",
            "suggestion": "Run ShapeUpgrade_UnifySameDomain to stitch.",
        },
        {
            "check": "ShortEdges",
            "severity": "Minor",
            "detail": "7 sub-mm edges near M4 hole fillets (tol 0.05 mm).",
            "suggestion": "Merge edges below tol before meshing.",
        },
    ],
    "ml": {
        "available": True,
        "weights_loaded": True,
        "score_source": "BRepSAGE_v0",
        "model_name": "brep_sage_2026_05_10",
    },
    "elapsed_seconds": 2.4,
    "validation": {"is_valid": True, "errors": []},
}


def _stub_analyze_file(path: str, timeout: int = 120) -> dict[str, Any]:
    return CANNED_REPORT


tools.analyze_file_safe = _stub_analyze_file

from simready.copilot.agent import CopilotAgent  # noqa: E402  (after monkeypatch)


def _on_event(ev: dict[str, Any]) -> None:
    t = ev.get("type", "")
    if t == "iteration_start":
        print(f"--- iter {ev['iteration']} ---", flush=True)
    elif t == "tool_call":
        args_raw = ev.get("arguments", "")
        args_short = args_raw if len(args_raw) <= 240 else args_raw[:240] + "...[truncated]"
        print(f"  [TOOL CALL] {ev['name']}({args_short})", flush=True)
    elif t == "tool_result":
        rs = json.dumps(ev["result"], default=str)
        head = rs if len(rs) <= 220 else rs[:220] + "...[truncated]"
        print(f"  [TOOL RESULT] {len(rs)} chars: {head}", flush=True)
    elif t == "final_text":
        print(f"  [FINAL] iters={ev['iterations']} usage={ev.get('usage')}", flush=True)
    elif t == "max_iterations":
        print(f"  [MAX ITERS HIT] iters={ev['iterations']}", flush=True)


def _print_metadata(label: str, resp: Any) -> None:
    print(f"\n=== {label} FINAL TEXT ===")
    print(resp.final_text or "(empty — bug)")
    print(f"\n=== {label} METADATA ===")
    print(f"stop_reason   : {resp.stop_reason}")
    print(f"iterations    : {resp.iterations}")
    print(f"tool_calls    : {[tc['name'] for tc in resp.tool_calls]}")
    print(f"usage         : {resp.usage}")


def main() -> int:
    step_path = Path("tests/data/grabcad/manifold_complex.STEP")
    if not step_path.exists():
        print(f"ERR: {step_path} missing.", file=sys.stderr)
        return 2

    agent = CopilotAgent()
    print(f"Provider base_url: {os.environ.get('OPENAI_BASE_URL', '(default OpenAI)')}")
    print(f"Model: {agent.model}")
    print(f"STEP: {step_path}\n")

    # ----- Turn 1: full triage (unchanged from day-4 light smoke) -----
    turn1_q = (
        f"What manufacturing issues does {step_path.as_posix()} have, "
        "and what fixes do you suggest? Cite a standard if relevant."
    )
    print(f"User (T1): {turn1_q}\n")
    resp1 = agent.run(turn1_q, on_event=_on_event)
    _print_metadata("T1", resp1)

    # ----- Turn 2: follow-up without re-pasting the STEP path -----
    # Uses AgentResponse.messages round-trip to validate multi-turn history.
    # If the model needs to re-call analyze_geometry it will still find the
    # path in earlier tool-call arguments inside history, NOT in turn2_q.
    turn2_q = (
        "Of those findings, which is the worst for an SLS print run, "
        "and what's the single highest-priority fix?"
    )
    print(f"\n\nUser (T2): {turn2_q}\n")
    resp2 = agent.run(turn2_q, on_event=_on_event, history=resp1.messages)
    _print_metadata("T2", resp2)

    # ----- Smoke assertions — soft, printed. -----
    finding_kws = ("SelfIntersection", "OpenBoundaries", "ShortEdges")
    t1_text = (resp1.final_text or "").lower()
    t2_text = (resp2.final_text or "").lower()
    t2_mentions_path = step_path.as_posix().lower() in turn2_q.lower()

    print("\n=== SMOKE CHECKS ===")
    checks = {
        # Turn 1
        "T1_called_analyze_geometry": any(
            tc["name"] == "analyze_geometry" for tc in resp1.tool_calls
        ),
        "T1_non_empty_final_text": bool(resp1.final_text and resp1.final_text.strip()),
        "T1_did_not_max_out": resp1.stop_reason == "stop",
        "T1_verdict_word_present": "verdict" in t1_text,
        "T1_cited_a_finding_check": any(kw.lower() in t1_text for kw in finding_kws),
        # Turn 2 (multi-turn history validation)
        "T2_question_omits_step_path": not t2_mentions_path,
        "T2_non_empty_final_text": bool(resp2.final_text and resp2.final_text.strip()),
        "T2_did_not_max_out": resp2.stop_reason == "stop",
        "T2_cited_a_finding_check": any(kw.lower() in t2_text for kw in finding_kws),
        "T2_history_grew": len(resp2.messages) > len(resp1.messages),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
