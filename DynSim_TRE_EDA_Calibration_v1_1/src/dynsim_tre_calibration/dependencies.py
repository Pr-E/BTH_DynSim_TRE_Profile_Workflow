"""Profile aggregate dependencies between variables and missingness patterns.

The functions in this module produce calibration summaries only. They never
write patient-level combinations or identifiers to the output profile.
"""

from itertools import combinations

import numpy as np
import pandas as pd


def numeric_correlations(table, df, numeric_cols, min_n, max_cols):
    """Calculate pairwise Pearson and Spearman correlations on complete-case pairs."""
    rows = []
    # Pairwise work is bounded by configuration to keep TRE runtime predictable on wide tables.
    cols = numeric_cols[:max_cols]

    for left, right in combinations(cols, 2):
        # Correlations use rows where both variables are observed; missingness is profiled separately.
        pair = df[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(pair) < min_n or pair[left].nunique() < 2 or pair[right].nunique() < 2:
            continue

        rows.append({
            "table": table,
            "left_column": left,
            "right_column": right,
            "n": int(len(pair)),
            "pearson_r": float(pair[left].corr(pair[right], method="pearson")),
            "spearman_rho": float(pair[left].corr(pair[right], method="spearman")),
        })

    return pd.DataFrame(rows)


def _cramers_v(left, right):
    """Calculate Cramér's V and supporting chi-square statistics for two categorical series."""
    table = pd.crosstab(left, right)
    n = int(table.to_numpy().sum())
    if n == 0 or table.shape[0] < 2 or table.shape[1] < 2:
        return None

    observed = table.to_numpy(dtype=float)
    expected = observed.sum(axis=1, keepdims=True) @ observed.sum(axis=0, keepdims=True) / n
    valid = expected > 0
    chi2 = float((((observed - expected) ** 2) / np.where(valid, expected, 1))[valid].sum())
    denom = n * min(table.shape[0] - 1, table.shape[1] - 1)

    return {
        "n": n,
        "left_levels": table.shape[0],
        "right_levels": table.shape[1],
        "chi_square": chi2,
        "cramers_v": float(np.sqrt(chi2 / denom)) if denom > 0 else np.nan,
    }


def categorical_associations(table, df, categorical_cols, min_n, max_cols, max_levels):
    """Rank eligible categorical pairs by Cramér's V."""
    rows = []
    cols = [
        c for c in categorical_cols[:max_cols]
        if df[c].nunique(dropna=True) <= max_levels
    ]

    for left, right in combinations(cols, 2):
        pair = df[[left, right]].dropna()
        if len(pair) < min_n:
            continue

        result = _cramers_v(pair[left], pair[right])
        if result:
            rows.append({
                "table": table,
                "left_column": left,
                "right_column": right,
                **result,
            })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("cramers_v", ascending=False).reset_index(drop=True)
    return out


def categorical_joint(table, df, associations, max_pairs, min_v):
    """Profile detailed joint/conditional distributions only for the strongest associations."""
    rows = []
    if associations is None or associations.empty:
        return pd.DataFrame(rows)

    # Detailed cells are retained only for sufficiently strong, top-ranked pairs to control output size.
    selected = associations[associations["cramers_v"] >= min_v].head(max_pairs)

    for _, assoc in selected.iterrows():
        left, right = assoc["left_column"], assoc["right_column"]
        pair = df[[left, right]].dropna()
        joint = pair.groupby([left, right]).size().rename("count").reset_index()
        total = int(joint["count"].sum())
        left_total = joint.groupby(left)["count"].transform("sum")
        right_total = joint.groupby(right)["count"].transform("sum")

        for idx, row in joint.iterrows():
            count = int(row["count"])
            rows.append({
                "table": table,
                "left_column": left,
                "right_column": right,
                "left_value": str(row[left]),
                "right_value": str(row[right]),
                "count": count,
                "joint_pct": count / total * 100 if total else np.nan,
                "right_given_left_pct": count / int(left_total.iloc[idx]) * 100,
                "left_given_right_pct": count / int(right_total.iloc[idx]) * 100,
                "cramers_v": float(assoc["cramers_v"]),
            })

    return pd.DataFrame(rows)


def missingness_profiles(table, df, max_columns, max_patterns):
    """Profile row-level, pairwise and repeated-pattern missingness structure."""
    pair_rows = []
    pattern_rows = []
    row_rows = []

    # Row burden answers "how many fields are missing together" before examining specific pairs.
    row_missing = df.isna().sum(axis=1)
    freq = row_missing.value_counts().sort_index()

    for missing_n, row_n in freq.items():
        row_rows.append({
            "table": table,
            "missing_columns_per_row": int(missing_n),
            "row_n": int(row_n),
            "pct_rows": row_n / len(df) * 100 if len(df) else np.nan,
        })

    missing_counts = df.isna().sum()
    cols = (
        missing_counts[(missing_counts > 0) & (missing_counts < len(df))]
        .sort_values(ascending=False)
        .head(max_columns)
        .index.tolist()
    )

    for left, right in combinations(cols, 2):
        a, b = df[left].isna(), df[right].isna()
        both_missing = int((a & b).sum())
        left_only = int((a & ~b).sum())
        right_only = int((~a & b).sum())
        both_present = int((~a & ~b).sum())

        # Phi is the Pearson correlation between two binary missing/not-missing indicators.
        phi = np.nan
        if len(df) > 1 and a.astype(int).std() > 0 and b.astype(int).std() > 0:
            phi = float(np.corrcoef(a.astype(int), b.astype(int))[0, 1])

        pair_rows.append({
            "table": table,
            "left_column": left,
            "right_column": right,
            "rows": int(len(df)),
            "left_missing_n": int(a.sum()),
            "right_missing_n": int(b.sum()),
            "both_missing_n": both_missing,
            "left_only_missing_n": left_only,
            "right_only_missing_n": right_only,
            "both_present_n": both_present,
            "missingness_phi": phi,
        })

    if cols:
        patterns = df[cols].isna().apply(
            lambda row: "|".join(row.index[row.to_numpy()].tolist()) if row.any() else "<NONE>",
            axis=1,
        ).value_counts().head(max_patterns)

        for pattern, count in patterns.items():
            pattern_rows.append({
                "table": table,
                "pattern": pattern,
                "count": int(count),
                "pct": count / len(df) * 100 if len(df) else np.nan,
            })

    return (
        pd.DataFrame(row_rows),
        pd.DataFrame(pair_rows),
        pd.DataFrame(pattern_rows),
    )
