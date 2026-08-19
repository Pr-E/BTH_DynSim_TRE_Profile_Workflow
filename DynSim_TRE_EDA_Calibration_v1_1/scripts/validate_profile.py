"""Command-line entry point for validating a completed aggregate profile."""

import argparse
import sys
from pathlib import Path

# Add the repository src/ directory explicitly so the TRE run does not require an editable install.
ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
sys.path = [SRC] + [p for p in sys.path if p != SRC]

from dynsim_tre_calibration import validate_profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()

    checks, passed = validate_profile(args.profile)
    print(checks.to_string(index=False))
    print("\nVALIDATION:", "PASS" if passed else "FAIL")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
