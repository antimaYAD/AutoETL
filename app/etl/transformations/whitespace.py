import pandas as pd

from app.etl.base import Transformation


class TrimWhitespace(Transformation):
    name = "trim_whitespace"

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        affected = 0
        for col in self._target_columns(df, column, dtype_include="object"):
            series = df[col].dropna().astype(str)
            affected += int((series != series.str.strip()).sum())
        return affected

    def apply(self, df: pd.DataFrame, column: str | None = None, **params) -> pd.DataFrame:
        result = df.copy()
        for col in self._target_columns(df, column, dtype_include="object"):
            result[col] = result[col].map(lambda v: v.strip() if isinstance(v, str) else v)
        return result
