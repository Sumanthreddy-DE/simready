"""CLI: python -m simready.bench {smoke,run,regrade,replay,report}.

Imports are lazy per subcommand so ``report`` runs in plain Python
(no OCC, no openai) on the committed logs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "data" / "bench_runs"

SMOKE_PROMPT = "A 40 x 30 x 5 mm plate with one 6 mm through hole in the centre."


def _smoke(args: argparse.Namespace) -> int:
    from simready.bench.attempt import classify_spec, parse_reply
    from simready.bench.prompting import BUILD_PART_TOOL, build_messages
    from simready.bench.providers import ModelClient, load_providers

    provider = load_providers()[args.model]
    client = ModelClient(provider, max_retries=2)
    try:
        ids = sorted(m.id for m in client.client.models.list())
        print(f"models.list: {len(ids)} ids; configured id present: {provider.model in ids}")
        if provider.model not in ids:
            print("  ids containing the alias stem:", [i for i in ids if args.model.split("-")[0] in i.lower()][:20])
    except Exception as exc:  # noqa: BLE001 — some providers don't serve models.list
        print(f"models.list unavailable: {type(exc).__name__}")
    reply = client.complete(build_messages(SMOKE_PROMPT), [BUILD_PART_TOOL], 0.7, seed=0)
    parsed = parse_reply(reply["tool_calls"], reply["content"])
    cls = classify_spec(parsed.spec)[0] if parsed.spec is not None else "F1_no_parse"
    print(json.dumps({
        "model_returned": reply["model_returned"],
        "finish_reason": reply["finish_reason"],
        "via": parsed.via,
        "n_tool_calls": parsed.n_tool_calls,
        "pre_build_class": cls,
        "usage": reply["usage"],
        "latency_s": reply["latency_s"],
    }, indent=2))
    return 0 if parsed.spec is not None else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m simready.bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke", help="one live call: model id, tool calling, parse")
    s.add_argument("--model", required=True)
    args = ap.parse_args(argv)
    handlers = {"smoke": _smoke}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
