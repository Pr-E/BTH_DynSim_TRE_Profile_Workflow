from pathlib import Path
import shutil
import zipfile

import numpy as np
import pandas as pd

from .profile import OUTPUTS
from .utils import save_json


COUNT_COLUMNS = {
    "rows_raw", "columns", "exact_duplicate_rows", "fully_blank_rows",
    "unique_patients_raw", "missing_patient_key_n", "unique_events_raw",
    "missing_event_key_n", "non_missing_n", "missing_n", "unique_n",
    "n", "available_n", "negative_n", "zero_n", "positive_n", "valid_n",
    "n_gt_1", "entity_n", "count", "populated_n", "patients_with_multiple_values_n",
    "patients_profiled_n", "row_n", "rows", "left_missing_n", "right_missing_n",
    "both_missing_n", "left_only_missing_n", "right_only_missing_n", "both_present_n",
    "overlap_n", "left_unique_patients", "right_unique_patients",
    "left_entities_n", "left_linked_to_one_right_n", "left_linked_to_multiple_right_n",
    "joint_combinations_n", "combinations_gt_1_n", "max_rows_per_combination",
}

DERIVED_COLUMNS = {
    "mean", "sd", "variance", "variance_to_mean", "skewness", "excess_kurtosis",
    "min", "p01", "p05", "p10", "q1", "median", "q3", "p90", "p95", "p99",
    "max", "iqr", "zero_pct", "negative_pct", "positive_pct", "pct_gt_1",
    "pct_entities", "pct", "parse_success_pct", "populated_pct",
    "pct_with_multiple_values", "pct_rows", "missingness_phi", "pearson_r",
    "spearman_rho", "chi_square", "cramers_v", "joint_pct",
    "right_given_left_pct", "left_given_right_pct", "left_coverage_pct",
    "right_coverage_pct", "jaccard",
}


def _numeric(s):
    return pd.to_numeric(s, errors="coerce")


def _small(s, threshold):
    x = _numeric(s)
    return x.notna() & (x > 0) & (x < threshold)


def protect_frame(df, threshold, round_base):
    out = df.copy()
    count_cols = [c for c in COUNT_COLUMNS if c in out.columns]
    unsafe = pd.Series(False, index=out.index)

    for col in count_cols:
        unsafe |= _small(out[col], threshold)

    for col in [c for c in DERIVED_COLUMNS if c in out.columns]:
        out.loc[unsafe, col] = np.nan

    for col in count_cols:
        out.loc[_small(out[col], threshold), col] = np.nan
        if round_base > 1:
            x = _numeric(out[col])
            out[col] = np.where(x.notna(), (x / round_base).round() * round_base, out[col])

    # Mask detailed labels when their supporting cells are small.
    if "count" in out.columns:
        cell_small = _small(out["count"], threshold)
        for label in ("value", "left_value", "right_value", "pattern"):
            if label in out.columns:
                out[label] = out[label].astype("object")
                out.loc[cell_small, label] = "__SUPPRESSED__"

    return out


def prepare_egress(internal_dir, export_dir, threshold, round_base, bundle_path):
    internal_dir = Path(internal_dir)
    export_dir = Path(export_dir)
    bundle_path = Path(bundle_path)

    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True)

    for source in sorted(internal_dir.glob("*.csv")):
        try:
            df = pd.read_csv(source, low_memory=False)
        except pd.errors.EmptyDataError:
            (export_dir / source.name).write_text("", encoding="utf-8")
            continue

        protect_frame(df, threshold, round_base).to_csv(export_dir / source.name, index=False)

    # portable metadata is reconstructed only from disclosure-controlled CSVs.
    tables = {}
    keys_path = export_dir / OUTPUTS["keys"]
    if keys_path.exists() and keys_path.stat().st_size:
        keys = pd.read_csv(keys_path)
        for _, row in keys.iterrows():
            table = row["table"]
            tables[table] = {
                "family": row.get("family"),
                "patient_key": row.get("patient_key"),
                "event_key": row.get("event_key"),
            }

    for key, filename in OUTPUTS.items():
        if key in {"keys", "cross_table_relationships"}:
            continue
        path = export_dir / filename
        if not path.exists() or not path.stat().st_size:
            continue
        try:
            frame = pd.read_csv(path, low_memory=False)
        except pd.errors.EmptyDataError:
            continue
        if "table" not in frame.columns:
            continue
        for table in tables:
            tables[table][key] = (
                frame[frame["table"] == table]
                .where(pd.notna(frame[frame["table"] == table]), None)
                .to_dict(orient="records")
            )

    cross = []
    cross_path = export_dir / OUTPUTS["cross_table_relationships"]
    if cross_path.exists() and cross_path.stat().st_size:
        try:
            frame = pd.read_csv(cross_path, low_memory=False)
            cross = frame.where(pd.notna(frame), None).to_dict(orient="records")
        except pd.errors.EmptyDataError:
            pass

    save_json({
        "metadata_format": "dynsim_tre_eda_calibration_v1",
        "source_type": "disclosure_controlled_aggregate_eda_profile",
        "tables": tables,
        "cross_table_relationships": cross,
    }, export_dir / "portable_metadata.json")

    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    if bundle_path.exists():
        bundle_path.unlink()

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(export_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(export_dir))

    return bundle_path
