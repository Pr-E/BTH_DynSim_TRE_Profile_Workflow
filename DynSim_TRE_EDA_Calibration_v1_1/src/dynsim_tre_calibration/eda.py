"""Core exploratory data analysis and table-family calibration routines.

The EDA preserves source grain long enough to measure duplicates, key quality
and chronology, then creates analysis views at the appropriate pathway, spell
or attendance grain for aggregate profiling.
"""

from itertools import combinations

import numpy as np
import pandas as pd

from .dependencies import (
    categorical_associations,
    categorical_joint,
    missingness_profiles,
    numeric_correlations,
)
from .discovery import date_candidates, find_named_column
from .utils import count_distribution, numbered_slot, nonnegative_interval_stats, numeric_stats


def _append(table, rows, **values):
    rows.append({"table": table, **values})


def schema_profile(table, df):
    """Describe source column order, dtype, missingness and cardinality without modifying the table."""
    rows = []
    for position, column in enumerate(df.columns):
        _append(
            table,
            rows,
            position=position,
            column=column,
            dtype=str(df[column].dtype),
            non_missing_n=int(df[column].notna().sum()),
            missing_n=int(df[column].isna().sum()),
            missing_pct=float(df[column].isna().mean() * 100),
            unique_n=int(df[column].nunique(dropna=True)),
        )
    return pd.DataFrame(rows)


def table_inventory(table, df, patient_key=None, event_key=None):
    """Record raw table grain, duplicate burden and resolved-key coverage."""
    row = {
        "table": table,
        "rows_raw": int(len(df)),
        "columns": int(df.shape[1]),
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "fully_blank_rows": int(df.isna().all(axis=1).sum()),
    }
    if patient_key and patient_key in df.columns:
        row["patient_key"] = patient_key
        row["unique_patients_raw"] = int(df[patient_key].nunique(dropna=True))
        row["missing_patient_key_n"] = int(df[patient_key].isna().sum())
    if event_key and event_key in df.columns:
        row["event_key"] = event_key
        row["unique_events_raw"] = int(df[event_key].nunique(dropna=True))
        row["missing_event_key_n"] = int(df[event_key].isna().sum())
    return pd.DataFrame([row])


def _profile_numeric(table, frame, excluded):
    """Profile eligible numeric columns while excluding identifiers and derived helper dates."""
    rows = []
    numeric_cols = []
    for column in frame.columns:
        if column in excluded or column.endswith("_dt"):
            continue
        if not pd.api.types.is_numeric_dtype(frame[column]):
            continue
        stats = numeric_stats(frame[column])
        if stats:
            numeric_cols.append(column)
            _append(table, rows, column=column, **stats)
    return pd.DataFrame(rows), numeric_cols


def _profile_categories(table, frame, excluded, full_max_unique, top_n):
    """Profile full or top-N categorical distributions according to configured cardinality limits."""
    rows = []
    categorical_cols = []

    for column in frame.columns:
        if column in excluded or column.endswith("_dt"):
            continue
        if pd.api.types.is_numeric_dtype(frame[column]):
            continue

        nonmissing = frame[column].dropna()
        if nonmissing.empty:
            continue

        unique_n = int(nonmissing.nunique())
        categorical_cols.append(column)
        counts = frame[column].fillna("<MISSING>").astype(str).value_counts()

        if unique_n <= full_max_unique:
            chosen = counts
            mode = "full"
        else:
            chosen = counts.head(top_n)
            mode = "top_n"

        denominator = len(frame)
        for value, count in chosen.items():
            _append(
                table,
                rows,
                column=column,
                value=str(value),
                count=int(count),
                pct=float(count / denominator * 100) if denominator else np.nan,
                profile_mode=mode,
                column_unique_n=unique_n,
            )

        if mode == "top_n" and len(counts) > len(chosen):
            other_n = int(counts.iloc[len(chosen):].sum())
            _append(
                table,
                rows,
                column=column,
                value="__OTHER__",
                count=other_n,
                pct=float(other_n / denominator * 100) if denominator else np.nan,
                profile_mode=mode,
                column_unique_n=unique_n,
            )

    return pd.DataFrame(rows), categorical_cols


