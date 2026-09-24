import datetime as dt

from pydantic import BaseModel, ConfigDict


class DatasetVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_number: int
    label: str
    row_count: int | None
    column_count: int | None
    status: str
    created_at: dt.datetime


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    original_filename: str
    industry: str | None
    department: str | None
    created_at: dt.datetime
    versions: list[DatasetVersionRead] = []


class DatasetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    original_filename: str
    industry: str | None
    department: str | None
    created_at: dt.datetime
