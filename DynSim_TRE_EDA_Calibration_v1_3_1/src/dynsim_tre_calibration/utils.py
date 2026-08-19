import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


ID_TOKENS = (
    "id", "identifier", "hash", "nhs", "patient", "person", "subject",
    "attendance", "attend", "episode", "spell", "referral", "observation",
    "encounter", "visit", "event", "record"
)
DATE_TOKENS = (
    "date", "time", "datetime", "arrival", "departure", "admission",
    "discharge", "start", "end", "birth", "death", "referral", "appointment"
)


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


def read_table(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".feather":
        return pd.read_feather(path)
    raise ValueError(f"Unsupported table type: {suffix}")


def discover_table_files(input_dir, extensions):
    input_dir = Path(input_dir)
    extensions = {x.lower() for x in extensions}
    return [
        p for p in sorted(input_dir.iterdir())
        if p.is_file() and p.suffix.lower() in extensions and not p.name.startswith((".", "_"))
    ]


def to_datetime(series):
    populated = series.dropna()
    if populated.empty:
        return pd.to_datetime(series, errors="coerce"), "empty"

    text = populated.astype(str).str.strip()
    iso_share = text.str.match(r"^\d{4}-\d{2}-\d{2}").mean()
    if iso_share >= 0.80:
        return pd.to_datetime(series, errors="coerce"), "ISO/default"

    return pd.to_datetime(series, errors="coerce", dayfirst=True, format="mixed"), "dayfirst=True"


def is_date_candidate(series, name, threshold):
    if pd.api.types.is_datetime64_any_dtype(series):
        return True, 1.0
    if pd.api.types.is_numeric_dtype(series):
        return False, 0.0
    if not any(token in str(name).lower() for token in DATE_TOKENS):
        return False, 0.0
    sample = series.dropna().head(5000)
    if sample.empty:
        return False, 0.0
    parsed, _ = to_datetime(sample)
    rate = float(parsed.notna().mean())
    return rate >= threshold, rate


def identifier_score(series, name):
    n = len(series)
    nonmissing = int(series.notna().sum())
    unique = int(series.nunique(dropna=True))
    if n == 0 or nonmissing == 0:
        return 0.0

    ratio = unique / nonmissing
    low = str(name).lower()
    score = 2.0 if any(token in low for token in ID_TOKENS) else 0.0
    if ratio >= 0.95:
        score += 2.0
    elif ratio >= 0.50:
        score += 1.25
    elif ratio >= 0.05:
        score += 0.75
    if nonmissing / n >= 0.99:
        score += 0.5
    elif nonmissing / n >= 0.90:
        score += 0.25
    return score


def numeric_stats(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None

    q = s.quantile([0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
    n = len(s)
    mean = float(s.mean())
    variance = float(s.var(ddof=1)) if n > 1 else 0.0

    return {
        "n": int(n),
        "unique_n": int(s.nunique()),
        "mean": mean,
        "sd": float(s.std(ddof=1)) if n > 1 else 0.0,
        "variance": variance,
        "variance_to_mean": float(variance / mean) if mean > 0 else np.nan,
        "skewness": float(s.skew()) if n > 2 else np.nan,
        "excess_kurtosis": float(s.kurt()) if n > 3 else np.nan,
        "min": float(s.min()),
        "p01": float(q.loc[0.01]),
        "p05": float(q.loc[0.05]),
        "p10": float(q.loc[0.10]),
        "q1": float(q.loc[0.25]),
        "median": float(q.loc[0.50]),
        "q3": float(q.loc[0.75]),
        "p90": float(q.loc[0.90]),
        "p95": float(q.loc[0.95]),
        "p99": float(q.loc[0.99]),
        "max": float(s.max()),
        "iqr": float(q.loc[0.75] - q.loc[0.25]),
        "zero_n": int((s == 0).sum()),
        "negative_n": int((s < 0).sum()),
        "positive_n": int((s > 0).sum()),
        "zero_pct": float((s == 0).mean() * 100),
        "negative_pct": float((s < 0).mean() * 100),
        "positive_pct": float((s > 0).mean() * 100),
    }


def nonnegative_interval_stats(series):
    s = pd.to_numeric(series, errors="coerce")
    available = int(s.notna().sum())
    negative_n = int((s < 0).sum())
    zero_n = int((s == 0).sum())
    valid = s[s >= 0].dropna()
    stats = numeric_stats(valid)

    base = {
        "available_n": available,
        "negative_n": negative_n,
        "zero_n": zero_n,
        "valid_n": int(len(valid)),
    }
    if stats:
        base.update(stats)
    return base


def count_distribution(series, metric, entity_name):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return pd.DataFrame(columns=["metric", "count_value", "entity_n", "pct_entities"])

    freq = s.value_counts().sort_index()
    out = freq.rename("entity_n").reset_index()
    out.columns = ["count_value", "entity_n"]
    out["metric"] = metric
    out["entity_type"] = entity_name
    out["pct_entities"] = out["entity_n"] / out["entity_n"].sum() * 100
    return out[["metric", "entity_type", "count_value", "entity_n", "pct_entities"]]


def numbered_slot(name):
    match = re.match(r"^(.*?)[_-]?(\d+)(?:_(?:des|desc|description))?$", str(name), flags=re.I)
    if not match:
        return None
    return match.group(1).rstrip("_-"), int(match.group(2))


def safe_records(df):
    if df is None or df.empty:
        return []
    clean = df.copy()
    return clean.where(pd.notna(clean), None).to_dict(orient="records")
