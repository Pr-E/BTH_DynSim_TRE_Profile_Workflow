from pathlib import Path

import numpy as np
import pandas as pd

from .compiler import compile_portable_metadata


COUNT_COLUMNS = {
    "rows", "columns", "missing_cells", "exact_duplicate_rows", "fully_blank_rows",
    "missing_n", "nonmissing_n", "unique_n", "count", "n", "n_entities", "n_gt_1",
    "joint_rows", "left_unique", "right_unique", "max_right_per_left",
    "max_left_per_right", "negative_n", "zero_n", "same_day_n", "within_7d_n",
    "within_30d_n", "overlap_n"
}

SUMMARY_SUPPORT_COLUMNS = (
    "n", "n_entities", "joint_rows", "nonmissing_n", "overlap_n"
)

DERIVED_STAT_COLUMNS = {
    "mean", "sd", "min", "q1", "median", "q3", "p95", "p99", "max",
    "pct", "missing_pct", "unique_ratio", "datetime_parse_success",
    "parse_success", "pct_gt_1", "left_maps_to_one_right_pct",
    "right_maps_to_one_left_pct", "left_coverage_pct", "right_coverage_pct",
    "jaccard", "occupancy_pct"
}


def _numeric(series):
    return pd.to_numeric(series, errors="coerce")


def _unsafe_positive_small(series, min_cell_count):
    numeric = _numeric(series)
    return numeric.notna() & (numeric > 0) & (numeric < min_cell_count)


def _suppress_supported_summary_rows(df, min_cell_count):
    """Suppress derived statistics for rows supported by a small contributing count."""
    out = df.copy()
    support_cols = [c for c in SUMMARY_SUPPORT_COLUMNS if c in out.columns]
    if not support_cols:
        return out

    unsafe = pd.Series(False, index=out.index)
    for col in support_cols:
        unsafe |= _unsafe_positive_small(out[col], min_cell_count)

    if unsafe.any():
        derived = [c for c in DERIVED_STAT_COLUMNS if c in out.columns]
        count_cols = [c for c in COUNT_COLUMNS if c in out.columns]
        out.loc[unsafe, derived + count_cols] = np.nan

    return out


def _suppress_small_counts(df, min_cell_count):
    out = df.copy()
    for col in out.columns:
        if col not in COUNT_COLUMNS:
            continue
        mask = _unsafe_positive_small(out[col], min_cell_count)
        out.loc[mask, col] = np.nan
    return out


def _suppress_dependent_percentages(df, min_cell_count):
    """Suppress percentages/derived ratios whose supporting count is unsafe."""
    out = df.copy()

    if "count" in out.columns and "pct" in out.columns:
        unsafe = _unsafe_positive_small(out["count"], min_cell_count)
        out.loc[unsafe, "pct"] = np.nan

    if "n_gt_1" in out.columns and "pct_gt_1" in out.columns:
        unsafe = _unsafe_positive_small(out["n_gt_1"], min_cell_count)
        out.loc[unsafe, "pct_gt_1"] = np.nan

    if "overlap_n" in out.columns:
        unsafe = _unsafe_positive_small(out["overlap_n"], min_cell_count)
        for col in ("left_coverage_pct", "right_coverage_pct", "jaccard"):
            if col in out.columns:
                out.loc[unsafe, col] = np.nan

    return out


def _round_count_columns(df, round_base):
    if round_base <= 1:
        return df

    out = df.copy()
    for col in out.columns:
        if col not in COUNT_COLUMNS:
            continue
        numeric = _numeric(out[col])
        out[col] = np.where(
            numeric.notna(),
            (numeric / round_base).round() * round_base,
            out[col],
        )
    return out


def _generalise_datetime_bounds(df, granularity):
    out = df.copy()
    for col in ("min", "max"):
        if col not in out.columns:
            continue

        parsed = pd.to_datetime(out[col], errors="coerce")
        if granularity == "year":
            out[col] = parsed.dt.strftime("%Y")
        elif granularity == "month":
            out[col] = parsed.dt.strftime("%Y-%m")
        elif granularity == "day":
            out[col] = parsed.dt.strftime("%Y-%m-%d")
        else:
            raise ValueError("date_granularity must be one of: year, month, day")

    return out


def _collapse_small_categories(df, min_cell_count):
    """Collapse small categorical cells before generic suppression is applied."""
    if df.empty or "count" not in df.columns:
        return df

    work = df.copy()
    counts = _numeric(work["count"])
    small = counts.notna() & (counts > 0) & (counts < min_cell_count)

    safe = work.loc[~small].copy()
    grouped_rows = []

    if small.any():
        for (table, column), group in work.loc[small].groupby(["table", "column"]):
            grouped_count = int(_numeric(group["count"]).sum())
            grouped_pct = float(_numeric(group["pct"]).sum()) if "pct" in group else np.nan
            grouped_rows.append({
                "table": table,
                "column": column,
                "value": "__OTHER_OR_SUPPRESSED__",
                "count": grouped_count,
                "pct": grouped_pct,
            })

    out = pd.concat([safe, pd.DataFrame(grouped_rows)], ignore_index=True)

    if not out.empty and "count" in out.columns:
        unsafe = _unsafe_positive_small(out["count"], min_cell_count)
        out.loc[unsafe, "count"] = np.nan
        if "pct" in out.columns:
            out.loc[unsafe, "pct"] = np.nan

    return out


def create_export_profile(
    internal_dir,
    export_dir,
    min_cell_count,
    round_base=1,
    date_granularity="month",
):
    internal_dir = Path(internal_dir)
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    for source in sorted(internal_dir.glob("*.csv")):
        df = pd.read_csv(source, low_memory=False)

        if source.name == "categorical.csv":
            df = _collapse_small_categories(df, min_cell_count)

        if source.name == "datetime.csv":
            df = _generalise_datetime_bounds(df, date_granularity)

        df = _suppress_supported_summary_rows(df, min_cell_count)
        df = _suppress_dependent_percentages(df, min_cell_count)
        df = _suppress_small_counts(df, min_cell_count)
        df = _round_count_columns(df, round_base)

        df.to_csv(export_dir / source.name, index=False)

    compile_portable_metadata(
        export_dir,
        export_dir / "portable_metadata.json",
    )
    return export_dir
