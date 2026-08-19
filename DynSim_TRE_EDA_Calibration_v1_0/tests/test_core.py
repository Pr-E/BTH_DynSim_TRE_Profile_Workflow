import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
sys.path = [SRC] + [p for p in sys.path if p != SRC]

from dynsim_tre_calibration.discovery import infer_family
from dynsim_tre_calibration.utils import numeric_stats


def test_family_detection():
    inpatient = pd.DataFrame({"SpellID": [1], "EpisodeId": [1]})
    ed = pd.DataFrame({"ArrivalDateTime": ["2024-01-01"], "Departure": ["2024-01-01"]})
    pathway = pd.DataFrame({
        "FirstMSKReferralDate": ["2024-01-01"],
        "FirstMSKDate": ["2024-01-02"],
        "LastMSKDate": ["2024-01-03"],
    })
    assert infer_family(inpatient) == "inpatient"
    assert infer_family(ed) == "ed"
    assert infer_family(pathway) == "pathway"


def test_numeric_stats():
    out = numeric_stats(pd.Series([0, 1, 2, 3, 4]))
    assert out["n"] == 5
    assert out["zero_n"] == 1
    assert out["median"] == 2


if __name__ == "__main__":
    test_family_detection()
    test_numeric_stats()
    print("Core tests: PASS")
