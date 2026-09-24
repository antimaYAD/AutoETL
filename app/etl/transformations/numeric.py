import re

import pandas as pd

from app.etl.base import Transformation

_CURRENCY_OR_COMMA_RE = re.compile(r"[$€£¥,]")


def _clean_numeric_string(value):
    if not isinstance(value, str):
        return value
    return _CURRENCY_OR_COMMA_RE.sub("", value.strip())


class NormalizeNumeric(Transformation):
    """Strips currency symbols/thousands separators and converts to float,
    turning unparseable values into null (never silently coerced to 0).
    """

    name = "normalize_numeric"

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        affected = 0
        for col in self._target_columns(df, column, dtype_include="object"):
            series = df[col].dropna().astype(str)
            if series.empty:
                continue
            cleaned = series.map(_clean_numeric_string)
            numeric = pd.to_numeric(cleaned, errors="coerce")
            affected += int((series != numeric.astype(str)).sum())
        return affected

    def apply(self, df: pd.DataFrame, column: str | None = None, **params) -> pd.DataFrame:
        result = df.copy()
        for col in self._target_columns(df, column, dtype_include="object"):
            cleaned = result[col].map(_clean_numeric_string)
            result[col] = pd.to_numeric(cleaned, errors="coerce")
        return result

    def validate(self, before: pd.DataFrame, after: pd.DataFrame) -> dict:
        base = super().validate(before, after)
        base["new_nulls_from_unparseable"] = int(after.isna().sum().sum() - before.isna().sum().sum())
        return base
