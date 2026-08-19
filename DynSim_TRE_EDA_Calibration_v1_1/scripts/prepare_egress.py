"""Command-line entry point for creating a disclosure-controlled egress candidate."""

import argparse
import sys
from pathlib import Path

# Add the repository src/ directory explicitly so the TRE run does not require an editable install.
ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
sys.path = [SRC] + [p for p in sys.path if p != SRC]

from dynsim_tre_calibration.disclosure import prepare_egress


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--internal", required=True)
    parser.add_argument("--export", default="metadata_profiles/export")
    parser.add_argument("--bundle", default="metadata_profiles/DynSim_Aggregate_EDA_Profile_EGRESS_CANDIDATE.zip")
    parser.add_argument("--min-cell-count", type=int, required=True)
    parser.add_argument("--round-base", type=int, required=True)
    args = parser.parse_args()

    # Threshold and rounding rules are supplied explicitly after confirmation by the TRE output-checking team.
    bundle = prepare_egress(
        args.internal,
        args.export,
        args.min_cell_count,
        args.round_base,
        args.bundle,
    )
    print("EGRESS CANDIDATE CREATED")
    print(bundle.resolve())
    print("This file still requires normal TRE disclosure/output approval.")


if __name__ == "__main__":
    main()
