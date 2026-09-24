"""Applies allowlisted transformations to a DataFrame and persists the
result as a new, immutable DatasetVersion (original is never overwritten).
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from app.etl.registry import get_transformation
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion, DatasetVersionStatus
from app.schemas.transformation import TransformationStep
from app.services import issue_service, storage_service


def preview_steps(df: pd.DataFrame, steps: list[TransformationStep]) -> list[dict]:
    previews = []
    current = df
    for step in steps:
        transformation = get_transformation(step.operation)
        previews.append(transformation.preview(current, column=step.column, **step.params))
        current = transformation.apply(current, column=step.column, **step.params)
    return previews


def apply_steps(df: pd.DataFrame, steps: list[TransformationStep]) -> tuple[pd.DataFrame, list[dict]]:
    """Returns (final_dataframe, list of per-step validation dicts)."""
    current = df
    validations = []
    for step in steps:
        transformation = get_transformation(step.operation)
        before = current
        current = transformation.apply(current, column=step.column, **step.params)
        validations.append(
            {
                "operation": step.operation,
                "column": step.column,
                **transformation.validate(before, current),
            }
        )
    return current, validations


def save_transformed_version(
    db: Session,
    dataset: Dataset,
    original_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
    steps: list[TransformationStep],
    step_validations: list[dict],
) -> DatasetVersion:
    next_version_number = max((v.version_number for v in dataset.versions), default=0) + 1

    csv_bytes = transformed_df.to_csv(index=False).encode("utf-8")
    filename = f"{dataset.original_filename.rsplit('.', 1)[0]}_v{next_version_number}.csv"
    path = storage_service.build_path(dataset.id, next_version_number, filename)
    checksum = storage_service.save_file(path, csv_bytes)

    issues = issue_service.detect_issues(transformed_df)
    quality_score = issue_service.compute_quality_score(transformed_df, issues)

    version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=next_version_number,
        label=f"Transformed ({', '.join(s.operation for s in steps)})",
        file_path=str(path),
        checksum=checksum,
        row_count=int(transformed_df.shape[0]),
        column_count=int(transformed_df.shape[1]),
        status=DatasetVersionStatus.TRANSFORMED,
        issues_result={
            "issue_count": len(issues),
            "quality_score": quality_score,
            "issues": issues,
        },
        applied_transformations=[
            {"operation": s.operation, "column": s.column, "params": s.params} for s in steps
        ],
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version
