"""Offline generation-path wall timings; run with --label before or after.

Each part has three rounds in one parent process. Each analyze/import probe
starts a fresh interpreter, just like analyze_file_safe. The import probe is
an estimate (startup + pipeline imports + exit), not a subtraction benchmark.
No credentials, dotenv loading, or network clients are used.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ROUNDS = 3


def final_specs() -> dict[str, dict[str, Any]]:
    """Exact final specs from geometry_gen_eval.md's v2.1 table."""
    def box(dx: float, dy: float, dz: float, **kwargs: Any) -> dict[str, Any]:
        return {"op": "box", "dx": dx, "dy": dy, "dz": dz, **kwargs}

    def hole(dx: float, dy: float, dz: float, radius: float) -> dict[str, Any]:
        return {"steps": [box(dx, dy, dz),
                          {"op": "cyl", "r": radius, "h": dz, "at": [dx / 2, dy / 2, 0]},
                          {"op": "cut", "a": 0, "b": 1}]}

    return {
        "normal_box": {"steps": [box(60, 40, 30)]},
        "thin_plate": {"steps": [box(100, 80, 0.5)]},
        "l_bracket": {"steps": [box(60, 60, 10), box(10, 60, 50, at=[0, 30, 10]),
                                {"op": "fuse", "a": 0, "b": 1}]},
        "bracket_with_hole": hole(80, 60, 10, 5),
        "small_feature_box": hole(60, 60, 30, 0.5),
    }


def timed(call: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter()
    result = call()
    return time.perf_counter() - started, result


def import_child() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run(
        [sys.executable, "-c", "from simready.pipeline import _analyze_file_inner"],
        cwd=ROOT, env=env, check=True, timeout=120,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )


def measure_part(spec: dict[str, Any]) -> list[dict[str, Any]]:
    # Kept inside the function: build_part uses multiprocessing spawn, which
    # re-imports this script. Do not load torch/OCC in that child's __main__.
    from simready.copilot.tools import _maybe_heal_step, _maybe_render_png
    from simready.gen.build import build_part
    from simready.gen.verify import analyze_generated_part
    from simready.pipeline import analyze_file_safe

    rounds = []
    for index in range(ROUNDS):
        seconds: dict[str, float] = {}
        seconds["import_child"], _ = timed(import_child)
        seconds["build_part"], built = timed(lambda: build_part(spec))
        if not built.get("occ_valid"):
            raise RuntimeError(f"build failed: {built}")
        path = built["step_path"]
        seconds["analyze_file_safe"], report = timed(lambda: analyze_file_safe(path))
        if report.get("status") == "InvalidInput":
            raise RuntimeError(f"analysis failed: {report}")
        seconds["png_render"], png = timed(lambda: _maybe_render_png(path, report))
        seconds["heal_export"], healed = timed(lambda: _maybe_heal_step(path, Path(path).stem))
        if png is None or healed is None:
            raise RuntimeError(f"artifact stage failed: png={png}, healed={healed}")
        seconds["analyze_generated_part"], verified = timed(lambda: analyze_generated_part(path))
        if not verified.get("ok"):
            raise RuntimeError(f"final analysis failed: {verified}")
        rounds.append({"round": index + 1, "seconds": seconds, "step_path": path,
                       "image_path": str(png), "healed_step_path": str(healed)})
    return rounds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not args.label or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in args.label):
        parser.error("label must contain only letters, digits, underscores or hyphens")

    from simready.gen.spec import PartSpec

    specs = final_specs()
    for spec in specs.values():
        PartSpec.model_validate(spec)
    os.chdir(ROOT)  # Match repo-relative render/heal directories used by the tools.
    results = {name: measure_part(spec) for name, spec in specs.items()}
    summary = {}
    print("\npart / stage                         first s     mean rounds 2-3 s")
    for name, rounds in results.items():
        summary[name] = {}
        for stage in rounds[0]["seconds"]:
            first = rounds[0]["seconds"][stage]
            warm = statistics.mean(r["seconds"][stage] for r in rounds[1:])
            summary[name][stage] = {"first_seconds": first, "later_mean_seconds": warm}
            print(f"{name + ' / ' + stage:40} {first:9.4f} {warm:20.4f}")
    out = ROOT / "data" / "gen_eval" / f"timing_{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"label": args.label, "python": sys.executable, "rounds": ROUNDS,
               "note": "First is first per part, not cold OS cache. Timings overlap: do not sum verifier and analysis.",
               "specs": specs, "results": results, "summary": summary}
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"JSON: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
