from typing import Any

from pydantic import BaseModel, Field


class TransformationStep(BaseModel):
    """One requested transformation. `operation` must be a key registered in
    app.etl.registry.TRANSFORMATIONS (an allowlist -- never arbitrary code).
    """

    operation: str
    column: str | None = None  # None / "*" means "all applicable columns"
    params: dict[str, Any] = Field(default_factory=dict)


class TransformationPlanRequest(BaseModel):
    steps: list[TransformationStep]


class TransformationPreviewResult(BaseModel):
    operation: str
    column: str | None
    rows_affected: int
    sample_before: list[dict[str, Any]]
    sample_after: list[dict[str, Any]]


class TransformationPreviewResponse(BaseModel):
    dataset_version_id: int
    previews: list[TransformationPreviewResult]


class TransformationApplyResponse(BaseModel):
    new_dataset_version_id: int
    applied_steps: list[str]
    rows_before: int
    rows_after: int
    validation: dict[str, Any]
