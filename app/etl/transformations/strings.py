import pandas as pd

from app.etl.base import Transformation


class LowercaseText(Transformation):
    name = "lowercase_text"

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        affected = 0
        for col in self._target_columns(df, column, dtype_include="object"):
            series = df[col].dropna().astype(str)
            affected += int((series != series.str.lower()).sum())
        return affected

    def apply(self, df: pd.DataFrame, column: str | None = None, **params) -> pd.DataFrame:
        result = df.copy()
        for col in self._target_columns(df, column, dtype_include="object"):
            result[col] = result[col].map(lambda v: v.lower() if isinstance(v, str) else v)
        return result


class UppercaseText(Transformation):
    name = "uppercase_text"

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        affected = 0
        for col in self._target_columns(df, column, dtype_include="object"):
            series = df[col].dropna().astype(str)
            affected += int((series != series.str.upper()).sum())
        return affected

    def apply(self, df: pd.DataFrame, column: str | None = None, **params) -> pd.DataFrame:
        result = df.copy()
        for col in self._target_columns(df, column, dtype_include="object"):
            result[col] = result[col].map(lambda v: v.upper() if isinstance(v, str) else v)
        return result


class TitlecaseText(Transformation):
    """Normalizes case-inconsistent free text (e.g. names) to Title Case."""

    name = "titlecase_text"

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        affected = 0
        for col in self._target_columns(df, column, dtype_include="object"):
            series = df[col].dropna().astype(str)
            affected += int((series != series.str.title()).sum())
        return affected

    def apply(self, df: pd.DataFrame, column: str | None = None, **params) -> pd.DataFrame:
        result = df.copy()
        for col in self._target_columns(df, column, dtype_include="object"):
            result[col] = result[col].map(lambda v: v.title() if isinstance(v, str) else v)
        return result
