from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .discovery import (
    identifier_candidates,
    infer_family,
    resolve_cross_table_patient_keys,
    resolve_event_key,
)
from .eda import complete_table_eda
from .profile import write_profile
from .relationships import cross_table_relationships
from .utils import discover_table_files, load_json, read_table, save_json


def run_eda_calibration(input_dir, output_dir, config_path):
    cfg = load_json(config_path)
    discovery_cfg = cfg["discovery"]
    eda_cfg = cfg["eda"]

    files = discover_table_files(input_dir, discovery_cfg["extensions"])
    if not files:
        raise FileNotFoundError(f"No supported source tables found in {input_dir}")

    states = {}

    print("DYNSIM TRE EDA + CALIBRATION")
    print("=" * 90)
    print(f"Input: {Path(input_dir).resolve()}")
    print(f"Tables discovered: {len(files)}")

    # Stage 1: load and discover structure, exactly as an EDA preflight.
    for path in files:
        table = path.stem
        df = read_table(path)
        ids = identifier_candidates(
            df,
            discovery_cfg["identifier_min_score"],
            discovery_cfg["max_identifier_candidates"],
        )
        family = infer_family(df)

        states[table] = {
            "path": path,
            "raw": df,
            "family": family,
            "identifier_candidates": ids,
        }

        print(
            f"{table}: rows={len(df):,}, cols={df.shape[1]}, "
            f"family={family}, id_candidates={len(ids)}"
        )

    # Stage 2: resolve patient keys from observed cross-table linkage.
    patient_keys = resolve_cross_table_patient_keys(states)

    for table, state in states.items():
        state["patient_key"] = patient_keys.get(table)
        state["event_key"] = resolve_event_key(
            state["raw"],
            state["family"],
            state["identifier_candidates"],
            state["patient_key"],
        )
        print(
            f"{table}: patient_key={state['patient_key']} | "
            f"event_key={state['event_key']}"
        )

    # Stage 3: run the actual EDA/calibration metrics.
    results = {}
    for table, state in states.items():
        print("\n" + "-" * 90)
        print(f"EDA: {table}")
        results[table] = complete_table_eda(
            table,
            state,
            eda_cfg,
            discovery_cfg,
        )

    # Stage 4: cross-table patient coverage/overlap QA.
    cross = cross_table_relationships(states, results)

    # Stage 5: profile the EDA findings into machine-readable aggregates.
    assembled = write_profile(states, results, cross, output_dir)

    manifest = {
        "profile_version": "dynsim_tre_eda_calibration_v1_3",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(Path(input_dir).resolve()),
        "table_names": list(states),
        "project_specific_statistical_findings_hardcoded": False,
        "process": [
            "source discovery",
            "EDA structural/key discovery",
            "table-family EDA",
            "statistical calibration",
            "cross-table relationship QA",
            "aggregate metadata profile",
        ],
    }
    save_json(manifest, Path(output_dir) / "manifest.json")

    print("\n" + "=" * 90)
    print("EDA + CALIBRATION COMPLETE")
    print(f"Aggregate profile: {Path(output_dir).resolve()}")
    print("No source rows or identifier values are written to the aggregate profile.")
    return states, results, assembled
