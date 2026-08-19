from itertools import combinations

import numpy as np
import pandas as pd

from .utils import (
    count_summary,
    datetime_candidate,
    detect_numbered_group,
    identifier_score,
    numeric_summary,
    probable_free_text,
)


def profile_table_inventory(table_name, df, source_path):
    return {
        "table": table_name,
        "source_file": source_path.name,
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "missing_cells": int(df.isna().sum().sum()),
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "fully_blank_rows": int(df.isna().all(axis=1).sum()),
    }


def profile_columns(table_name, df, settings):
    rows = []
    identifier_rows = []
    datetime_rows = []
    numeric_rows = []
    categorical_rows = []
    slot_rows = []

    sample_rows = settings["sample_rows_for_type_detection"]
    dt_threshold = settings["datetime_parse_threshold"]

    for position, column in enumerate(df.columns):
        s = df[column]
        missing_n = int(s.isna().sum())
        nonmissing_n = int(s.notna().sum())
        unique_n = int(s.nunique(dropna=True))
        unique_ratio = unique_n / nonmissing_n if nonmissing_n else 0.0

        is_dt, dt_success = datetime_candidate(
            s, column, sample_rows, dt_threshold
        )
        is_num = pd.api.types.is_numeric_dtype(s) and not is_dt
        free_text = probable_free_text(
            s,
            settings["free_text_mean_length_threshold"],
            settings["free_text_unique_ratio_threshold"],
        ) if not is_num and not is_dt else False

        if is_dt:
            inferred_kind = "datetime"
        elif is_num:
            inferred_kind = "numeric"
        elif free_text:
            inferred_kind = "free_text"
        else:
            inferred_kind = "string_or_categorical"

        score, id_meta = identifier_score(s, column)
        if is_dt:
            score, id_meta = 0.0, {}
        elif free_text and not id_meta.get("strong_name_token_match", False):
            score, id_meta = 0.0, {}

        rows.append({
            "table": table_name,
            "position": position,
            "column": column,
            "source_dtype": str(s.dtype),
            "inferred_kind": inferred_kind,
            "missing_n": missing_n,
            "missing_pct": (missing_n / len(df) * 100) if len(df) else 0.0,
            "nonmissing_n": nonmissing_n,
            "unique_n": unique_n,
            "unique_ratio": unique_ratio,
            "datetime_parse_success": dt_success,
            "probable_free_text": bool(free_text),
            "identifier_score": score,
        })

        if score >= settings["identifier_min_score"]:
            identifier_rows.append({
                "table": table_name,
                "column": column,
                "score": score,
                **id_meta,
            })

        if is_dt:
            parsed = pd.to_datetime(s, errors="coerce", dayfirst=True, format="mixed")
            valid = parsed.dropna()
            datetime_rows.append({
                "table": table_name,
                "column": column,
                "n": int(len(valid)),
                "missing_n": int(parsed.isna().sum()),
                "min": valid.min() if not valid.empty else pd.NaT,
                "max": valid.max() if not valid.empty else pd.NaT,
                "parse_success": dt_success,
            })

        if is_num:
            summary = numeric_summary(s)
            if summary:
                numeric_rows.append({"table": table_name, "column": column, **summary})

        if (
            not is_dt
            and not free_text
            and nonmissing_n > 0
            and (
                unique_n <= settings["categorical_max_unique"]
                or unique_ratio <= settings["categorical_max_unique_ratio"]
            )
        ):
            counts = s.astype("string").value_counts(dropna=False)
            for value, count in counts.items():
                categorical_rows.append({
                    "table": table_name,
                    "column": column,
                    "value": "<MISSING>" if pd.isna(value) else str(value),
                    "count": int(count),
                    "pct": float(count / len(df) * 100) if len(df) else 0.0,
                })

        slot = detect_numbered_group(column)
        if slot and slot["suffix"] == "":
            slot_rows.append({
                "table": table_name,
                "group": slot["group"],
                "slot": slot["slot"],
                "column": column,
                "nonmissing_n": nonmissing_n,
                "occupancy_pct": float(nonmissing_n / len(df) * 100) if len(df) else 0.0,
            })

    identifiers = pd.DataFrame(identifier_rows)
    if not identifiers.empty:
        identifiers = (
            identifiers.sort_values(["table", "score", "unique_ratio"], ascending=[True, False, False])
            .groupby("table", as_index=False, group_keys=False)
            .head(settings["identifier_max_candidates_per_table"])
            .reset_index(drop=True)
        )

    return {
        "columns": pd.DataFrame(rows),
        "identifiers": identifiers,
        "numeric": pd.DataFrame(numeric_rows),
        "categorical": pd.DataFrame(categorical_rows),
        "datetime": pd.DataFrame(datetime_rows),
        "slots": pd.DataFrame(slot_rows),
    }


