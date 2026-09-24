from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.dataset_version import DatasetVersionStatus
from app.models.user import User
from app.schemas.issue import DatasetIssues
from app.schemas.transformation import (
    TransformationApplyResponse,
    TransformationPlanRequest,
    TransformationPreviewResponse,
)
from app.services import execution_service, ingestion_service, issue_service
from app.services.dataset_access import get_owned_dataset, get_owned_version

router = APIRouter(prefix="/datasets", tags=["transformations"])


@router.post("/{dataset_id}/analyze", response_model=DatasetIssues)
def analyze_dataset(
    dataset_id: int,
    version_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_owned_dataset(db, dataset_id, current_user)
    version = get_owned_version(dataset, version_id)

    df = ingestion_service.load_version_dataframe(version)
    issues = issue_service.detect_issues(df)
    quality_score = issue_service.compute_quality_score(df, issues)

    version.issues_result = {"issue_count": len(issues), "quality_score": quality_score, "issues": issues}
    version.status = DatasetVersionStatus.ANALYZED
    db.commit()

    return DatasetIssues(dataset_version_id=version.id, issue_count=len(issues), quality_score=quality_score, issues=issues)


@router.get("/{dataset_id}/issues", response_model=DatasetIssues)
def get_issues(
    dataset_id: int,
    version_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_owned_dataset(db, dataset_id, current_user)
    version = get_owned_version(dataset, version_id)

    if not version.issues_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset has not been analyzed yet")

    return DatasetIssues(dataset_version_id=version.id, **version.issues_result)


@router.post("/{dataset_id}/preview", response_model=TransformationPreviewResponse)
def preview_transformations(
    dataset_id: int,
    plan: TransformationPlanRequest,
    version_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_owned_dataset(db, dataset_id, current_user)
    version = get_owned_version(dataset, version_id)
    df = ingestion_service.load_version_dataframe(version)

    try:
        previews = execution_service.preview_steps(df, plan.steps)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TransformationPreviewResponse(dataset_version_id=version.id, previews=previews)


@router.post("/{dataset_id}/transform", response_model=TransformationApplyResponse)
def apply_transformations(
    dataset_id: int,
    plan: TransformationPlanRequest,
    version_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_owned_dataset(db, dataset_id, current_user)
    version = get_owned_version(dataset, version_id)
    df = ingestion_service.load_version_dataframe(version)

    try:
        transformed_df, step_validations = execution_service.apply_steps(df, plan.steps)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    new_version = execution_service.save_transformed_version(
        db, dataset, df, transformed_df, plan.steps, step_validations
    )

    return TransformationApplyResponse(
        new_dataset_version_id=new_version.id,
        applied_steps=[s.operation for s in plan.steps],
        rows_before=int(df.shape[0]),
        rows_after=int(transformed_df.shape[0]),
        validation={"steps": step_validations, **new_version.issues_result},
    )
