import datetime as dt
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DatasetVersionStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROFILED = "PROFILED"
    ANALYZED = "ANALYZED"
    TRANSFORMED = "TRANSFORMED"


class DatasetVersion(Base):
    """One immutable snapshot of a dataset's file (original upload, or the
    output of applying transformations). Never overwritten -- see spec
    section 13 (Versioning & Audit).
    """

    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(255), default="Original", nullable=False)

    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[DatasetVersionStatus] = mapped_column(
        Enum(DatasetVersionStatus), default=DatasetVersionStatus.UPLOADED, nullable=False
    )

    # For Excel workbooks: names of the sheets that were merged into this
    # version (None for CSV uploads / transformed versions).
    source_sheets: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Persisted results (deferred: dedicated tables for job/validation history
    # come in a later phase; these JSON columns are enough for Phase 1).
    profile_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    issues_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applied_transformations: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )

    dataset: Mapped["Dataset"] = relationship(back_populates="versions")
