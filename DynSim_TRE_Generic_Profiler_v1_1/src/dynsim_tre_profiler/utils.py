import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


STRONG_IDENTIFIER_TOKENS = (
    "id", "identifier", "hash", "key", "uuid", "guid", "nhsnumber", "nhsno"
)

ENTITY_IDENTIFIER_TOKENS = (
    "patient", "person", "subject", "member", "record", "observation",
    "attendance", "attend", "episode", "spell", "referral", "encounter",
    "visit", "case", "event"
)

DATETIME_NAME_TOKENS = (
    "date", "time", "datetime", "dob", "death", "birth", "admission",
    "admit", "discharge", "arrival", "departure", "start", "end",
    "referral", "appointment", "episode"
)


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")


def read_table(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".feather":
        return pd.read_feather(path)
    raise ValueError(f"Unsupported file type: {path}")


def discover_tables(input_dir, include_extensions, exclude_name_startswith):
    input_dir = Path(input_dir)
    tables = {}
    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in set(include_extensions):
            continue
        if any(path.name.startswith(prefix) for prefix in exclude_name_startswith):
            continue
        tables[path.stem] = path
    return tables


def normalised_name(name):
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def name_tokens(name):
    text = str(name)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return [token for token in re.split(r"[^A-Za-z0-9]+", text.lower()) if token]


def contains_token(name, tokens):
    token_set = set(name_tokens(name))
    return any(token in token_set for token in tokens)


def numeric_summary(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    q = s.quantile([0.25, 0.50, 0.75, 0.95, 0.99])
    return {
        "n": int(len(s)),
        "mean": float(s.mean()),
        "sd": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "min": float(s.min()),
        "q1": float(q.loc[0.25]),
        "median": float(q.loc[0.50]),
        "q3": float(q.loc[0.75]),
        "p95": float(q.loc[0.95]),
        "p99": float(q.loc[0.99]),
        "max": float(s.max()),
    }


def count_summary(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    q = s.quantile([0.25, 0.50, 0.75, 0.95, 0.99])
    return {
        "n_entities": int(len(s)),
        "mean": float(s.mean()),
        "q1": float(q.loc[0.25]),
        "median": float(q.loc[0.50]),
        "q3": float(q.loc[0.75]),
        "p95": float(q.loc[0.95]),
        "p99": float(q.loc[0.99]),
        "max": float(s.max()),
        "n_gt_1": int((s > 1).sum()),
        "pct_gt_1": float((s > 1).mean() * 100),
    }


def datetime_candidate(series, column_name, sample_rows, threshold):
    if pd.api.types.is_datetime64_any_dtype(series):
        return True, 1.0

    if pd.api.types.is_numeric_dtype(series):
        return False, 0.0

    nonmissing = series.dropna()
    if nonmissing.empty:
        return False, 0.0

    if not contains_token(column_name, DATETIME_NAME_TOKENS):
        return False, 0.0

    sample = nonmissing.head(sample_rows)
    parsed = pd.to_datetime(sample, errors="coerce", dayfirst=True, format="mixed")
    success = float(parsed.notna().mean())
    return success >= threshold, success


def probable_free_text(series, mean_length_threshold, unique_ratio_threshold):
    s = series.dropna().astype(str)
    if s.empty:
        return False
    mean_len = float(s.str.len().mean())
    unique_ratio = float(s.nunique() / len(s))
    return mean_len >= mean_length_threshold and unique_ratio >= unique_ratio_threshold


def identifier_score(series, column_name):
    n = len(series)
    nonmissing = int(series.notna().sum())
    unique = int(series.nunique(dropna=True))
    if n == 0 or nonmissing == 0:
        return 0.0, {}

    unique_ratio = unique / nonmissing
    missing_rate = 1 - (nonmissing / n)
    tokens = set(name_tokens(column_name))
    strong_name_hit = bool(tokens.intersection(STRONG_IDENTIFIER_TOKENS))
    entity_name_hit = bool(tokens.intersection(ENTITY_IDENTIFIER_TOKENS))
    is_numeric = pd.api.types.is_numeric_dtype(series)

    score = 0.0
    if strong_name_hit:
        score += 2.5
    if entity_name_hit:
        score += 0.5

    if unique_ratio >= 0.95:
        score += 2.0
    elif unique_ratio >= 0.50:
        score += 1.25
    elif unique_ratio >= 0.05:
        score += 0.5

    if missing_rate <= 0.01:
        score += 0.5
    elif missing_rate <= 0.10:
        score += 0.25

    # Numeric fields without an explicit identifier marker are often measures
    # such as age, score or LOS rather than keys.
    if is_numeric and not strong_name_hit:
        score = min(score, 1.5)

    # Automatic key discovery is deliberately conservative. A column needs
    # identifier/entity semantics in its name; high uniqueness alone is not
    # sufficient because codes and free-text fields can also be unique.
    if not strong_name_hit and not entity_name_hit:
        score = 0.0

    value_type = "numeric" if is_numeric else "string_like"
    return score, {
        "nonmissing_n": nonmissing,
        "unique_n": unique,
        "unique_ratio": unique_ratio,
        "missing_rate": missing_rate,
        "strong_name_token_match": strong_name_hit,
        "entity_name_token_match": entity_name_hit,
        "value_type": value_type,
    }


def detect_numbered_group(column_name):
    match = re.match(r"^(.*?)[_\s-]?(\d+)(?:(_des|_desc|_description))?$", str(column_name), flags=re.I)
    if not match:
        return None
    prefix, number, suffix = match.groups()
    return {
        "group": prefix.rstrip("_ -"),
        "slot": int(number),
        "suffix": suffix or "",
    }


def round_or_nan(value, ndigits=6):
    try:
        if pd.isna(value):
            return np.nan
    except Exception:
        pass
    return round(float(value), ndigits)
