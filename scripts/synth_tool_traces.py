"""scripts/synth_tool_traces.py

Day 15: generate synthetic tool-call traces for fine-tuning.

Each trace = random STEP + random question → full CopilotAgent run → JSONL line.
Output: data/fine_tune/traces.jsonl  (appended on each run; resume-safe).

Usage:
    python scripts/synth_tool_traces.py
    python scripts/synth_tool_traces.py --count 100 --dry-run
    python scripts/synth_tool_traces.py --count 5000 --model llama-3.1-8b-instant

Env vars (via .env):
    OPENAI_API_KEY=...        required
    OPENAI_BASE_URL=...       e.g. https://api.groq.com/openai/v1
    OPENAI_MODEL=...          overridden by --model flag

Optional:
    pip install tqdm           for progress bar
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from tqdm import tqdm as _tqdm

    def tqdm(it, **kwargs):  # type: ignore[misc]
        return _tqdm(it, **kwargs)
except ImportError:
    def tqdm(it, **kwargs):  # type: ignore[misc]
        return it

# Patch render + heal BEFORE importing agent so OCC PNG/ShapeFix is skipped.
# analyze_geometry still runs the full pipeline and returns all findings.
import simready.copilot.tools as _tools
_tools._maybe_render_png = lambda *a, **kw: None  # type: ignore[assignment]
_tools._maybe_heal_step = lambda *a, **kw: None   # type: ignore[assignment]

from simready.copilot.agent import CopilotAgent  # noqa: E402

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DEFAULT = REPO_ROOT / "data" / "fine_tune" / "traces.jsonl"

# ---------------------------------------------------------------------------
# Question templates
# {step_path} is substituted with a repo-relative POSIX path the LLM can pass
# to analyze_geometry. Standards questions have no {step_path}.
# ---------------------------------------------------------------------------

QUESTION_TEMPLATES: list[tuple[str, str]] = [
    # file_triage (12)
    ("What manufacturing issues does {step_path} have?", "file_triage"),
    ("Triage {step_path} for FEA readiness. What is the overall verdict?", "file_triage"),
    ("Analyze {step_path} and tell me if it is safe to mesh as-is.", "file_triage"),
    ("I am about to run structural FEA on {step_path}. Any issues I should fix first?", "file_triage"),
    ("Give me a full geometry quality assessment of {step_path}.", "file_triage"),
    ("What is wrong with {step_path} and how do I fix it before simulation?", "file_triage"),
    ("Rate the FEA readiness of {step_path} and list the top issues.", "file_triage"),
    ("I need to mesh {step_path} for stress analysis. Is it ready?", "file_triage"),
    ("Run a geometry check on {step_path} and summarize the findings.", "file_triage"),
    ("What are the critical defects in {step_path}?", "file_triage"),
    ("Give me a pass/fail verdict on {step_path} for nonlinear implicit FEA.", "file_triage"),
    ("Summarize the geometry health of {step_path}.", "file_triage"),
    # file_specific (15)
    ("Are there open boundary issues in {step_path} that would cause mesh failure?", "file_specific"),
    ("Does {step_path} have any sharp edges or sliver faces that need cleanup?", "file_specific"),
    ("Check {step_path} for self-intersection or overlapping bodies.", "file_specific"),
    ("Flag any features in {step_path} that are too small to mesh reliably.", "file_specific"),
    ("Does {step_path} have any duplicate bodies or geometry topology errors?", "file_specific"),
    ("What is the complexity tier of {step_path} and how does it affect meshing?", "file_specific"),
    ("Check {step_path} for degenerate edges or faces.", "file_specific"),
    ("What is the overall score of {step_path}? What is pulling it down?", "file_specific"),
    ("I am getting non-manifold geometry errors in Hypermesh for {step_path}. What is the root cause?", "file_specific"),
    ("Does {step_path} have any open shells or missing faces?", "file_specific"),
    ("What is the face count and edge count of {step_path}? Is it overly complex?", "file_specific"),
    ("Find all geometry issues in {step_path} and rank them by severity.", "file_specific"),
    ("Does {step_path} pass the basic manufacturability check?", "file_specific"),
    ("Check {step_path} for topology issues that would fail an ANSA quality check.", "file_specific"),
    ("How many bodies does {step_path} contain and are any of them problematic?", "file_specific"),
    # manufacturability (8)
    ("Is {step_path} suitable for injection molding? Flag wall thickness issues.", "manufacturability"),
    ("Can the part in {step_path} be manufactured by CNC machining without fixturing issues?", "manufacturability"),
    ("Would {step_path} be suitable for SLS 3D printing? Check minimum wall thickness.", "manufacturability"),
    ("Is {step_path} castable? Are there undercuts or thin sections that would cause problems?", "manufacturability"),
    ("Assess {step_path} for design-for-manufacturing compliance.", "manufacturability"),
    ("Is the wall thickness in {step_path} adequate for aluminum die casting?", "manufacturability"),
    ("Flag any features in {step_path} that are too thin for FDM printing at a 0.4 mm nozzle.", "manufacturability"),
    ("Can the part in {step_path} be machined from a single billet? Any trapped pockets or undercuts?", "manufacturability"),
    # mesh_prep (6)
    ("I am getting mesh errors in my FEA preprocessor for {step_path}. What does the geometry analysis show?", "mesh_prep"),
    ("Before I mesh {step_path} in ANSYS, what geometry issues should I fix?", "mesh_prep"),
    ("My mesher is failing on {step_path}. What geometry issues could be causing this?", "mesh_prep"),
    ("Recommend a mesh strategy for {step_path}. What is the part complexity?", "mesh_prep"),
    ("I need to create a hex-dominant mesh for {step_path}. Are there geometry blockers?", "mesh_prep"),
    ("My adaptive mesher produced poor quality elements on {step_path}. What is the likely cause?", "mesh_prep"),
    # standards (no {step_path} — tests lookup_standard tool)
    ("What aspect ratio limits should I use for linear-elastic FEA shell elements?", "standards"),
    ("What is the NAFEMS recommendation for minimum element quality in structural analysis?", "standards"),
    ("What Jacobian ratio threshold indicates a degenerate element in implicit FEA?", "standards"),
    ("What are the ASME mesh quality criteria for pressure vessel simulation?", "standards"),
    ("How many element layers should I use through the thickness for bending-dominated FEA?", "standards"),
    ("What warpage angle limit should tetrahedral elements stay under for explicit dynamics?", "standards"),
    ("What is the recommended skewness threshold for RANS CFD meshing?", "standards"),
    ("What element aspect ratio does NAFEMS allow for shell elements in vibration analysis?", "standards"),
]

FILE_TEMPLATES = [(t, c) for t, c in QUESTION_TEMPLATES if c != "standards"]
STANDARDS_TEMPLATES = [(t, c) for t, c in QUESTION_TEMPLATES if c == "standards"]


def discover_step_files() -> list[Path]:
    """All .step/.STEP files under tests/data/ excluding tests/data/grabcad/.

    Deduplicates because Windows case-insensitive fs matches both *.step and *.STEP.
    """
    data_dir = REPO_ROOT / "tests" / "data"
    seen: set[Path] = set()
    result: list[Path] = []
    for p in list(data_dir.rglob("*.step")) + list(data_dir.rglob("*.STEP")):
        if "grabcad" not in p.parts and p not in seen:
            seen.add(p)
            result.append(p)
    return result


def build_seed_pool(
    n_target: int,
    step_files: list[Path],
    rng: random.Random,
    standards_fraction: float = 0.12,
) -> list[tuple[str | None, str, str]]:
    """Return a shuffled list of (step_path_or_None, question, category) seeds."""
    n_standards = int(n_target * standards_fraction)
    n_file = n_target - n_standards

    file_combos: list[tuple[str | None, str, str]] = []
    for step in step_files:
        rel = step.relative_to(REPO_ROOT).as_posix()
        for template, cat in FILE_TEMPLATES:
            file_combos.append((rel, template.format(step_path=rel), cat))

    repeats = math.ceil(n_file / max(len(file_combos), 1))
    file_seeds = (file_combos * repeats)[:n_file]
    rng.shuffle(file_seeds)

    std_combos: list[tuple[str | None, str, str]] = [
        (None, t, c) for t, c in STANDARDS_TEMPLATES
    ]
    std_repeats = math.ceil(n_standards / max(len(std_combos), 1))
    std_seeds = (std_combos * std_repeats)[:n_standards]
    rng.shuffle(std_seeds)

    pool = file_seeds + std_seeds
    rng.shuffle(pool)
    return pool


def count_existing_lines(out_path: Path) -> int:
    if not out_path.exists():
        return 0
    count = 0
    with out_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                count += 1
    return count


def run_trace(
    agent: CopilotAgent,
    trace_id: str,
    step_path: str | None,
    question: str,
    category: str,
) -> dict:
    response = agent.run(question)
    return {
        "id": trace_id,
        "step_path": step_path,
        "question": question,
        "category": category,
        "messages": response.messages,
        "final_text": response.final_text,
        "model": response.model,
        "usage": response.usage,
        "iterations": response.iterations,
        "stop_reason": response.stop_reason,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic copilot tool-call traces for fine-tuning."
    )
    parser.add_argument("--count", type=int, default=5000,
                        help="Total traces to generate (default 5000)")
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT,
                        help="Output JSONL path (default data/fine_tune/traces.jsonl)")
    parser.add_argument("--model", type=str, default=None,
                        help="Model name, overrides OPENAI_MODEL env var")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print seed pool sample and exit — no LLM calls")
    parser.add_argument("--list-steps", action="store_true",
                        help="List discovered STEP files and exit")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for reproducible pool order (default 42)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    step_files = discover_step_files()

    if args.list_steps:
        print(f"Found {len(step_files)} STEP file(s) under tests/data/:")
        for p in sorted(step_files):
            print(f"  {p.relative_to(REPO_ROOT).as_posix()}")
        return

    if not step_files:
        logger.error("No STEP files found under tests/data/. Run from repo root.")
        sys.exit(1)

    rng = random.Random(args.seed)
    pool = build_seed_pool(args.count, step_files, rng)

    if args.dry_run:
        n_show = min(15, len(pool))
        print(f"\nDry run — {len(pool)} seeds planned. First {n_show}:\n")
        for i, (sp, q, cat) in enumerate(pool[:n_show]):
            label = sp or "(no file)"
            print(f"  [{i + 1:>4}] [{cat:<17}] {q[:70]}")
            if sp:
                print(f"              path: {label}")
        cats: dict[str, int] = {}
        for _, _, c in pool:
            cats[c] = cats.get(c, 0) + 1
        print("\nCategory breakdown:")
        for c, n in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"  {c:<20} {n}")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    already_done = count_existing_lines(args.out)
    if already_done:
        logger.info("Resuming: %d traces already written to %s", already_done, args.out)

    remaining = pool[already_done:]
    if not remaining:
        logger.info("All %d traces already generated. Nothing to do.", args.count)
        return

    model = args.model or os.environ.get("OPENAI_MODEL", "llama-3.1-8b-instant")
    agent = CopilotAgent(model=model)
    logger.info(
        "Model: %s | Generating %d trace(s) -> %s",
        model, len(remaining), args.out,
    )

    n_ok = n_fail = 0
    global_idx = already_done

    with args.out.open("a", encoding="utf-8") as fout:
        for step_path, question, category in tqdm(remaining, initial=already_done, total=args.count):
            global_idx += 1
            trace_id = f"synth_{global_idx:05d}"
            try:
                trace = run_trace(agent, trace_id, step_path, question, category)
                fout.write(json.dumps(trace, ensure_ascii=False) + "\n")
                fout.flush()
                n_ok += 1
            except KeyboardInterrupt:
                logger.info("Interrupted at trace %s. %d ok / %d failed.", trace_id, n_ok, n_fail)
                sys.exit(0)
            except Exception as exc:
                logger.warning("Trace %s failed (%s): %s", trace_id, type(exc).__name__, exc)
                n_fail += 1

    logger.info("Complete. %d ok, %d failed. Output: %s", n_ok, n_fail, args.out)


if __name__ == "__main__":
    main()
