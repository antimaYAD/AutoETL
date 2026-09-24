"""Generic data-quality issue detection (spec section 8).

Each detector inspects statistical/structural properties only -- no
hard-coded business column names -- and returns a list of issue dicts
matching app.schemas.issue.DataIssue.
"""
from __future__ import annotations

import re

import pandas as pd

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9()\-.\s]{7,20}$")
_CURRENCY_RE = re.compile(r"[$€£¥]")

MIN_ROWS_FOR_PCT = 1


def _pct(count: int, total: int) -> float:
    return round((count / total) * 100, 2) if total else 0.0


def _issue(issue_type: str, column: str | None, affected_rows: int, severity: str, confidence: float, description: str) -> dict:
    return {
        "issue_type": issue_type,
        "column": column,
        "affected_rows": affected_rows,
        "severity": severity,
        "confidence": confidence,
        "description": description,
    }


def detect_missing_values(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        if null_count == 0:
            continue
        pct = _pct(null_count, len(df))
        severity = "high" if pct > 20 else "medium" if pct > 5 else "low"
        issues.append(
            _issue("MISSING_VALUES", col, null_count, severity, 1.0, f"{null_count} missing values ({pct}%)")
        )
    return issues


def detect_whitespace(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.select_dtypes(include=["object", "string"]).columns:
        series = df[col].dropna().astype(str)
        if series.empty:
            continue
        affected = int((series != series.str.strip()).sum())
        if affected:
            issues.append(
                _issue("WHITESPACE", col, affected, "low", 0.99, f"{affected} values have leading/trailing whitespace")
            )
    return issues


def detect_duplicate_rows(df: pd.DataFrame) -> list[dict]:
    dup_count = int(df.duplicated().sum())
    if not dup_count:
        return []
    return [_issue("DUPLICATE_ROWS", None, dup_count, "medium", 1.0, f"{dup_count} fully duplicate rows")]


def detect_case_inconsistency(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.select_dtypes(include=["object", "string"]).columns:
        series = df[col].dropna().astype(str)
        if series.empty:
            continue
        lowered = series.str.lower()
        # If the same value appears with different casing, flag it.
        variants_per_value = lowered.groupby(lowered).transform("nunique")
        actual_variants = series.groupby(lowered).transform("nunique")
        affected = int((actual_variants > 1).sum())
        if affected:
            issues.append(
                _issue("CASE_INCONSISTENCY", col, affected, "low", 0.9, f"{affected} values have inconsistent case for the same content")
            )
    return issues


def detect_invalid_emails(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.columns:
        if "email" not in str(col).lower():
            continue
        series = df[col].dropna().astype(str)
        if series.empty:
            continue
        invalid = int((~series.str.strip().map(lambda v: bool(_EMAIL_RE.match(v)))).sum())
        if invalid:
            issues.append(
                _issue("INVALID_EMAIL", col, invalid, "medium", 0.95, f"{invalid} values are not valid email addresses")
            )
    return issues


def detect_invalid_phones(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.columns:
        if "phone" not in str(col).lower() and "mobile" not in str(col).lower():
            continue
        series = df[col].dropna().astype(str)
        if series.empty:
            continue
        invalid = int((~series.str.strip().map(lambda v: bool(_PHONE_RE.match(v)))).sum())
        if invalid:
            issues.append(
                _issue("INVALID_PHONE", col, invalid, "medium", 0.85, f"{invalid} values don't look like valid phone numbers")
            )
    return issues


def detect_currency_symbols(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.select_dtypes(include=["object", "string"]).columns:
        series = df[col].dropna().astype(str)
        if series.empty:
            continue
        affected = int(series.str.contains(_CURRENCY_RE).sum())
        if affected:
            issues.append(
                _issue("CURRENCY_SYMBOL", col, affected, "low", 0.9, f"{affected} values contain currency symbols mixed with numbers")
            )
    return issues


def detect_mixed_numeric_formats(df: pd.DataFrame) -> list[dict]:
    """Flags text columns where most values look numeric but some don't
    parse cleanly as numbers (e.g. commas, mixed separators)."""
    issues = []
    for col in df.select_dtypes(include=["object", "string"]).columns:
        series = df[col].dropna().astype(str).str.strip()
        if series.empty:
            continue
        cleaned = series.str.replace(",", "", regex=False).str.replace(_CURRENCY_RE, "", regex=True)
        numeric_like = pd.to_numeric(cleaned, errors="coerce")
        numeric_ratio = numeric_like.notna().mean()
        if 0.5 < numeric_ratio < 1.0:
            affected = int(numeric_like.isna().sum())
            issues.append(
                _issue(
                    "MIXED_NUMERIC_FORMAT",
                    col,
                    affected,
                    "medium",
                    0.8,
                    f"{affected} values don't parse as numbers though the column looks numeric",
                )
            )
    return issues


def detect_outliers(df: pd.DataFrame) -> list[dict]:
    issues = []
    for col in df.select_dtypes(include="number").columns:
        series = df[col].dropna()
        if len(series) < 4:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        affected = int(((series < lower) | (series > upper)).sum())
        if affected:
            issues.append(
                _issue("OUTLIER", col, affected, "low", 0.7, f"{affected} statistical outliers detected (IQR method)")
            )
    return issues


DETECTORS = [
    detect_missing_values,
    detect_whitespace,
    detect_duplicate_rows,
    detect_case_inconsistency,
    detect_invalid_emails,
    detect_invalid_phones,
    detect_currency_symbols,
    detect_mixed_numeric_formats,
    detect_outliers,
]


def detect_issues(df: pd.DataFrame) -> list[dict]:
    issues: list[dict] = []
    for detector in DETECTORS:
        issues.extend(detector(df))
    return issues


def compute_quality_score(df: pd.DataFrame, issues: list[dict]) -> float:
    total_cells = max(df.shape[0] * df.shape[1], 1)
    weighted_affected = sum(issue["affected_rows"] * issue["confidence"] for issue in issues)
    score = max(0.0, 100.0 - (weighted_affected / total_cells) * 100)
    return round(score, 2)
