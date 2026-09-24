import re

import pandas as pd

from app.etl.base import Transformation

_NON_DIGIT_PLUS_RE = re.compile(r"[^0-9+]")
_PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


def _normalize(value):
    if not isinstance(value, str):
        return value
    return _NON_DIGIT_PLUS_RE.sub("", value.strip())


class NormalizePhone(Transformation):
    """Strips formatting characters (spaces, dashes, parens) from phone
    numbers, keeping only digits and a leading '+'.
    """

    name = "normalize_phone"

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        cols = self._target_columns(df, column, dtype_include="object")
        affected = 0
        for col in cols:
            series = df[col].dropna().astype(str)
            affected += int((series != series.map(_normalize)).sum())
        return affected

    def apply(self, df: pd.DataFrame, column: str | None = None, **params) -> pd.DataFrame:
        result = df.copy()
        for col in self._target_columns(df, column, dtype_include="object"):
            result[col] = result[col].map(_normalize)
        return result

    def validate(self, before: pd.DataFrame, after: pd.DataFrame) -> dict:
        base = super().validate(before, after)
        invalid_after = 0
        for col in after.select_dtypes(include="object").columns:
            if "phone" not in str(col).lower() and "mobile" not in str(col).lower():
                continue
            series = after[col].dropna().astype(str)
            invalid_after += int((~series.map(lambda v: bool(_PHONE_RE.match(v)))).sum())
        base["invalid_phones_after"] = invalid_after
        return base
