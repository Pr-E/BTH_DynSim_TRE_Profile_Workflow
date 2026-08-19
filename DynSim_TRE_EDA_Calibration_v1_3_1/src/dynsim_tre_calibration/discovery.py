from itertools import combinations

import pandas as pd

from .utils import identifier_score, is_date_candidate


def infer_family(df):
    cols = {str(c).lower() for c in df.columns}

    inpatient_score = sum(token in cols for token in ("spellid", "episodeid"))
    ed_score = sum(any(token in c for c in cols) for token in ("arrival", "departure", "emergency", "aereferral"))
    pathway_score = sum(any(token in c for c in cols) for token in ("firstmsk", "lastmsk", "referralobservation"))

    if inpatient_score >= 2:
        return "inpatient"
    if ed_score >= 2:
        return "ed"
    if pathway_score >= 2:
        return "pathway"
    return "generic"


def identifier_candidates(df, min_score, max_candidates):
    rows = []
    for column in df.columns:
        score = identifier_score(df[column], column)
        if score < min_score:
            continue
        nonmissing = int(df[column].notna().sum())
        unique = int(df[column].nunique(dropna=True))
        rows.append({
            "column": column,
            "score": score,
            "nonmissing_n": nonmissing,
            "unique_n": unique,
            "unique_ratio": unique / nonmissing if nonmissing else 0.0,
            "missing_n": int(df[column].isna().sum()),
        })

    if not rows:
        return pd.DataFrame(columns=["column", "score", "nonmissing_n", "unique_n", "unique_ratio", "missing_n"])

    return (
        pd.DataFrame(rows)
        .sort_values(["score", "unique_ratio"], ascending=[False, False])
        .head(max_candidates)
        .reset_index(drop=True)
    )


def date_candidates(df, threshold):
    rows = []
    parsed = {}
    for column in df.columns:
        is_date, rate = is_date_candidate(df[column], column, threshold)
        if not is_date:
            continue

        from .utils import to_datetime
        values, mode = to_datetime(df[column])
        parsed[column] = values
        rows.append({
            "column": column,
            "parse_mode": mode,
            "source_populated_n": int(df[column].notna().sum()),
            "parsed_n": int(values.notna().sum()),
            "parse_fail_n": int(df[column].notna().sum() - values.notna().sum()),
            "parse_success_pct": float(values.notna().sum() / df[column].notna().sum() * 100)
            if df[column].notna().sum() else None,
            "min": values.min(),
            "max": values.max(),
        })

    return pd.DataFrame(rows), parsed


def _values(df, column):
    return set(df[column].dropna().astype(str).unique())


def resolve_cross_table_patient_keys(table_states):
    """Resolve patient-like keys from cross-table structure without fixed column names.

    The score favours identifier-like/hash fields that recur across tables and have
    real cross-table overlap, while penalising record-level ID names such as spell,
    episode, referral and event identifiers.
    """
    table_names = list(table_states)
    selected = {}

    value_sets = {}
    for table, state in table_states.items():
        value_sets[table] = {
            col: _values(state["raw"], col)
            for col in state["identifier_candidates"]["column"].tolist()
            if col in state["raw"].columns
        }

    for name, state in table_states.items():
        ids = state["identifier_candidates"]
        if ids.empty:
            selected[name] = None
            continue

        best_col, best_score = None, float("-inf")

        for _, row in ids.iterrows():
            col = row["column"]
            values = value_sets[name].get(col, set())
            if not values:
                continue

            low = str(col).lower()
            semantic = 0.0
            if "hash" in low or "patient" in low or "person" in low or "nhs" in low:
                semantic += 3.0
            if any(token in low for token in ("spell", "episode", "referral", "attendance", "event", "observation")):
                semantic -= 2.0
            if "date" in low or "time" in low:
                semantic -= 5.0

            max_overlap_share = 0.0
            same_name_support = 0
            supported_tables = 0

            for other_name in table_names:
                if other_name == name:
                    continue

                other_best_overlap = 0.0
                for other_col, other_values in value_sets[other_name].items():
                    if not other_values:
                        continue
                    overlap = len(values & other_values)
                    if overlap == 0:
                        continue

                    share = overlap / max(1, min(len(values), len(other_values)))
                    other_best_overlap = max(other_best_overlap, share)

                    if str(other_col).lower() == low:
                        same_name_support += 1

                if other_best_overlap > 0:
                    supported_tables += 1
                    max_overlap_share = max(max_overlap_share, other_best_overlap)

            repeatability = 0.75 if float(row["unique_ratio"]) < 0.95 else 0.0
            score = (
                semantic
                + float(row["score"])
                + repeatability
                + 6.0 * max_overlap_share
                + 1.5 * supported_tables
                + 1.5 * same_name_support
            )

            if score > best_score:
                best_col, best_score = col, score

        selected[name] = best_col

    return selected


def resolve_event_key(df, family, ids, patient_key):
    if ids.empty:
        return None

    if family == "inpatient":
        names = {str(c).lower(): c for c in df.columns}
        for token in ("episodeid", "spellid"):
            if token in names:
                return names[token]

    candidates = ids[ids["column"] != patient_key].copy()
    if candidates.empty:
        return None

    candidates = candidates[
        ~candidates["column"].astype(str).str.lower().str.contains("date|time", regex=True)
    ].copy()
    if candidates.empty:
        return None

    def event_bonus(name):
        low = str(name).lower()
        bonus = 0.0
        if "id" in low or "identifier" in low or "observation" in low:
            bonus += 2.0
        if any(token in low for token in ("episode", "spell", "attendance", "attend", "event", "referral")):
            bonus += 1.5
        if "hash" in low:
            bonus += 0.5
        return bonus

    candidates["event_rank"] = (
        candidates["unique_ratio"] * 3
        + candidates["score"]
        + candidates["column"].map(event_bonus)
    )
    return candidates.sort_values("event_rank", ascending=False).iloc[0]["column"]


def find_named_column(df, tokens):
    for column in df.columns:
        low = str(column).lower()
        if all(token in low for token in tokens):
            return column
    return None
