from pathlib import Path
import json

import pandas as pd


REQUIRED_FILES = [
    "tables.csv",
    "columns.csv",
    "identifier_candidates.csv",
    "numeric.csv",
    "categorical.csv",
    "datetime.csv",
    "identifier_burden.csv",
    "within_table_links.csv",
    "cross_table_links.csv",
    "temporal_intervals.csv",
    "repeat_gaps.csv",
    "slot_occupancy.csv",
    "portable_metadata.json",
]


def validate_profile(profile_dir):
    profile_dir = Path(profile_dir)
    checks = []

    for name in REQUIRED_FILES:
        path = profile_dir / name
        checks.append({
            "check": f"file_exists:{name}",
            "pass": path.exists(),
            "detail": str(path),
        })

    tables_path = profile_dir / "tables.csv"
    columns_path = profile_dir / "columns.csv"

    if tables_path.exists() and columns_path.exists():
        tables = pd.read_csv(tables_path, low_memory=False)
        columns = pd.read_csv(columns_path, low_memory=False)

        checks.append({
            "check": "at_least_one_table",
            "pass": len(tables) > 0,
            "detail": f"n_tables={len(tables)}",
        })

        missing_column_profiles = sorted(
            set(tables["table"].astype(str)) - set(columns["table"].astype(str))
        )
        checks.append({
            "check": "all_tables_have_column_profiles",
            "pass": not missing_column_profiles,
            "detail": str(missing_column_profiles),
        })

    metadata_path = profile_dir / "portable_metadata.json"
    if metadata_path.exists():
        try:
            with metadata_path.open("r", encoding="utf-8") as f:
                metadata = json.load(f)
            ok = metadata.get("metadata_format") == "dynsim_portable_profile_v1"
            checks.append({
                "check": "portable_metadata_format",
                "pass": ok,
                "detail": metadata.get("metadata_format"),
            })
        except Exception as exc:
            checks.append({
                "check": "portable_metadata_readable",
                "pass": False,
                "detail": repr(exc),
            })

    result = pd.DataFrame(checks)
    return result, bool(result["pass"].all()) if not result.empty else False
