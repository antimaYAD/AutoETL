import pandas as pd

from app.etl.base import Transformation


class FillNull(Transformation):
    name = "fill_null"

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        cols = self._target_columns(df, column)
        return int(df[cols].isna().sum().sum())

    def apply(self, df: pd.DataFrame, column: str | None = None, value=0, **params) -> pd.DataFrame:
        result = df.copy()
        for col in self._target_columns(df, column):
            result[col] = result[col].fillna(value)
        return result


class DropNullRows(Transformation):
    name = "drop_null_rows"

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        subset = [column] if column and column != "*" else None
        return int(df.isna().any(axis=1).sum() if subset is None else df[subset[0]].isna().sum())

    def apply(self, df: pd.DataFrame, column: str | None = None, **params) -> pd.DataFrame:
        subset = [column] if column and column != "*" else None
        return df.dropna(subset=subset).reset_index(drop=True)

    def validate(self, before: pd.DataFrame, after: pd.DataFrame) -> dict:
        base = super().validate(before, after)
        base["rows_dropped"] = base["rows_before"] - base["rows_after"]
        return base
