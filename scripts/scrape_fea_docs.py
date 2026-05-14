"""Download FEA / mechanical-standards PDFs into data/fea_docs/.

URLs come from data/fea_docs/sources.txt (one URL per line, '#' comments allowed).
Existing files are skipped unless --force. Filenames are derived from the URL
basename; rename in-place if you need something tidier.

Suggested public sources (paste into sources.txt — assistant does NOT auto-fetch
URLs that may rot):
    NAFEMS quality publications     https://www.nafems.org/publications/
    ASME PTC 60 (mesh adequacy)     https://www.asme.org/codes-standards
    Open mesh-quality whitepapers   any vendor doc you trust (Ansys, Abaqus, ...)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests


DEFAULT_SOURCES = Path("data/fea_docs/sources.txt")
DEFAULT_OUTPUT = Path("data/fea_docs")
TIMEOUT_SECONDS = 60
USER_AGENT = "SimReady/0.4 RAG fetcher"


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = unquote(Path(parsed.path).name) or "download"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name


def _read_sources(path: Path) -> list[str]:
    if not path.exists():
        return []
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if cleaned:
            urls.append(cleaned)
    return urls


def _ensure_sources_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# One URL per line. '#' starts a comment.\n"
        "# Add public-domain or vendor whitepapers on FEA mesh quality, manufacturability, etc.\n"
        "# Examples (you must vet & paste actual stable URLs yourself):\n"
        "# https://example.org/nafems_qa01.pdf\n"
        "# https://example.org/asme_ptc60.pdf\n",
        encoding="utf-8",
    )


def download(url: str, dest: Path, force: bool = False) -> str:
    if dest.exists() and not force:
        return "skip-exists"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*;q=0.8"}
    response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS, stream=True)
    response.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if chunk:
                f.write(chunk)
    return "ok"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES,
                        help=f"Sources file (default: {DEFAULT_SOURCES})")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Output directory (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if file exists")
    args = parser.parse_args(argv)

    if not args.sources.exists():
        _ensure_sources_template(args.sources)
        print(f"Created template at {args.sources}. Paste URLs and re-run.", flush=True)
        return 0

    urls = _read_sources(args.sources)
    if not urls:
        print(f"{args.sources} has no URLs (only comments / blanks). Nothing to do.",
              flush=True)
        return 0

    args.output.mkdir(parents=True, exist_ok=True)
    failures: list[tuple[str, str]] = []
    counts = {"ok": 0, "skip-exists": 0, "fail": 0}

    for url in urls:
        dest = args.output / _filename_from_url(url)
        try:
            status = download(url, dest, force=args.force)
        except requests.RequestException as exc:
            counts["fail"] += 1
            failures.append((url, str(exc)))
            print(f"  FAIL  {url}  -> {exc}", flush=True)
            continue
        counts[status] += 1
        print(f"  {status:<12} {dest}", flush=True)

    print(f"\nDone. ok={counts['ok']} skip={counts['skip-exists']} fail={counts['fail']}",
          flush=True)
    if failures:
        print("Failures:")
        for url, err in failures:
            print(f"  {url} -> {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
