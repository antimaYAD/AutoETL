"""Generic, column-agnostic data profiler (spec section 6).

Nothing here should ever hard-code a specific business column name -- only
statistical/structural inspection of whatever DataFrame it's given.
"""
from __future__ import annotations

import re

import pandas as pd

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%b %d, %Y"]

MAX_SAMPLE_VALUES = 5
MAX_CATEGORY_FREQUENCIES = 20
CATEGORY_UNIQUE_RATIO_THRESHOLD = 0.5


def _infer_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "unknown"

    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"

    sample = non_null.astype(str).head(200)
    if sample.map(lambda v: bool(_EMAIL_RE.match(v.strip()))).mean() > 0.8:
        return "email"

    date_candidates = _detect_date_formats(sample)
    if date_candidates:
        return "date"

    unique_ratio = non_null.nunique() / max(len(non_null), 1)
    if unique_ratio <= CATEGORY_UNIQUE_RATIO_THRESHOLD and non_null.nunique() <= MAX_CATEGORY_FREQUENCIES:
        return "category"

    return "text"


def _detect_date_formats(sample: pd.Series) -> list[str]:
    candidates: list[str] = []
    for fmt in _DATE_FORMATS:
        try:
            parsed = pd.to_datetime(sample, format=fmt, errors="coerce")
        except (ValueError, TypeError):
            continue
        if parsed.notna().mean() > 0.8:
            candidates.append(fmt)
    return candidates


def _has_mixed_types(series: pd.Series) -> bool:
    non_null = series.dropna()
    if non_null.empty:
        return False
    python_types = non_null.map(type).unique()
    return len(python_types) > 1


def profile_column(series: pd.Series) -> dict:
    non_null = series.dropna()
    inferred_type = _infer_type(series)

    profile: dict = {
        "column": series.name,
        "inferred_type": inferred_type,
        "null_count": int(series.isna().sum()),
        "null_percentage": round(float(series.isna().mean() * 100), 2),
        "unique_count": int(non_null.nunique()),
        "duplicate_value_count": int(len(non_null) - non_null.nunique()),
        "sample_values": non_null.head(MAX_SAMPLE_VALUES).astype(str).tolist(),
        "min": None,
        "max": None,
        "mean": None,
        "median": None,
        "string_length_min": None,
        "string_length_max": None,
        "string_length_mean": None,
        "date_format_candidates": [],
        "category_frequencies": None,
        "mixed_types": _has_mixed_types(series),
    }

    if inferred_type == "numeric" and not non_null.empty:
        numeric = pd.to_numeric(non_null, errors="coerce").dropna()
        if not numeric.empty:
            profile["min"] = float(numeric.min())
            profile["max"] = float(numeric.max())
            profile["mean"] = round(float(numeric.mean()), 4)
            profile["median"] = round(float(numeric.median()), 4)

    if inferred_type in {"text", "email", "category"} and not non_null.empty:
        lengths = non_null.astype(str).map(len)
        profile["string_length_min"] = int(lengths.min())
        profile["string_length_max"] = int(lengths.max())
        profile["string_length_mean"] = round(float(lengths.mean()), 2)

    if inferred_type == "date" and not non_null.empty:
        profile["date_format_candidates"] = _detect_date_formats(non_null.astype(str).head(200))

    if inferred_type == "category" and not non_null.empty:
        freq = non_null.astype(str).value_counts().head(MAX_CATEGORY_FREQUENCIES)
        profile["category_frequencies"] = {str(k): int(v) for k, v in freq.items()}

    return profile


def profile_dataframe(df: pd.DataFrame) -> dict:
    return {
        "row_count": int(df.shape[0]),
        "column_count": int(df.shape[1]),
        "columns": [profile_column(df[col]) for col in df.columns],
    }
