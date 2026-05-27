#!/usr/bin/env python3
"""Capture Streamlit analysis-UI screenshots for the README.

Drives ui/app.py (must already be running on the given port): screenshots the
upload screen, uploads a fixture with real findings, then screenshots the full
analysis report. Output PNGs land in docs/img/.

Usage:
    python scripts/ui_screenshots.py [--port 8501] [--fixture tests/data/realistic_brackets/boxed_beam_with_holes.step]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--fixture", default="tests/data/realistic_brackets/boxed_beam_with_holes.step")
    parser.add_argument("--out-dir", default="docs/img")
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fixture = Path(args.fixture).resolve()
    if not fixture.is_file():
        print(f"fixture not found: {fixture}", file=sys.stderr)
        return 1

    url = f"http://127.0.0.1:{args.port}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1500})
        page.goto(url, wait_until="networkidle", timeout=45000)
        page.screenshot(path=str(out / "streamlit-upload.png"), full_page=True)
        print("wrote", out / "streamlit-upload.png")

        page.locator('input[type="file"]').set_input_files(str(fixture))
        # Streamlit reruns on upload; wait for the report to render.
        page.wait_for_load_state("networkidle", timeout=45000)
        try:
            page.get_by_text("Score Breakdown", exact=False).first.wait_for(timeout=15000)
        except Exception:
            pass
        # st.dataframe components (Findings, per-face table) hydrate via a JS
        # glide-grid after networkidle — give them time so they aren't captured
        # as empty loading skeletons.
        page.wait_for_timeout(9000)
        page.screenshot(path=str(out / "streamlit-analysis.png"), full_page=True)
        print("wrote", out / "streamlit-analysis.png")

        body = page.locator("body").inner_text()
        browser.close()

    ok = "SimReady" in body and fixture.name in body
    print("render check:", "OK" if ok else "PARTIAL", "| contains findings:", "Findings" in body)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
