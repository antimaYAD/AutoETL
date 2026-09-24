from pydantic import BaseModel


class DataIssue(BaseModel):
    issue_type: str
    column: str | None = None
    affected_rows: int
    severity: str  # low | medium | high
    confidence: float
    description: str


class DatasetIssues(BaseModel):
    dataset_version_id: int
    issue_count: int
    quality_score: float
    issues: list[DataIssue]