def _profile_seasonality(table, parsed):
    """Summarise aggregate calendar patterns for each recognised datetime field."""
    rows = []
    for column, values in parsed.items():
        s = values.dropna()
        if s.empty:
            continue

        dimensions = {
            "year": s.dt.year.astype("Int64").astype(str),
            "year_month": s.dt.to_period("M").astype(str),
            "month_of_year": s.dt.month.astype("Int64").astype(str),
            "day_of_week": s.dt.day_name(),
        }
        if s.dt.hour.nunique() > 1 or (s.dt.hour != 0).any():
            dimensions["hour_of_day"] = s.dt.hour.astype("Int64").astype(str)

        for dimension, vals in dimensions.items():
            counts = vals.value_counts().sort_index()
            total = int(counts.sum())
            for value, count in counts.items():
                _append(
                    table,
                    rows,
                    column=column,
                    dimension=dimension,
                    value=str(value),
                    count=int(count),
                    pct=float(count / total * 100) if total else np.nan,
                )

    return pd.DataFrame(rows)


def _slot_profile(table, frame):
    """Measure population of numbered repeated fields such as diagnosis/procedure slots."""
    rows = []
    for column in frame.columns:
        slot = numbered_slot(column)
        if not slot:
            continue
        group, number = slot
        # Description columns are intentionally excluded from occupancy calibration.
        if str(column).lower().endswith(("_des", "_desc", "_description")):
            continue
        _append(
            table,
            rows,
            group=group,
            slot=number,
            column=column,
            populated_n=int(frame[column].notna().sum()),
            populated_pct=float(frame[column].notna().mean() * 100),
            unique_n=int(frame[column].nunique(dropna=True)),
        )
    return pd.DataFrame(rows)


def _consistency(table, frame, patient_key, excluded):
    """Measure whether low-cardinality attributes remain stable within a resolved patient."""
    rows = []
    if not patient_key or patient_key not in frame.columns:
        return pd.DataFrame(rows)

    for column in frame.columns:
        if column == patient_key or column in excluded or column.endswith("_dt"):
            continue
        if frame[column].nunique(dropna=True) > 200:
            continue

        grouped = frame.groupby(patient_key)[column].nunique(dropna=True)
        _append(
            table,
            rows,
            column=column,
            patients_with_multiple_values_n=int((grouped > 1).sum()),
            patients_profiled_n=int(len(grouped)),
            pct_with_multiple_values=float((grouped > 1).mean() * 100) if len(grouped) else np.nan,
        )
    return pd.DataFrame(rows)


def _pair_interval(table, name, values):
    """Wrap non-negative interval statistics in a standard one-row profile."""
    return pd.DataFrame([{"table": table, "metric": name, **nonnegative_interval_stats(values)}])


