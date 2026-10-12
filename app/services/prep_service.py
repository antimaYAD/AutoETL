"""Structural tidy-up shared by every reader of a stored dataset file.

Real-world exports (especially Excel reports) often carry a title row, so
pandas names columns "Unnamed: N". `prepare_frame` fixes that shape only --
it never converts types or renames data columns, so issue detection still sees
the raw values. Value-level conversions (text->number, serial->date, derived
column names) live in analytics_service.prepare_dataframe, which calls this
first.
"""
from __future__ import annotations

import pandas as pd


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for n in names:
        if n in seen:
            seen[n] += 1
            out.append(f"{n} ({seen[n]})")
        else:
            seen[n] = 0
            out.append(n)
    return out


def _promote_header(df: pd.DataFrame, notes: list[str]) -> pd.DataFrame:
    """Report exports often have a title row, so pandas names columns 'Unnamed: N'."""
    cols = [str(c) for c in df.columns]
    unnamed = sum(c.startswith("Unnamed") for c in cols)
    if len(cols) < 2 or unnamed < max(2, len(cols) * 0.5) or df.empty:
        return df

    ncols = len(cols)
    for i in range(min(10, len(df))):
        row = df.iloc[i]
        strings = [str(v).strip() for v in row if isinstance(v, str) and str(v).strip()]
        if len(strings) >= max(2, ncols * 0.5) and len(set(strings)) >= len(strings) * 0.9:
            header = [str(v).strip() if isinstance(v, str) and str(v).strip() else f"Column {j + 1}" for j, v in enumerate(row)]
            title = cols[0] if not cols[0].startswith("Unnamed") else None
            df = df.iloc[i + 1:].reset_index(drop=True)
            df.columns = _dedupe(header)
            msg = f"Report-style file detected: used data row {i + 1} as the column headers"
            notes.append(msg + (f" (ignored title '{title}')." if title else "."))
            return df
    return df


def prepare_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Return (tidied_frame, notes). Structural fixes only:

    - normalise column labels to str
    - drop fully-empty rows
    - promote the real header row when pandas saw a report title ("Unnamed" cols)
    - drop rows inside the data that repeat the header
    """
    notes: list[str] = []
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    df = df.dropna(how="all")
    df = _promote_header(df, notes)
    if df.empty:
        return df, notes

    header = pd.Series(list(df.columns), index=df.columns)
    repeated = (df.astype(str) == header.astype(str)).sum(axis=1) >= max(2, len(df.columns) * 0.5)
    if repeated.any():
        df = df[~repeated].reset_index(drop=True)
        notes.append(f"Removed {int(repeated.sum())} repeated header row(s) found inside the data.")
    return df, notes
