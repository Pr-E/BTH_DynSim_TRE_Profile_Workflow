from pathlib import Path

import pandas as pd

from .utils import save_json


PROFILE_FILES = {
    "tables": "tables.csv",
    "columns": "columns.csv",
    "identifiers": "identifier_candidates.csv",
    "numeric": "numeric.csv",
    "categorical": "categorical.csv",
    "datetime": "datetime.csv",
    "identifier_burden": "identifier_burden.csv",
    "within_table_links": "within_table_links.csv",
    "cross_table_links": "cross_table_links.csv",
    "temporal_intervals": "temporal_intervals.csv",
    "repeat_gaps": "repeat_gaps.csv",
    "slot_occupancy": "slot_occupancy.csv",
}


def _records(path):
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    df = pd.read_csv(path, low_memory=False)
    return df.where(pd.notna(df), None).to_dict(orient="records")


def compile_portable_metadata(profile_dir, output_path=None):
    profile_dir = Path(profile_dir)
    data = {name: _records(profile_dir / filename) for name, filename in PROFILE_FILES.items()}

    tables = {}
    for row in data["tables"]:
        table_name = row["table"]
        tables[table_name] = {
            "inventory": row,
            "columns": [r for r in data["columns"] if r["table"] == table_name],
            "identifier_candidates": [r for r in data["identifiers"] if r["table"] == table_name],
            "numeric_profiles": [r for r in data["numeric"] if r["table"] == table_name],
            "categorical_profiles": [r for r in data["categorical"] if r["table"] == table_name],
            "datetime_profiles": [r for r in data["datetime"] if r["table"] == table_name],
            "identifier_burden": [r for r in data["identifier_burden"] if r["table"] == table_name],
            "within_table_links": [r for r in data["within_table_links"] if r["table"] == table_name],
            "temporal_intervals": [r for r in data["temporal_intervals"] if r["table"] == table_name],
            "repeat_gaps": [r for r in data["repeat_gaps"] if r["table"] == table_name],
            "slot_occupancy": [r for r in data["slot_occupancy"] if r["table"] == table_name],
        }

    portable = {
        "metadata_format": "dynsim_portable_profile_v1",
        "source_type": "aggregate_profile",
        "tables": tables,
        "cross_table_links": data["cross_table_links"],
    }

    if output_path:
        save_json(portable, output_path)
    return portable
