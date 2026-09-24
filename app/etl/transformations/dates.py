import pandas as pd

from app.etl.base import Transformation

DEFAULT_OUTPUT_FORMAT = "%Y-%m-%d"


class ParseDate(Transformation):
    """Parses mixed/ambiguous date strings into a single ISO format
    (YYYY-MM-DD). Values that can't be parsed become null rather than being
    silently dropped -- see spec's data-safety rule.
    """

    name = "parse_date"

    def _parse(self, series: pd.Series) -> pd.Series:
        return pd.to_datetime(series, errors="coerce", format="mixed")

    def detect(self, df: pd.DataFrame, column: str | None = None) -> int:
        affected = 0
        for col in self._target_columns(df, column):
            series = df[col].dropna().astype(str)
            if series.empty:
                continue
            parsed = self._parse(series)
            formatted = parsed.dt.strftime(DEFAULT_OUTPUT_FORMAT)
            affected += int((series != formatted).sum())
        return affected

    def apply(self, df: pd.DataFrame, column: str | None = None, output_format: str = DEFAULT_OUTPUT_FORMAT, **params) -> pd.DataFrame:
        result = df.copy()
        for col in self._target_columns(df, column):
            parsed = self._parse(result[col].astype(str))
            result[col] = parsed.dt.strftime(output_format)
        return result

    def validate(self, before: pd.DataFrame, after: pd.DataFrame) -> dict:
        base = super().validate(before, after)
        base["unparseable_became_null"] = int(after.isna().sum().sum() - before.isna().sum().sum())
        return base
