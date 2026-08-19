import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dynsim_tre_calibration.eda import _anomaly_candidates


def test_anomaly_candidates():
    frame = pd.DataFrame({
        "age_like": [40, 41, 42, 43, 44, 45, 999],
        "departure": pd.to_datetime([
            "1900-01-01",
            "2023-01-01",
            "2023-02-01",
            "2024-01-01",
            "2024-02-01",
            "2025-01-01",
            "2025-02-01",
        ]),
    })
    out = _anomaly_candidates(
        "table",
        frame,
        {"departure": frame["departure"]},
        excluded=set(),
    )

    assert (
        (out["anomaly_type"] == "numeric_extreme_high")
        & (out["column"] == "age_like")
        & (out["value"] == 999)
    ).any()

    assert (
        (out["anomaly_type"] == "isolated_early_year")
        & (out["column"] == "departure")
        & (out["value"] == 1900)
    ).any()


if __name__ == "__main__":
    test_anomaly_candidates()
    print("Anomaly tests: PASS")
