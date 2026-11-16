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


def _run(args: argparse.Namespace) -> int:
    from simready.bench.providers import ModelClient, load_providers
    from simready.bench.runner import run_benchmark

    provider = load_providers()[args.model]
    run_id = args.run_id or f"{args.model}-k{args.k}" + (f"-smoke{args.limit}" if args.limit else "")
    summary = run_benchmark(
        client=ModelClient(provider),
        model_alias=args.model,
        model_id=provider.model,
        base_url=provider.base_url,
        k=args.k,
        out_path=RUNS_DIR / f"{run_id}.jsonl",
        limit=args.limit,
        workers=args.workers,
        official=args.official,
        max_tokens=provider.max_tokens,
    )
    print(f"{summary.path}: wrote {summary.written}, infra errors {summary.infra_errors}, "
          f"stopped: {summary.stopped_reason or 'no'}")
    return 0 if summary.stopped_reason is None else 2


def _regrade(args: argparse.Namespace) -> int:
    from simready.bench import CHECKER_VERSION
    from simready.bench.replay import regrade

    run = Path(args.run)
    stem = run.name.removesuffix(".gz").removesuffix(".jsonl")
    out = Path(args.out) if args.out else run.with_name(f"{stem}.regrade-{CHECKER_VERSION}.jsonl")
    n = regrade(run, out)
    print(f"{out}: re-graded {n} attempts with checker {CHECKER_VERSION}")
    return 0


def _replay(args: argparse.Namespace) -> int:
    from simready.bench.replay import replay

    match, logged, rebuilt = replay(Path(args.run), args.attempt_id)
    print(json.dumps({"match": match, "logged": logged, "rebuilt": rebuilt}, indent=2))
    return 0 if match else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m simready.bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke", help="one live call: model id, tool calling, parse")
    s.add_argument("--model", required=True)
    r = sub.add_parser("run", help="run the benchmark for one model")
    r.add_argument("--model", required=True)
    r.add_argument("--k", type=int, default=5)
    r.add_argument("--limit", type=int)
    r.add_argument("--run-id")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--official", action="store_true")
    g = sub.add_parser("regrade", help="re-check logged specs with the current checker")
    g.add_argument("run")
    g.add_argument("--out")
    p = sub.add_parser("replay", help="rebuild one attempt and verify its fingerprint")
    p.add_argument("run")
    p.add_argument("attempt_id")
    args = ap.parse_args(argv)
    handlers = {"smoke": _smoke, "run": _run, "regrade": _regrade, "replay": _replay}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