def profile_identifier_burden(table_name, df, identifier_candidates):
    rows = []
    if identifier_candidates.empty:
        return pd.DataFrame(rows)

    for column in identifier_candidates["column"].tolist():
        if column not in df.columns:
            continue
        counts = df.groupby(column, dropna=True).size()
        summary = count_summary(counts)
        if summary:
            rows.append({
                "table": table_name,
                "identifier_column": column,
                "metric": "rows_per_identifier",
                **summary,
            })
    return pd.DataFrame(rows)


def profile_within_table_links(table_name, df, identifier_candidates):
    rows = []
    if identifier_candidates.empty or "column" not in identifier_candidates.columns:
        return pd.DataFrame(rows)
    cols = [c for c in identifier_candidates["column"].tolist() if c in df.columns]
    for a, b in combinations(cols, 2):
        subset = df[[a, b]].dropna()
        if subset.empty:
            continue

        a_to_b = subset.groupby(a)[b].nunique()
        b_to_a = subset.groupby(b)[a].nunique()

        rows.append({
            "table": table_name,
            "left_column": a,
            "right_column": b,
            "joint_rows": int(len(subset)),
            "left_unique": int(subset[a].nunique()),
            "right_unique": int(subset[b].nunique()),
            "left_maps_to_one_right_pct": float((a_to_b == 1).mean() * 100),
            "right_maps_to_one_left_pct": float((b_to_a == 1).mean() * 100),
            "max_right_per_left": int(a_to_b.max()) if len(a_to_b) else 0,
            "max_left_per_right": int(b_to_a.max()) if len(b_to_a) else 0,
        })
    return pd.DataFrame(rows)


def profile_temporal_intervals(table_name, df, datetime_columns, max_columns):
    rows = []
    columns = datetime_columns["column"].tolist()[:max_columns] if not datetime_columns.empty else []
    parsed = {
        col: pd.to_datetime(df[col], errors="coerce", dayfirst=True, format="mixed")
        for col in columns if col in df.columns
    }

    for left, right in combinations(parsed.keys(), 2):
        mask = parsed[left].notna() & parsed[right].notna()
        if not mask.any():
            continue
        days = (parsed[right][mask] - parsed[left][mask]).dt.total_seconds() / 86400.0
        summary = numeric_summary(days)
        if summary:
            rows.append({
                "table": table_name,
                "left_datetime": left,
                "right_datetime": right,
                "negative_n": int((days < 0).sum()),
                "zero_n": int((days == 0).sum()),
                **summary,
            })
    return pd.DataFrame(rows)


def profile_repeat_gaps(table_name, df, identifiers, datetime_columns, max_ids):
    rows = []
    if identifiers.empty or datetime_columns.empty:
        return pd.DataFrame(rows)

    id_columns = identifiers["column"].tolist()[:max_ids]
    date_columns = datetime_columns["column"].tolist()

    for id_col in id_columns:
        for date_col in date_columns:
            if id_col == date_col:
                continue
            if id_col not in df.columns or date_col not in df.columns:
                continue

            work = df[[id_col, date_col]].copy()
            work[date_col] = pd.to_datetime(
                work[date_col], errors="coerce", dayfirst=True, format="mixed"
            )
            work = work.dropna().sort_values([id_col, date_col])
            if work.empty:
                continue

            gaps = work.groupby(id_col)[date_col].diff().dt.total_seconds() / 86400.0
            valid = gaps.dropna()
            if valid.empty:
                continue

            summary = numeric_summary(valid)
            rows.append({
                "table": table_name,
                "identifier_column": id_col,
                "datetime_column": date_col,
                "same_day_n": int((valid < 1).sum()),
                "within_7d_n": int((valid <= 7).sum()),
                "within_30d_n": int((valid <= 30).sum()),
                **summary,
            })

    return pd.DataFrame(rows)
