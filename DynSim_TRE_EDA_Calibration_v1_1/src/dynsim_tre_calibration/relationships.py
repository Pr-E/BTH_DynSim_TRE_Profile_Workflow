"""Calculate aggregate patient coverage and overlap across discovered tables.

Only set sizes and overlap statistics are returned; raw identifier values are
used transiently in memory and are not written to profile outputs.
"""

from itertools import combinations

import pandas as pd


def cross_table_relationships(states, results):
    """Calculate aggregate overlap/coverage for every pair of tables with resolved patient keys."""
    rows = []
    names = list(states)

    for left, right in combinations(names, 2):
        left_key = states[left]["patient_key"]
        right_key = states[right]["patient_key"]
        if not left_key or not right_key:
            continue

        left_view = results[left]["analysis_view"]
        right_view = results[right]["analysis_view"]

        if left_key not in left_view.columns or right_key not in right_view.columns:
            continue

        # Identifier values are used only transiently to compute set overlap; only aggregate counts leave this function.
        left_ids = set(left_view[left_key].dropna().astype(str).unique())
        right_ids = set(right_view[right_key].dropna().astype(str).unique())
        if not left_ids or not right_ids:
            continue

        # Coverage is directional, while Jaccard provides a symmetric similarity measure.
        overlap = len(left_ids & right_ids)
        union = len(left_ids | right_ids)

        rows.append({
            "left_table": left,
            "left_patient_key": left_key,
            "left_unique_patients": len(left_ids),
            "right_table": right,
            "right_patient_key": right_key,
            "right_unique_patients": len(right_ids),
            "overlap_n": overlap,
            "left_coverage_pct": overlap / len(left_ids) * 100,
            "right_coverage_pct": overlap / len(right_ids) * 100,
            "jaccard": overlap / union if union else 0.0,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("overlap_n", ascending=False).reset_index(drop=True)
    return out
