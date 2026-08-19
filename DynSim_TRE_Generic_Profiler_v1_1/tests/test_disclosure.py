import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
sys.path = [SRC] + [p for p in sys.path if p != SRC]

from dynsim_tre_profiler.disclosure import (
    _collapse_small_categories,
    _suppress_dependent_percentages,
    _suppress_supported_summary_rows,
)


def test_small_supported_summary_is_fully_suppressed():
    df = pd.DataFrame([{
        "n": 4, "mean": 10.0, "median": 9.0, "q1": 8.0,
        "q3": 11.0, "min": 7.0, "max": 12.0,
    }])
    out = _suppress_supported_summary_rows(df, 10)
    for col in ("n", "mean", "median", "q1", "q3", "min", "max"):
        assert pd.isna(out.loc[0, col])


def test_small_count_suppresses_percentage():
    df = pd.DataFrame([{"count": 3, "pct": 1.5}])
    out = _suppress_dependent_percentages(df, 10)
    assert pd.isna(out.loc[0, "pct"])


def test_small_categories_are_collapsed():
    df = pd.DataFrame([
        {"table": "t", "column": "c", "value": "A", "count": 100, "pct": 90.0},
        {"table": "t", "column": "c", "value": "B", "count": 6, "pct": 5.4},
        {"table": "t", "column": "c", "value": "C", "count": 5, "pct": 4.6},
    ])
    out = _collapse_small_categories(df, 10)
    grouped = out[out["value"] == "__OTHER_OR_SUPPRESSED__"]
    assert len(grouped) == 1
    assert grouped.iloc[0]["count"] == 11


if __name__ == "__main__":
    test_small_supported_summary_is_fully_suppressed()
    test_small_count_suppresses_percentage()
    test_small_categories_are_collapsed()
    print("Disclosure tests: PASS")
