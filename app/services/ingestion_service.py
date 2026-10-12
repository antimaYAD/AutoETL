"""Validates uploads and turns them into Dataset / DatasetVersion rows."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion, DatasetVersionStatus
from app.services import storage_service
from app.services.prep_service import prepare_frame

settings = get_settings()


class IngestionError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _validate_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.allowed_upload_extensions:
        allowed = ", ".join(settings.allowed_upload_extensions)
        raise IngestionError(f"Unsupported file type '{suffix}'. Allowed types: {allowed}")
    return suffix


def load_dataframe(content: bytes, suffix: str) -> pd.DataFrame:
    try:
        if suffix == ".csv":
            return pd.read_csv(io.BytesIO(content))
        return pd.read_excel(io.BytesIO(content))
    except Exception as exc:  # pandas raises many different error types
        raise IngestionError(f"Could not parse file as {suffix}: {exc}") from exc


def _read_upload(content: bytes, suffix: str) -> tuple[pd.DataFrame, list[str] | None]:
    """Parse an uploaded file into one DataFrame.

    Excel workbooks: every sheet with data rows is merged into a single table
    (union of columns; missing columns become null) and a ``source_sheet``
    column records which sheet each row came from. Returns the merged frame
    plus the list of contributing sheet names (None for CSV uploads).
    """
    if suffix == ".csv":
        return load_dataframe(content, suffix), None
    try:
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None)
    except Exception as exc:  # pandas raises many different error types
        raise IngestionError(f"Could not parse file as {suffix}: {exc}") from exc

    non_empty = {}
    for name, df in sheets.items():
        if df.shape[0] == 0:
            continue
        # Tidy each sheet before merging so a report-title row in one sheet
        # doesn't poison the merged columns.
        tidied, _ = prepare_frame(df)
        if tidied.shape[0] > 0 and tidied.shape[1] > 0:
            non_empty[name] = tidied
    if not non_empty:
        raise IngestionError("Workbook contains no data rows in any sheet")
    names = list(non_empty)
    if len(non_empty) == 1:
        return non_empty[names[0]].copy(), names
    merged = pd.concat(
        [df.assign(source_sheet=name) for name, df in non_empty.items()],
        ignore_index=True,
    )
    return merged, names


async def ingest_upload(
    db: Session,
    owner_id: int,
    upload: UploadFile,
    industry: str | None,
    department: str | None,
) -> Dataset:
    if not upload.filename:
        raise IngestionError("Uploaded file must have a filename")

    suffix = _validate_extension(upload.filename)

    content = await upload.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise IngestionError(f"File exceeds max upload size of {settings.max_upload_size_mb}MB")
    if len(content) == 0:
        raise IngestionError("Uploaded file is empty")

    dataframe, source_sheets = _read_upload(content, suffix)
    # Metadata reflects what readers see: reads go through prepare_frame, which
    # drops report-title / repeated-header rows for CSVs (Excel sheets are
    # already tidied per-sheet in _read_upload).
    prepared, _ = prepare_frame(dataframe)
    if prepared.empty:
        raise IngestionError("File contains no usable data rows")

    dataset = Dataset(
        owner_id=owner_id,
        name=Path(upload.filename).stem,
        original_filename=storage_service.sanitize_filename(upload.filename),
        industry=industry,
        department=department,
    )
    db.add(dataset)
    db.flush()  # assign dataset.id without committing

    # Excel uploads are normalized to a single merged CSV so every stored
    # version is a plain single-table file (same as transformed versions).
    if suffix == ".csv":
        stored_filename = upload.filename
        stored_bytes = content
    else:
        stored_filename = f"{Path(upload.filename).stem}.csv"
        stored_bytes = prepared.to_csv(index=False).encode("utf-8")

    path = storage_service.build_path(dataset.id, 1, stored_filename)
    checksum = storage_service.save_file(path, stored_bytes)

    version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=1,
        label="Original",
        file_path=str(path),
        checksum=checksum,
        row_count=int(prepared.shape[0]),
        column_count=int(prepared.shape[1]),
        status=DatasetVersionStatus.UPLOADED,
        source_sheets=source_sheets,
    )
    db.add(version)
    db.commit()
    db.refresh(dataset)
    return dataset


def load_version_dataframe(version: DatasetVersion) -> pd.DataFrame:
    path = Path(version.file_path)
    suffix = path.suffix.lower()
    content = storage_service.read_bytes(path)
    return prepare_frame(load_dataframe(content, suffix))[0]
