"""Shared ownership/lookup helpers for datasets and their versions."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.user import User


def get_owned_dataset(db: Session, dataset_id: int, user: User) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None or dataset.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


def get_owned_version(dataset: Dataset, version_id: int | None) -> DatasetVersion:
    if version_id is None:
        if not dataset.versions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset has no versions")
        return dataset.versions[-1]

    for version in dataset.versions:
        if version.id == version_id:
            return version
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found")
