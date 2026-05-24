"""scripts/eval_finetune.py

Day 18: evaluate model quality on val set + gold traces.

Runs the CopilotAgent on each trace and scores:
  - tool_call_exact:   model called exactly the expected tools
  - tool_call_partial: model called at least the expected tools
  - tool_order_ok:     tools appear in expected relative order
  - format_ok:         output contains "Verdict:" header
  - sections_ok:       output contains both "Issues:" and "Fixes:" sections
  - theme_hit_rate:    fraction of expected themes found (gold traces only)

Run twice with different --model-tag values to fill base vs LoRA columns in
docs/finetune_results.md.

Usage:
    python scripts/eval_finetune.py                           # both datasets, all gold
    python scripts/eval_finetune.py --dataset gold            # gold only
    python scripts/eval_finetune.py --dataset val --n-val 50  # 50 val traces
    python scripts/eval_finetune.py --model-tag "LoRA-3B"     # label for results
    python scripts/eval_finetune.py --dry-run                 # preview 3 traces, no write

Env vars:
    OPENAI_API_KEY, OPENAI_BASE_URL  (same as trace gen)
    OPENAI_MODEL                     (overridden by --model flag)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent

# Patch render + heal to skip PNG/ShapeFix during eval runs
import simready.copilot.tools as _tools
_tools._maybe_render_png = lambda *a, **kw: None  # type: ignore[assignment]
_tools._maybe_heal_step  = lambda *a, **kw: None  # type: ignore[assignment]

from simready.copilot.agent import CopilotAgent  # noqa: E402

logger = logging.getLogger(__name__)

GOLD_FILE    = REPO_ROOT / "tests" / "data" / "gold_traces.jsonl"
TRACES_FILE  = REPO_ROOT / "data" / "fine_tune" / "traces.jsonl"
RESULTS_FILE = REPO_ROOT / "docs" / "finetune_results.md"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _extract_ref_tools(openai_messages: list[dict]) -> list[str]:
    """Pull tool names from OpenAI-format assistant messages."""
    tools: list[str] = []
    for msg in openai_messages:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                name = tc.get("function", {}).get("name", "")
                if name:
                    tools.append(name)
    return tools


def _tool_order_ok(actual: list[str], expected: list[str]) -> bool:
    """Actual tool subsequence matches expected relative order."""
    exp_set = set(expected)
    filtered = [t for t in actual if t in exp_set]
    exp_filtered = [t for t in expected if t in set(actual)]
    return filtered == exp_filtered


def score_response(
    tool_calls_made: list[str],
    final_text: str,
    expected_tools: list[str],
    expected_themes: list[str] | None = None,
) -> dict:
    text_lower = final_text.lower()
    actual_set = set(tool_calls_made)
    expected_set = set(expected_tools)

    result: dict = {
        "tool_call_exact":   actual_set == expected_set,
        "tool_call_partial": expected_set.issubset(actual_set),
        "tool_order_ok":     _tool_order_ok(tool_calls_made, expected_tools),
        "format_ok":         "verdict:" in text_lower,
        "sections_ok":       ("issues:" in text_lower and "fixes:" in text_lower),
        "n_tool_calls":      len(tool_calls_made),
    }

    if expected_themes:
        hits = sum(1 for t in expected_themes if t.lower() in text_lower)
        result["theme_hit_rate"] = hits / len(expected_themes)
        result["theme_hits"] = hits
        result["theme_total"] = len(expected_themes)

    return result


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_gold_traces() -> list[dict]:
    traces: list[dict] = []
    with GOLD_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                traces.append(json.loads(line))
    return traces


def load_val_traces(n: int, seed: int = 42) -> list[dict]:
    """Sample up to n completed traces from traces.jsonl."""
    if not TRACES_FILE.exists():
        return []
    all_traces: list[dict] = []
    with TRACES_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
                if t.get("stop_reason") == "stop":
                    all_traces.append(t)
            except json.JSONDecodeError:
                continue
    rng = random.Random(seed)
    rng.shuffle(all_traces)
    return all_traces[:n]


# ---------------------------------------------------------------------------
# Question construction
# ---------------------------------------------------------------------------

def build_question(trace: dict) -> str:
    """Embed step_path in question so agent knows which file to analyze."""
    q = trace["question"]
    sp = trace.get("step_path")
    if sp and sp not in q:
        return f"{q} File: {sp}"
    return q


# ---------------------------------------------------------------------------
# Eval loop
# ---------------------------------------------------------------------------

def eval_gold(agent: CopilotAgent, traces: list[dict], dry_run: bool = False,
              request_delay: float = 0.0) -> list[dict]:
    results: list[dict] = []
    skip_count = 0

    for i, trace in enumerate(traces):
        if request_delay and not dry_run and i:
            time.sleep(request_delay)
        sp = trace.get("step_path")
        # Skip if STEP file referenced but missing (e.g. gitignored grabcad)
        if sp and not (REPO_ROOT / sp).exists():
            logger.debug("Gold %s: STEP missing (%s), skipping.", trace["id"], sp)
            skip_count += 1
            continue

        question = build_question(trace)
        expected_tools  = trace["expected_tool_calls"]
        expected_themes = trace["expected_answer_themes"]

        if dry_run:
            print(f"\n[DRY RUN gold] {trace['id']} [{trace['category']}]")
            print(f"  Q: {question[:80]}")
            print(f"  Expected tools: {expected_tools}")
            results.append({"id": trace["id"], "dry_run": True})
            if len(results) >= 3:
                break
            continue

        try:
            response = agent.run(question)
            actual_tools = [tc["name"] for tc in response.tool_calls]
            scores = score_response(
                actual_tools, response.final_text,
                expected_tools, expected_themes,
            )
            scores.update({
                "id": trace["id"],
                "category": trace["category"],
                "actual_tools": actual_tools,
                "expected_tools": expected_tools,
            })
            results.append(scores)
            logger.info(
                "gold %s  tools=%s exact=%s theme=%.2f format=%s",
                trace["id"], actual_tools,
                scores["tool_call_exact"],
                scores.get("theme_hit_rate", 0.0),
                scores["format_ok"],
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logger.warning("gold %s failed: %s", trace["id"], exc)
            results.append({"id": trace["id"], "error": str(exc)})

    if skip_count:
        logger.info("Gold: skipped %d traces (STEP files missing).", skip_count)
    return results


def eval_val(agent: CopilotAgent, traces: list[dict], dry_run: bool = False,
             request_delay: float = 0.0) -> list[dict]:
    results: list[dict] = []

    for i, trace in enumerate(traces):
        if request_delay and not dry_run and i:
            time.sleep(request_delay)
        question = build_question(trace)
        ref_tools = _extract_ref_tools(trace.get("messages") or [])

        if dry_run:
            print(f"\n[DRY RUN val] {trace['id']} [{trace['category']}]")
            print(f"  Q: {question[:80]}")
            print(f"  Reference tools: {ref_tools}")
            results.append({"id": trace["id"], "dry_run": True})
            if len(results) >= 3:
                break
            continue

        try:
            response = agent.run(question)
            actual_tools = [tc["name"] for tc in response.tool_calls]
            scores = score_response(actual_tools, response.final_text, ref_tools)
            scores.update({
                "id": trace["id"],
                "category": trace["category"],
                "actual_tools": actual_tools,
                "ref_tools": ref_tools,
            })
            results.append(scores)
            logger.info(
                "val %s  tools=%s exact=%s format=%s",
                trace["id"], actual_tools,
                scores["tool_call_exact"],
                scores["format_ok"],
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logger.warning("val %s failed: %s", trace["id"], exc)
            results.append({"id": trace["id"], "error": str(exc)})

    return results


# ---------------------------------------------------------------------------
# Aggregation + report
# ---------------------------------------------------------------------------

def aggregate(results: list[dict]) -> dict:
    valid = [r for r in results if "error" not in r and not r.get("dry_run")]
    if not valid:
        return {}

    def mean(key: str) -> float:
        vals = [r[key] for r in valid if key in r]
        return sum(vals) / len(vals) if vals else 0.0

    agg: dict = {
        "n": len(valid),
        "n_error": sum(1 for r in results if "error" in r),
        "tool_call_exact":   mean("tool_call_exact"),
        "tool_call_partial": mean("tool_call_partial"),
        "tool_order_ok":     mean("tool_order_ok"),
        "format_ok":         mean("format_ok"),
        "sections_ok":       mean("sections_ok"),
    }
    theme_vals = [r["theme_hit_rate"] for r in valid if "theme_hit_rate" in r]
    if theme_vals:
        agg["theme_hit_rate"] = sum(theme_vals) / len(theme_vals)
    return agg


def print_table(label: str, agg: dict) -> None:
    if not agg:
        print(f"  {label}: no results")
        return
    print(f"\n  {label}  (n={agg['n']}, errors={agg['n_error']})")
    print(f"    tool_call_exact:   {agg['tool_call_exact']:.3f}")
    print(f"    tool_call_partial: {agg['tool_call_partial']:.3f}")
    print(f"    tool_order_ok:     {agg['tool_order_ok']:.3f}")
    print(f"    format_ok:         {agg['format_ok']:.3f}")
    print(f"    sections_ok:       {agg['sections_ok']:.3f}")
    if "theme_hit_rate" in agg:
        print(f"    theme_hit_rate:    {agg['theme_hit_rate']:.3f}")


def append_results_to_md(
    model_tag: str,
    gold_agg: dict,
    val_agg: dict,
    out_path: Path,
) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = f"\n\n## Run: {model_tag}  —  {ts}\n\n"
    block += "| Metric | Gold ({n_g}) | Val ({n_v}) |\n".format(
        n_g=gold_agg.get("n", "-"), n_v=val_agg.get("n", "-")
    )
    block += "|---|---|---|\n"

    metrics = [
        ("tool_call_exact",   "Tool-call exact match"),
        ("tool_call_partial", "Tool-call partial match"),
        ("tool_order_ok",     "Tool order correct"),
        ("format_ok",         "Verdict format present"),
        ("sections_ok",       "Issues+Fixes sections"),
        ("theme_hit_rate",    "Theme hit rate (gold only)"),
    ]
    for key, label in metrics:
        g = f"{gold_agg[key]:.3f}" if key in gold_agg else "—"
        v = f"{val_agg[key]:.3f}"  if key in val_agg  else "—"
        block += f"| {label} | {g} | {v} |\n"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(block)
    logger.info("Results appended to %s", out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Eval fine-tuned vs base model on gold + val traces."
    )
    parser.add_argument("--dataset", choices=["gold", "val", "both"], default="both")
    parser.add_argument("--n-val", type=int, default=200,
                        help="Max val traces to sample (default 200)")
    parser.add_argument("--model", type=str, default=None,
                        help="Override OPENAI_MODEL env var")
    parser.add_argument("--model-tag", type=str, default=None,
                        help="Label for results table (default: model name)")
    parser.add_argument("--out", type=Path, default=RESULTS_FILE,
                        help="Results markdown output path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview 3 traces per dataset, no LLM calls, no write")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--request-delay", type=float, default=0.0,
                        help="Seconds to sleep between traces. Use to stay under "
                             "rate-limited endpoints (e.g. NIM free tier ~4.0).")
    parser.add_argument("--max-retries", type=int, default=3,
                        help="Per-call retry budget on 429/transient errors "
                             "(passed to CopilotAgent; bump to ~6 on NIM free tier).")
    parser.add_argument("--initial-backoff", type=float, default=1.0,
                        help="Initial exponential-backoff seconds for retries "
                             "(passed to CopilotAgent; ~4.0 on NIM free tier).")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    model = args.model or os.environ.get("OPENAI_MODEL", "meta/llama-3.3-70b-instruct")
    model_tag = args.model_tag or model

    if not args.dry_run:
        agent = CopilotAgent(
            model=model,
            max_retries=args.max_retries,
            initial_backoff=args.initial_backoff,
        )
        logger.info(
            "Agent ready. Model: %s  Tag: %s  (max_retries=%d, initial_backoff=%.1fs, "
            "request_delay=%.1fs)",
            model, model_tag, args.max_retries, args.initial_backoff, args.request_delay,
        )
    else:
        agent = None  # type: ignore[assignment]

    gold_results: list[dict] = []
    val_results: list[dict] = []

    if args.dataset in ("gold", "both"):
        gold_traces = load_gold_traces()
        logger.info("Gold traces loaded: %d", len(gold_traces))
        gold_results = eval_gold(agent, gold_traces, dry_run=args.dry_run,
                                 request_delay=args.request_delay)

    if args.dataset in ("val", "both"):
        val_traces = load_val_traces(args.n_val, seed=args.seed)
        if not val_traces:
            logger.warning(
                "No val traces found in %s. Run day-15 first.", TRACES_FILE
            )
        else:
            logger.info("Val traces sampled: %d", len(val_traces))
            val_results = eval_val(agent, val_traces, dry_run=args.dry_run,
                                   request_delay=args.request_delay)

    if args.dry_run:
        print("\nDry run complete. No results written.")
        return

    gold_agg = aggregate(gold_results)
    val_agg  = aggregate(val_results)

    print("\n=== Eval complete ===")
    print_table(f"Gold ({model_tag})", gold_agg)
    print_table(f"Val  ({model_tag})", val_agg)

    if gold_agg or val_agg:
        append_results_to_md(model_tag, gold_agg, val_agg, args.out)


if __name__ == "__main__":
    main()
