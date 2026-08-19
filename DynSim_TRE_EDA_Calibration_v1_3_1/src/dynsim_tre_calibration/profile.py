from pathlib import Path

import pandas as pd

from .utils import safe_records, save_json


OUTPUTS = {
    "inventory": "eda_table_inventory.csv",
    "schema": "eda_schema.csv",
    "keys": "eda_keys.csv",
    "key_qa": "eda_key_qa.csv",
    "anomaly_candidates": "eda_anomaly_candidates.csv",
    "count_summaries": "eda_count_summaries.csv",
    "count_distributions": "eda_count_distributions.csv",
    "numeric": "eda_numeric.csv",
    "categorical": "eda_categorical.csv",
    "dates": "eda_dates.csv",
    "intervals": "eda_intervals.csv",
    "temporal_qa": "eda_temporal_qa.csv",
    "slots": "eda_slot_occupancy.csv",
    "seasonality": "eda_seasonality.csv",
    "within_patient_consistency": "eda_within_patient_consistency.csv",
    "row_missingness": "eda_row_missingness.csv",
    "missingness_pairs": "eda_missingness_pairs.csv",
    "missingness_patterns": "eda_missingness_patterns.csv",
    "numeric_correlations": "eda_numeric_correlations.csv",
    "categorical_associations": "eda_categorical_associations.csv",
    "categorical_joint": "eda_categorical_joint.csv",
    "cross_table_relationships": "eda_cross_table_relationships.csv",
}


def _concat(results, key):
    frames = [
        result.get(key) for result in results.values()
        if result.get(key) is not None and not result.get(key).empty
    ]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def write_profile(states, results, cross_table, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = {}
    keys_rows = []

    for table, state in states.items():
        keys_rows.append({
            "table": table,
            "family": state["family"],
            "patient_key": state["patient_key"],
            "event_key": state["event_key"],
        })

    assembled = {
        "inventory": _concat(results, "inventory"),
        "schema": _concat(results, "schema"),
        "keys": pd.DataFrame(keys_rows),
        "key_qa": _concat(results, "key_qa"),
        "anomaly_candidates": _concat(results, "anomaly_candidates"),
        "count_summaries": _concat(results, "count_summaries"),
        "count_distributions": _concat(results, "count_distributions"),
        "numeric": _concat(results, "numeric"),
        "categorical": _concat(results, "categorical"),
        "dates": _concat(results, "dates"),
        "intervals": _concat(results, "intervals"),
        "temporal_qa": _concat(results, "temporal_qa"),
        "slots": _concat(results, "slots"),
        "seasonality": _concat(results, "seasonality"),
        "within_patient_consistency": _concat(results, "within_patient_consistency"),
        "row_missingness": _concat(results, "row_missingness"),
        "missingness_pairs": _concat(results, "missingness_pairs"),
        "missingness_patterns": _concat(results, "missingness_patterns"),
        "numeric_correlations": _concat(results, "numeric_correlations"),
        "categorical_associations": _concat(results, "categorical_associations"),
        "categorical_joint": _concat(results, "categorical_joint"),
        "cross_table_relationships": cross_table,
    }

    for key, filename in OUTPUTS.items():
        assembled[key].to_csv(output_dir / filename, index=False)

    for table, state in states.items():
        table_profile = {
            "family": state["family"],
            "patient_key": state["patient_key"],
            "event_key": state["event_key"],
        }
        for key, frame in assembled.items():
            if key == "cross_table_relationships":
                continue
            if frame.empty or "table" not in frame.columns:
                table_profile[key] = []
            else:
                table_profile[key] = safe_records(frame[frame["table"] == table])
        tables[table] = table_profile

    portable = {
        "metadata_format": "dynsim_tre_eda_calibration_v1",
        "source_type": "aggregate_eda_profile",
        "tables": tables,
        "cross_table_relationships": safe_records(cross_table),
    }
    save_json(portable, output_dir / "portable_metadata.json")
    return assembled
