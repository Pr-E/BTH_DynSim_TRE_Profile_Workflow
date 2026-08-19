from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from .compiler import compile_portable_metadata
from .profiles import (
    profile_columns,
    profile_identifier_burden,
    profile_repeat_gaps,
    profile_table_inventory,
    profile_temporal_intervals,
    profile_within_table_links,
)
from .relationships import profile_cross_table_links
from .utils import discover_tables, load_json, read_table, save_json


OUTPUT_NAMES = {
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
    "slots": "slot_occupancy.csv",
}


def _concat(parts):
    parts = [df for df in parts if df is not None and not df.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def run_profile(input_dir, output_dir, config_path):
    config = load_json(config_path)
    settings = config["discovery"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    discovered = discover_tables(
        input_dir,
        settings["include_extensions"],
        settings["exclude_name_startswith"],
    )
    if not discovered:
        raise FileNotFoundError(f"No supported tables found in: {input_dir}")

    tables = {}
    inventories = []
    column_parts = []
    identifier_parts = []
    numeric_parts = []
    categorical_parts = []
    datetime_parts = []
    burden_parts = []
    within_parts = []
    interval_parts = []
    gap_parts = []
    slot_parts = []
    identifier_profiles = {}

    print("DYNSIM GENERIC TRE PROFILER")
    print("=" * 80)
    print(f"Input:  {Path(input_dir).resolve()}")
    print(f"Output: {output_dir.resolve()}")
    print(f"Tables discovered: {len(discovered)}")

    for table_name, path in discovered.items():
        print(f"\nProfiling {table_name} ...")
        df = read_table(path)
        tables[table_name] = df

        inventories.append(profile_table_inventory(table_name, df, path))
        parts = profile_columns(table_name, df, settings)

        column_parts.append(parts["columns"])
        identifier_parts.append(parts["identifiers"])
        numeric_parts.append(parts["numeric"])
        categorical_parts.append(parts["categorical"])
        datetime_parts.append(parts["datetime"])
        slot_parts.append(parts["slots"])

        identifier_profiles[table_name] = parts["identifiers"]

        burden_parts.append(
            profile_identifier_burden(table_name, df, parts["identifiers"])
        )
        within_parts.append(
            profile_within_table_links(table_name, df, parts["identifiers"])
        )
        interval_parts.append(
            profile_temporal_intervals(
                table_name,
                df,
                parts["datetime"],
                settings["max_datetime_columns_for_pairwise_intervals"],
            )
        )
        gap_parts.append(
            profile_repeat_gaps(
                table_name,
                df,
                parts["identifiers"],
                parts["datetime"],
                settings["max_identifier_columns_for_repeat_gaps"],
            )
        )

        print(
            f"  rows={len(df):,}, cols={df.shape[1]}, "
            f"identifier_candidates={len(parts['identifiers'])}, "
            f"datetime_candidates={len(parts['datetime'])}"
        )

    outputs = {
        "tables": pd.DataFrame(inventories),
        "columns": _concat(column_parts),
        "identifiers": _concat(identifier_parts),
        "numeric": _concat(numeric_parts),
        "categorical": _concat(categorical_parts),
        "datetime": _concat(datetime_parts),
        "identifier_burden": _concat(burden_parts),
        "within_table_links": _concat(within_parts),
        "temporal_intervals": _concat(interval_parts),
        "repeat_gaps": _concat(gap_parts),
        "slots": _concat(slot_parts),
    }

    outputs["cross_table_links"] = profile_cross_table_links(
        tables,
        identifier_profiles,
        settings["cross_table_min_overlap"],
    )

    for key, filename in OUTPUT_NAMES.items():
        outputs[key].to_csv(output_dir / filename, index=False)

    compile_portable_metadata(
        output_dir,
        output_dir / "portable_metadata.json",
    )

    manifest = {
        "profile_version": "dynsim_tre_generic_profiler_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(Path(input_dir).resolve()),
        "n_tables": len(discovered),
        "table_names": list(discovered.keys()),
        "project_specific_values_hardcoded": False,
        "notes": (
            "Table names, schemas, identifier candidates, distributions, temporal "
            "profiles and relationships are discovered from the source tables."
        ),
    }
    save_json(manifest, output_dir / "manifest.json")

    print("\n" + "=" * 80)
    print("PROFILE COMPLETE")
    print(f"Aggregate profile: {output_dir.resolve()}")
    print("No source rows or identifier values are written to the profile outputs.")

    return outputs