def analyse_pathway(table, df, patient_key, settings, date_threshold):
    """Profile pathway grain, repeat referrals, timing intervals and chronology QA."""
    # Use a duplicate-free pathway view for behavioural summaries; raw duplicate counts remain in inventory.
    clean = df.drop_duplicates().copy()
    date_profile, parsed = date_candidates(clean, date_threshold)
    for column, values in parsed.items():
        clean[column + "_dt"] = values

    count_summaries = []
    count_distributions = []
    interval_rows = []
    temporal_qa = []

    referral_key = find_named_column(clean, ("referral", "id"))
    if patient_key and patient_key in clean.columns:
        if referral_key:
            per_patient = clean.groupby(patient_key)[referral_key].nunique()
        else:
            per_patient = clean.groupby(patient_key).size()

        stats = numeric_stats(per_patient)
        if stats:
            count_summaries.append({
                "table": table,
                "metric": "referrals_or_rows_per_patient",
                "entity_type": "patient",
                **stats,
                "n_gt_1": int((per_patient > 1).sum()),
                "pct_gt_1": float((per_patient > 1).mean() * 100),
            })
        dist = count_distribution(per_patient, "referrals_or_rows_per_patient", "patient")
        if not dist.empty:
            dist.insert(0, "table", table)
            count_distributions.append(dist)

    referral_col = find_named_column(clean, ("first", "referral", "date"))
    first_col = find_named_column(clean, ("first", "msk"))
    last_col = find_named_column(clean, ("last", "msk"))

    referral_dt = clean.get(referral_col + "_dt") if referral_col else None
    first_dt = clean.get(first_col + "_dt") if first_col else None
    last_dt = clean.get(last_col + "_dt") if last_col else None

    if patient_key and referral_dt is not None:
        timing = pd.DataFrame({
            patient_key: clean[patient_key],
            "referral": referral_dt,
        }).dropna().sort_values([patient_key, "referral"])
        gaps = timing.groupby(patient_key)["referral"].diff().dt.total_seconds() / 86400
        interval_rows.append(_pair_interval(table, "repeat_referral_gap_days", gaps))

    if referral_dt is not None and first_dt is not None:
        interval_rows.append(_pair_interval(table, "referral_to_first_days", (first_dt - referral_dt).dt.total_seconds() / 86400))
        temporal_qa.append({
            "table": table,
            "check": "first_before_referral",
            "count": int(((first_dt < referral_dt) & first_dt.notna() & referral_dt.notna()).sum()),
        })

    if first_dt is not None and last_dt is not None:
        interval_rows.append(_pair_interval(table, "first_to_last_days", (last_dt - first_dt).dt.total_seconds() / 86400))
        temporal_qa.append({
            "table": table,
            "check": "last_before_first",
            "count": int(((last_dt < first_dt) & last_dt.notna() & first_dt.notna()).sum()),
        })

    if referral_dt is not None and last_dt is not None:
        interval_rows.append(_pair_interval(table, "referral_to_last_days", (last_dt - referral_dt).dt.total_seconds() / 86400))
        temporal_qa.append({
            "table": table,
            "check": "last_before_referral",
            "count": int(((last_dt < referral_dt) & last_dt.notna() & referral_dt.notna()).sum()),
        })

    return {
        "analysis_view": clean,
        "count_summaries": pd.DataFrame(count_summaries),
        "count_distributions": pd.concat(count_distributions, ignore_index=True) if count_distributions else pd.DataFrame(),
        "dates": date_profile.assign(table=table),
        "intervals": pd.concat(interval_rows, ignore_index=True) if interval_rows else pd.DataFrame(),
        "temporal_qa": pd.DataFrame(temporal_qa),
    }


