"""Transformation strategy interface (spec section 9).

Every transformation is isolated and testable via four operations:
- detect:   does this transformation apply / how many rows would it affect?
- preview:  return a small before/after sample without mutating the input.
- apply:    return a NEW DataFrame with the transformation applied (never
            mutate the input in place -- callers rely on this for versioning).
- validate: sanity-check the output against the input (row count, schema).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

PREVIEW_SAMPLE_SIZE = 5


class Transformation(ABC):
    name: str = "transformation"

    @abstractmethod
    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        """Return the number of rows this transformation would affect."""

    @abstractmethod
    def apply(self, df: pd.DataFrame, column: str | None = None, **params) -> pd.DataFrame:
        """Return a new DataFrame with the transformation applied."""

    def preview(self, df: pd.DataFrame, column: str | None = None, **params) -> dict:
        affected = self.detect(df, column=column)
        after = self.apply(df, column=column, **params)
        return {
            "operation": self.name,
            "column": column,
            "rows_affected": affected,
            "sample_before": df.head(PREVIEW_SAMPLE_SIZE).astype(object).where(pd.notna(df.head(PREVIEW_SAMPLE_SIZE)), None).to_dict(orient="records"),
            "sample_after": after.head(PREVIEW_SAMPLE_SIZE).astype(object).where(pd.notna(after.head(PREVIEW_SAMPLE_SIZE)), None).to_dict(orient="records"),
        }

    def validate(self, before: pd.DataFrame, after: pd.DataFrame) -> dict:
        """Generic invariants: no silent row loss, no silent column loss."""
        return {
            "rows_before": int(before.shape[0]),
            "rows_after": int(after.shape[0]),
            "columns_before": list(before.columns),
            "columns_after": list(after.columns),
            "row_count_changed": before.shape[0] != after.shape[0],
        }

    def _target_columns(self, df: pd.DataFrame, column: str | None, dtype_include=None) -> list[str]:
        if column and column != "*":
            if column not in df.columns:
                raise ValueError(f"Column '{column}' not found in dataset")
            return [column]
        if dtype_include is not None:
            include = ["object", "string"] if dtype_include == "object" else dtype_include
            return list(df.select_dtypes(include=include).columns)
        return list(df.columns)
