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

    dataframe = load_dataframe(content, suffix)

    dataset = Dataset(
        owner_id=owner_id,
        name=Path(upload.filename).stem,
        original_filename=storage_service.sanitize_filename(upload.filename),
        industry=industry,
        department=department,
    )
    db.add(dataset)
    db.flush()  # assign dataset.id without committing

    path = storage_service.build_path(dataset.id, 1, upload.filename)
    checksum = storage_service.save_file(path, content)

    version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=1,
        label="Original",
        file_path=str(path),
        checksum=checksum,
        row_count=int(dataframe.shape[0]),
        column_count=int(dataframe.shape[1]),
        status=DatasetVersionStatus.UPLOADED,
    )
    db.add(version)
    db.commit()
    db.refresh(dataset)
    return dataset


def load_version_dataframe(version: DatasetVersion) -> pd.DataFrame:
    path = Path(version.file_path)
    suffix = path.suffix.lower()
    content = storage_service.read_bytes(path)
    return load_dataframe(content, suffix)
