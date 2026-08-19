"""Command-line entry point for running the TRE EDA and calibration workflow."""

import argparse
import sys
from pathlib import Path

# Add the repository src/ directory explicitly so the TRE run does not require an editable install.
ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
sys.path = [SRC] + [p for p in sys.path if p != SRC]

from dynsim_tre_calibration import run_eda_calibration


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="TRE folder containing source tables.")
    parser.add_argument("--output", default="metadata_profiles/internal")
    parser.add_argument("--config", default="config/profile.json")
    args = parser.parse_args()

    run_eda_calibration(args.input, args.output, args.config)


if __name__ == "__main__":
    main()
