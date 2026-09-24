from typing import Any

from pydantic import BaseModel


class ColumnProfile(BaseModel):
    column: str
    inferred_type: str
    null_count: int
    null_percentage: float
    unique_count: int
    duplicate_value_count: int
    sample_values: list[Any]
    min: Any | None = None
    max: Any | None = None
    mean: float | None = None
    median: float | None = None
    string_length_min: int | None = None
    string_length_max: int | None = None
    string_length_mean: float | None = None
    date_format_candidates: list[str] = []
    category_frequencies: dict[str, int] | None = None
    mixed_types: bool = False


class DatasetProfile(BaseModel):
    dataset_version_id: int
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
