import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
sys.path = [SRC] + [p for p in sys.path if p != SRC]

from dynsim_tre_profiler.disclosure import create_export_profile
from dynsim_tre_profiler.validation import validate_profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--internal", required=True)
    parser.add_argument("--export", default="metadata_profiles/export")
    parser.add_argument("--bundle", default="metadata_profiles/DynSim_Aggregate_Profile_EGRESS_CANDIDATE.zip")
    parser.add_argument("--min-cell-count", type=int, required=True)
    parser.add_argument("--round-base", type=int, default=1)
    parser.add_argument("--date-granularity", choices=["year", "month", "day"], default="month")
    args = parser.parse_args()

    export_dir = Path(args.export)
    if export_dir.exists():
        shutil.rmtree(export_dir)

    create_export_profile(
        args.internal,
        export_dir,
        min_cell_count=args.min_cell_count,
        round_base=args.round_base,
        date_granularity=args.date_granularity,
    )

    checks, passed = validate_profile(export_dir)
    if not passed:
        print(checks.to_string(index=False))
        raise SystemExit("Export profile validation failed.")

    bundle = Path(args.bundle)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    if bundle.exists():
        bundle.unlink()

    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(export_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(export_dir))

    print("EGRESS CANDIDATE CREATED")
    print(f"Export folder: {export_dir.resolve()}")
    print(f"Bundle: {bundle.resolve()}")
    print("This does not authorise egress; submit through the TRE disclosure process.")


if __name__ == "__main__":
    main()
