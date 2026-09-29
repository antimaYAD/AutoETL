from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import analytics_service, ingestion_service
from app.services.dataset_access import get_owned_dataset, get_owned_version

router = APIRouter(prefix="/datasets", tags=["analytics"])


@router.get("/{dataset_id}/analytics")
def dataset_analytics(
    dataset_id: int,
    version_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_owned_dataset(db, dataset_id, current_user)
    version = get_owned_version(dataset, version_id)
    df = ingestion_service.load_version_dataframe(version)
    result = analytics_service.analyze_dataset(df)
    return {"dataset_version_id": version.id, **result}
