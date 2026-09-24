import pandas as pd

from app.etl.base import Transformation


class RemoveDuplicates(Transformation):
    name = "remove_duplicates"

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        subset = [column] if column and column != "*" else None
        return int(df.duplicated(subset=subset).sum())

    def apply(self, df: pd.DataFrame, column: str | None = None, keep: str = "first", **params) -> pd.DataFrame:
        subset = [column] if column and column != "*" else None
        return df.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)

    def validate(self, before: pd.DataFrame, after: pd.DataFrame) -> dict:
        base = super().validate(before, after)
        base["duplicates_removed"] = base["rows_before"] - base["rows_after"]
        return base
