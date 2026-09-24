"""Job-style entry points around the ETL services.

Phase 1 runs these synchronously inside the request/response cycle (per the
spec's MVP guidance: "small files may be synchronous in MVP"). Redis has no
clean native-Windows story without Docker, so Celery is intentionally
deferred -- but these functions are written as standalone, side-effect-free
wrappers so a future `@celery_app.task` decorator can be added here without
touching `app/services/*` or the API routers.
"""
from sqlalchemy.orm import Session

from app.models.dataset_version import DatasetVersion
from app.services import ingestion_service, issue_service, profiler_service


def run_profile_job(db: Session, version: DatasetVersion) -> dict:
    df = ingestion_service.load_version_dataframe(version)
    result = profiler_service.profile_dataframe(df)
    version.profile_result = result
    db.commit()
    return result


def run_analyze_job(db: Session, version: DatasetVersion) -> dict:
    df = ingestion_service.load_version_dataframe(version)
    issues = issue_service.detect_issues(df)
    quality_score = issue_service.compute_quality_score(df, issues)
    result = {"issue_count": len(issues), "quality_score": quality_score, "issues": issues}
    version.issues_result = result
    db.commit()
    return result
