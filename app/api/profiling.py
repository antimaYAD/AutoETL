from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersionStatus
from app.models.user import User
from app.schemas.profile import DatasetProfile
from app.services import ingestion_service, profiler_service
from app.services.dataset_access import get_owned_dataset, get_owned_version

router = APIRouter(prefix="/datasets", tags=["profiling"])


@router.post("/{dataset_id}/profile", response_model=DatasetProfile)
def profile_dataset(
    dataset_id: int,
    version_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_owned_dataset(db, dataset_id, current_user)
    version = get_owned_version(dataset, version_id)

    df = ingestion_service.load_version_dataframe(version)
    result = profiler_service.profile_dataframe(df)

    version.profile_result = result
    version.status = DatasetVersionStatus.PROFILED
    db.commit()

    return DatasetProfile(dataset_version_id=version.id, **result)


@router.get("/{dataset_id}/profile", response_model=DatasetProfile)
def get_profile(
    dataset_id: int,
    version_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_owned_dataset(db, dataset_id, current_user)
    version = get_owned_version(dataset, version_id)

    if not version.profile_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset has not been profiled yet")

    return DatasetProfile(dataset_version_id=version.id, **version.profile_result)