def analyse_inpatient(table, df, patient_key, settings, date_threshold):
    """Profile inpatient episode/spell hierarchy, utilisation burden, LOS and chronology QA."""
    # Completely blank rows carry no clinical/event information but their raw burden is retained in inventory.
    populated = df.loc[~df.isna().all(axis=1)].copy()
    names = {str(c).lower(): c for c in populated.columns}
    spell_key = names.get("spellid")
    episode_key = names.get("episodeid")

    date_profile, parsed = date_candidates(populated, date_threshold)
    for column, values in parsed.items():
        populated[column + "_dt"] = values

    count_summaries = []
    count_distributions = []
    key_qa = []
    intervals = []
    temporal_qa = []

    if spell_key and patient_key:
        # A valid inpatient spell should normally map to one patient; violations are surfaced as QA, not silently fixed.
        nesting = populated.dropna(subset=[spell_key, patient_key]).groupby(spell_key)[patient_key].nunique()
        key_qa.append({
            "table": table,
            "left_key": spell_key,
            "right_key": patient_key,
            "relationship": "spell_to_patient",
            "left_entities_n": int(len(nesting)),
            "left_linked_to_one_right_n": int((nesting == 1).sum()),
            "left_linked_to_multiple_right_n": int((nesting > 1).sum()),
            "max_right_per_left": int(nesting.max()) if len(nesting) else 0,
        })

    if episode_key:
        episode_counts = populated[episode_key].dropna().value_counts()
        repeated = episode_counts[episode_counts > 1]
        key_qa.append({
            "table": table,
            "left_key": episode_key,
            "right_key": None,
            "relationship": "episode_id_uniqueness",
            "duplicate_id_values_n": int(len(repeated)),
            "rows_with_repeated_id_n": int(repeated.sum()) if len(repeated) else 0,
            "max_rows_per_id": int(episode_counts.max()) if len(episode_counts) else 0,
        })

    if spell_key and episode_key:
        per_spell = populated.dropna(subset=[spell_key, episode_key]).groupby(spell_key)[episode_key].nunique()
        stats = numeric_stats(per_spell)
        if stats:
            count_summaries.append({
                "table": table,
                "metric": "episodes_per_spell",
                "entity_type": "spell",
                **stats,
                "n_gt_1": int((per_spell > 1).sum()),
                "pct_gt_1": float((per_spell > 1).mean() * 100),
            })
        dist = count_distribution(per_spell, "episodes_per_spell", "spell")
        if not dist.empty:
            dist.insert(0, "table", table)
            count_distributions.append(dist)

    if spell_key and patient_key:
        per_patient = populated.dropna(subset=[patient_key, spell_key]).groupby(patient_key)[spell_key].nunique()
        stats = numeric_stats(per_patient)
        if stats:
            count_summaries.append({
                "table": table,
                "metric": "spells_per_patient",
                "entity_type": "patient",
                **stats,
                "n_gt_1": int((per_patient > 1).sum()),
                "pct_gt_1": float((per_patient > 1).mean() * 100),
            })
        dist = count_distribution(per_patient, "spells_per_patient", "patient")
        if not dist.empty:
            dist.insert(0, "table", table)
            count_distributions.append(dist)

    admission_col = find_named_column(populated, ("admission", "date"))
    discharge_col = find_named_column(populated, ("discharge", "date"))
    episode_start_col = find_named_column(populated, ("episode", "start"))
    episode_end_col = find_named_column(populated, ("episode", "end"))

    admission = populated.get(admission_col + "_dt") if admission_col else None
    discharge = populated.get(discharge_col + "_dt") if discharge_col else None
    episode_start = populated.get(episode_start_col + "_dt") if episode_start_col else None
    episode_end = populated.get(episode_end_col + "_dt") if episode_end_col else None

    if admission is not None and discharge is not None:
        temporal_qa.append({
            "table": table,
            "check": "discharge_before_admission",
            "count": int(((discharge < admission) & discharge.notna() & admission.notna()).sum()),
        })

        if spell_key:
            spell_dates = pd.DataFrame({
                spell_key: populated[spell_key],
                "admission": admission,
                "discharge": discharge,
            }).dropna(subset=[spell_key]).groupby(spell_key).agg(
                admission=("admission", "min"),
                discharge=("discharge", "max"),
            )
            los = (spell_dates["discharge"] - spell_dates["admission"]).dt.total_seconds() / 86400
            intervals.append(_pair_interval(table, "spell_los_days", los))

    if episode_start is not None and episode_end is not None:
        temporal_qa.append({
            "table": table,
            "check": "episode_end_before_start",
            "count": int(((episode_end < episode_start) & episode_end.notna() & episode_start.notna()).sum()),
        })
    if episode_start is not None and admission is not None:
        temporal_qa.append({
            "table": table,
            "check": "episode_start_before_admission",
            "count": int(((episode_start < admission) & episode_start.notna() & admission.notna()).sum()),
        })
    if episode_end is not None and discharge is not None:
        temporal_qa.append({
            "table": table,
            "check": "episode_end_after_discharge",
            "count": int(((episode_end > discharge) & episode_end.notna() & discharge.notna()).sum()),
        })

    # Build the calibration view at episode grain while retaining raw populated rows for duplicate/key QA.
    episode_view = populated
    if episode_key:
        sort_cols = [episode_key] + ([episode_start_col + "_dt"] if episode_start_col else [])
        episode_view = populated.sort_values(sort_cols).drop_duplicates(episode_key, keep="first").copy()

    return {
        "analysis_view": episode_view,
        "raw_analysis_view": populated,
        "count_summaries": pd.DataFrame(count_summaries),
        "count_distributions": pd.concat(count_distributions, ignore_index=True) if count_distributions else pd.DataFrame(),
        "key_qa": pd.DataFrame(key_qa),
        "dates": date_profile.assign(table=table),
        "intervals": pd.concat(intervals, ignore_index=True) if intervals else pd.DataFrame(),
        "temporal_qa": pd.DataFrame(temporal_qa),
    }


