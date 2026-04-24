"""Download sample GrabCAD STEP files for real-world testing.

Since GrabCAD requires login for downloads, this script provides instructions
and verifies downloaded files are placed correctly.
"""
from pathlib import Path

SAMPLE_DIR = Path("tests/data/grabcad")
EXPECTED_FILES = [
    "bracket_simple.step",
    "bracket_medium.step",
    "housing_complex.step",
]


def check_samples():
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    missing = [f for f in EXPECTED_FILES if not (SAMPLE_DIR / f).exists()]
    if missing:
        print("Missing GrabCAD sample files:")
        print(f"  Place them in: {SAMPLE_DIR.resolve()}")
        for f in missing:
            print(f"  - {f}")
        print()
        print("Download instructions:")
        print("1. Go to grabcad.com and search for 'bracket STEP'")
        print("2. Download 3 models of varying complexity")
        print("3. Rename to the expected filenames above")
        print("4. Place in the tests/data/grabcad/ directory")
    else:
        print(f"All {len(EXPECTED_FILES)} sample files present.")
    return missing


if __name__ == "__main__":
    check_samples()
