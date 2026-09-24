import pandas as pd

from app.etl.base import Transformation


class NormalizeCategory(Transformation):
    """Maps free-text category values to a canonical set via a case/whitespace
    -insensitive mapping supplied in params (e.g. {"ny": "New York"}). Values
    not found in the mapping are left untouched -- never guessed silently.
    """

    name = "normalize_category"

    def _canonical(self, value, mapping: dict[str, str]):
        if not isinstance(value, str):
            return value
        key = value.strip().lower()
        return mapping.get(key, value)

    def detect(self, df: pd.DataFrame, column: str | None = None, mapping: dict[str, str] | None = None) -> int:
        mapping = {k.lower(): v for k, v in (mapping or {}).items()}
        affected = 0
        for col in self._target_columns(df, column, dtype_include="object"):
            series = df[col].dropna()
            affected += int((series != series.map(lambda v: self._canonical(v, mapping))).sum())
        return affected

    def apply(self, df: pd.DataFrame, column: str | None = None, mapping: dict[str, str] | None = None, **params) -> pd.DataFrame:
        mapping = {k.lower(): v for k, v in (mapping or {}).items()}
        result = df.copy()
        for col in self._target_columns(df, column, dtype_include="object"):
            result[col] = result[col].map(lambda v: self._canonical(v, mapping))
        return result