def analyse_ed(table, df, patient_key, event_key, settings, date_threshold):
    """Profile ED attendance grain, composite-key integrity, utilisation burden and timing QA."""
    # Remove exact duplicate rows first; the residual patient/event-key check below detects non-identical duplicates.
    clean = df.drop_duplicates().copy()
    key_qa = []

    if patient_key and event_key:
        composite = clean.groupby([patient_key, event_key]).size()
        key_qa.append({
            "table": table,
            "left_key": patient_key,
            "right_key": event_key,
            "relationship": "patient_event_composite",
            "joint_combinations_n": int(len(composite)),
            "combinations_gt_1_n": int((composite > 1).sum()),
            "max_rows_per_combination": int(composite.max()) if len(composite) else 0,
        })

    # Downstream ED utilisation is calibrated at attendance/event grain, not raw row grain.
    attendance = clean
    if event_key:
        attendance = clean.drop_duplicates(event_key, keep="first").copy()

    date_profile, parsed = date_candidates(attendance, date_threshold)
    for column, values in parsed.items():
        attendance[column + "_dt"] = values

    count_summaries = []
    count_distributions = []
    intervals = []
    temporal_qa = []

    if patient_key and event_key:
        per_patient = attendance.groupby(patient_key)[event_key].nunique()
        stats = numeric_stats(per_patient)
        if stats:
            count_summaries.append({
                "table": table,
                "metric": "attendances_per_patient",
                "entity_type": "patient",
                **stats,
                "n_gt_1": int((per_patient > 1).sum()),
                "pct_gt_1": float((per_patient > 1).mean() * 100),
            })
        dist = count_distribution(per_patient, "attendances_per_patient", "patient")
        if not dist.empty:
            dist.insert(0, "table", table)
            count_distributions.append(dist)

    arrival_col = find_named_column(attendance, ("arrival",))
    departure_col = find_named_column(attendance, ("departure",))
    arrival = attendance.get(arrival_col + "_dt") if arrival_col else None
    departure = attendance.get(departure_col + "_dt") if departure_col else None

    if arrival is not None and departure is not None:
        temporal_qa.append({
            "table": table,
            "check": "departure_before_arrival",
            "count": int(((departure < arrival) & departure.notna() & arrival.notna()).sum()),
        })
        intervals.append(_pair_interval(
            table,
            "arrival_to_departure_minutes",
            (departure - arrival).dt.total_seconds() / 60,
        ))

    if patient_key and arrival is not None:
        timing = pd.DataFrame({
            patient_key: attendance[patient_key],
            "arrival": arrival,
        }).dropna().sort_values([patient_key, "arrival"])
        gaps = timing.groupby(patient_key)["arrival"].diff().dt.total_seconds() / 86400
        intervals.append(_pair_interval(table, "repeat_attendance_gap_days", gaps))

    return {
        "analysis_view": attendance,
        "raw_analysis_view": clean,
        "count_summaries": pd.DataFrame(count_summaries),
        "count_distributions": pd.concat(count_distributions, ignore_index=True) if count_distributions else pd.DataFrame(),
        "key_qa": pd.DataFrame(key_qa),
        "dates": date_profile.assign(table=table),
        "intervals": pd.concat(intervals, ignore_index=True) if intervals else pd.DataFrame(),
        "temporal_qa": pd.DataFrame(temporal_qa),
    }


def analyse_generic(table, df, patient_key, settings, date_threshold):
    """Provide baseline profiling for tables that do not match a specialist family."""
    clean = df.drop_duplicates().copy()
    dates, parsed = date_candidates(clean, date_threshold)
    for column, values in parsed.items():
        clean[column + "_dt"] = values

    return {
        "analysis_view": clean,
        "dates": dates.assign(table=table),
        "count_summaries": pd.DataFrame(),
        "count_distributions": pd.DataFrame(),
        "intervals": pd.DataFrame(),
        "temporal_qa": pd.DataFrame(),
        "key_qa": pd.DataFrame(),
    }



