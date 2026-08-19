from itertools import combinations

import pandas as pd


def _unique_nonmissing(df, column):
    return set(df[column].dropna().astype(str).unique().tolist())


def profile_cross_table_links(tables, identifier_profiles, min_overlap):
    rows = []
    table_names = list(tables.keys())

    for left_name, right_name in combinations(table_names, 2):
        left_ids = identifier_profiles.get(left_name)
        right_ids = identifier_profiles.get(right_name)
        if left_ids is None or right_ids is None or left_ids.empty or right_ids.empty:
            continue

        left_df = tables[left_name]
        right_df = tables[right_name]

        left_sets = {
            row.column: (_unique_nonmissing(left_df, row.column), row.value_type)
            for row in left_ids.itertuples(index=False)
            if row.column in left_df.columns
        }
        right_sets = {
            row.column: (_unique_nonmissing(right_df, row.column), row.value_type)
            for row in right_ids.itertuples(index=False)
            if row.column in right_df.columns
        }

        for left_col, (left_values, left_type) in left_sets.items():
            if not left_values:
                continue
            for right_col, (right_values, right_type) in right_sets.items():
                if not right_values:
                    continue

                # Sequential numeric IDs from unrelated tables can overlap by chance.
                # Compare numeric identifiers across tables only when their names match.
                if left_type == "numeric" or right_type == "numeric":
                    if left_type != right_type or left_col.lower() != right_col.lower():
                        continue

                overlap = len(left_values.intersection(right_values))
                if overlap < min_overlap:
                    continue

                rows.append({
                    "left_table": left_name,
                    "left_column": left_col,
                    "left_unique": len(left_values),
                    "right_table": right_name,
                    "right_column": right_col,
                    "right_unique": len(right_values),
                    "overlap_n": overlap,
                    "left_coverage_pct": overlap / len(left_values) * 100,
                    "right_coverage_pct": overlap / len(right_values) * 100,
                    "jaccard": overlap / len(left_values.union(right_values)),
                })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(
            ["left_table", "right_table", "overlap_n", "jaccard"],
            ascending=[True, True, False, False],
        ).reset_index(drop=True)
    return out
