"""Day-4 smoke (light): real LLM + canned analyze_file payload.

Validates against the real provider (NIM Llama 3.3 70B per env):
  * tool-call argument shape on a multi-tool chain
  * Verdict / Issues / Fixes / Citations format
  * severity_counts surfaced correctly
  * lookup_standard graceful fallback on no_index (RAG corpus empty)
  * max_iterations not silently hit

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

# Stub analyze_file BEFORE the agent imports it — module-global swap.
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


tools.analyze_file = _stub_analyze_file

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


def main() -> int:
    step_path = Path("tests/data/grabcad/manifold_complex.STEP")
    if not step_path.exists():
        print(f"ERR: {step_path} missing.", file=sys.stderr)
        return 2

    agent = CopilotAgent()
    print(f"Provider base_url: {os.environ.get('OPENAI_BASE_URL', '(default OpenAI)')}")
    print(f"Model: {agent.model}")
    print(f"STEP: {step_path}\n")

    question = (
        f"What manufacturing issues does {step_path.as_posix()} have, "
        "and what fixes do you suggest? Cite a standard if relevant."
    )
    print(f"User: {question}\n")

    resp = agent.run(question, on_event=_on_event)

    print("\n=== FINAL TEXT ===")
    print(resp.final_text or "(empty — bug)")
    print("\n=== METADATA ===")
    print(f"stop_reason   : {resp.stop_reason}")
    print(f"iterations    : {resp.iterations}")
    print(f"tool_calls    : {[tc['name'] for tc in resp.tool_calls]}")
    print(f"usage         : {resp.usage}")

    # Smoke assertions — soft, just printed.
    print("\n=== SMOKE CHECKS ===")
    checks = {
        "called_analyze_geometry": any(tc["name"] == "analyze_geometry" for tc in resp.tool_calls),
        "non_empty_final_text": bool(resp.final_text and resp.final_text.strip()),
        "did_not_max_out": resp.stop_reason == "stop",
        "verdict_word_present": "verdict" in (resp.final_text or "").lower(),
        "cited_a_finding_check": any(
            kw.lower() in (resp.final_text or "").lower()
            for kw in ("SelfIntersection", "OpenBoundaries", "ShortEdges")
        ),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