def _anomaly_candidates(table, frame, parsed_dates, excluded):
    """Identify aggregate anomaly candidates without project-specific values.

    Candidates are retained for data-quality review and synthetic calibration;
    they are not automatically classified as clinically invalid.
    """
    rows = []

    for column in frame.columns:
        if column in excluded or column.endswith("_dt"):
            continue
        if not pd.api.types.is_numeric_dtype(frame[column]):
            continue

        s = pd.to_numeric(frame[column], errors="coerce").dropna()
        if len(s) < 4 or s.nunique() < 2:
            continue

        q1 = float(s.quantile(0.25))
        q3 = float(s.quantile(0.75))
        iqr = q3 - q1
        if iqr <= 0:
            continue

        high = float(s.max())
        low = float(s.min())

        # A deliberately conservative 10×IQR rule flags candidates for review without labelling them invalid.
        if high > q3 + 10 * iqr:
            rows.append({
                "table": table,
                "anomaly_type": "numeric_extreme_high",
                "column": column,
                "value": high,
                "count": int((s == high).sum()),
                "reference_q1": q1,
                "reference_q3": q3,
                "reference_iqr": iqr,
            })

        if low < q1 - 10 * iqr:
            rows.append({
                "table": table,
                "anomaly_type": "numeric_extreme_low",
                "column": column,
                "value": low,
                "count": int((s == low).sum()),
                "reference_q1": q1,
                "reference_q3": q3,
                "reference_iqr": iqr,
            })

    for column, values in parsed_dates.items():
        low_name = str(column).lower()
        if low_name.endswith("_dt") or "birth" in low_name or "death" in low_name:
            continue
        years = values.dropna().dt.year.value_counts().sort_index()
        if len(years) < 2:
            continue

        year_values = years.index.to_numpy(dtype=int)
        earliest_gap = int(year_values[1] - year_values[0])
        latest_gap = int(year_values[-1] - year_values[-2])

        # Large isolated year gaps can indicate date sentinels; DOB/DOD fields are excluded above by design.
        if earliest_gap >= 5:
            rows.append({
                "table": table,
                "anomaly_type": "isolated_early_year",
                "column": column,
                "value": int(year_values[0]),
                "count": int(years.iloc[0]),
                "reference_gap": earliest_gap,
            })

        if latest_gap >= 5:
            rows.append({
                "table": table,
                "anomaly_type": "isolated_late_year",
                "column": column,
                "value": int(year_values[-1]),
                "count": int(years.iloc[-1]),
                "reference_gap": latest_gap,
            })

    return pd.DataFrame(rows)

def complete_table_eda(table, state, settings, discovery_settings):
    """Run family-specific EDA, then add common statistical, missingness and dependency profiles."""
    df = state["raw"]
    family = state["family"]
    patient_key = state["patient_key"]
    event_key = state["event_key"]
    date_threshold = discovery_settings["datetime_parse_threshold"]

    if family == "pathway":
        result = analyse_pathway(table, df, patient_key, settings, date_threshold)
    elif family == "inpatient":
        result = analyse_inpatient(table, df, patient_key, settings, date_threshold)
    elif family == "ed":
        result = analyse_ed(table, df, patient_key, event_key, settings, date_threshold)
    else:
        result = analyse_generic(table, df, patient_key, settings, date_threshold)

    view = result["analysis_view"]
    # Identifiers are excluded from ordinary marginal/dependency profiling to avoid treating IDs as measurements.
    excluded = {x for x in (patient_key, event_key) if x}
    excluded.update(state["identifier_candidates"]["column"].tolist())

    numeric, numeric_cols = _profile_numeric(table, view, excluded)
    categorical, categorical_cols = _profile_categories(
        table,
        view,
        excluded,
        settings["categorical_full_max_unique"],
        settings["top_n"],
    )

    dates, parsed = date_candidates(view, date_threshold)
    dates["table"] = table

    result.update({
        "inventory": table_inventory(table, df, patient_key, event_key),
        "schema": schema_profile(table, df),
        "numeric": numeric,
        "categorical": categorical,
        "dates": dates,
        "seasonality": _profile_seasonality(table, parsed),
        "slots": _slot_profile(table, view),
        "within_patient_consistency": _consistency(table, view, patient_key, excluded),
        "anomaly_candidates": _anomaly_candidates(
            table,
            view,
            parsed,
            excluded,
        ),
    })

    # Helper *_dt columns are derivations, so missingness is measured only on source/analysis fields.
    row_missing, missing_pairs, missing_patterns = missingness_profiles(
        table,
        view.drop(columns=[c for c in view.columns if c.endswith("_dt")], errors="ignore"),
        settings["max_missingness_columns"],
        settings["max_missingness_patterns"],
    )
    result["row_missingness"] = row_missing
    result["missingness_pairs"] = missing_pairs
    result["missingness_patterns"] = missing_patterns

    result["numeric_correlations"] = numeric_correlations(
        table,
        view,
        numeric_cols,
        settings["min_pairwise_n"],
        settings["max_dependency_numeric_columns"],
    )

    # First rank all eligible categorical pairs, then retain detailed joint cells only for strong pairs.
    associations = categorical_associations(
        table,
        view,
        categorical_cols,
        settings["min_pairwise_n"],
        settings["max_dependency_categorical_columns"],
        settings["max_dependency_levels"],
    )
    result["categorical_associations"] = associations
    result["categorical_joint"] = categorical_joint(
        table,
        view,
        associations,
        settings["max_joint_dependency_pairs"],
        settings["min_cramers_v_for_joint_profile"],
    )

    return result
