import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
sys.path = [SRC] + [p for p in sys.path if p != SRC]

from dynsim_tre_profiler import run_profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Folder containing source tables.")
    parser.add_argument("--output", default="metadata_profiles/internal")
    parser.add_argument("--config", default="config/profile.json")
    args = parser.parse_args()

    run_profile(args.input, args.output, args.config)


if __name__ == "__main__":
    main()
