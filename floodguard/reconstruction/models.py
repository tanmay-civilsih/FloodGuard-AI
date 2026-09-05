"""SQLAlchemy models owned by the Sequence 5 reconstruction domain."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from floodguard.contracts.time import utc_now
from floodguard.registry.models import Base, UTCDateTimeType


class DrainageReconstructionRecord(Base):
    __tablename__ = "drainage_reconstructions"
    __table_args__ = (
        UniqueConstraint(
            "reconstruction_fingerprint",
            name="uq_drainage_reconstruction_fingerprint",
        ),
    )

    reconstruction_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_dataset_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    source_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    source_object_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ward_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_authority: Mapped[str] = mapped_column(String(64), nullable=False)
    source_object_key: Mapped[str] = mapped_column(Text(), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[str] = mapped_column(Text(), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    reconstruction_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    calibration_id: Mapped[str] = mapped_column(String(160), nullable=False)
    working_crs: Mapped[str] = mapped_column(String(100), nullable=False)
    georeference_method: Mapped[str] = mapped_column(String(160), nullable=False)
    affine_coefficients: Mapped[list[float]] = mapped_column(JSON(), nullable=False)
    control_points: Mapped[list[dict[str, object]]] = mapped_column(JSON(), nullable=False)
    georeference_rmse_m: Mapped[float] = mapped_column(Float(), nullable=False)
    georeference_max_error_m: Mapped[float] = mapped_column(Float(), nullable=False)
    georeference_tolerance_m: Mapped[float] = mapped_column(Float(), nullable=False)
    native_inspection: Mapped[dict[str, object]] = mapped_column(JSON(), nullable=False)
    working_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    qa_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    audit_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    working_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    qa_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    drain_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    structure_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    label_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    bounds_working: Mapped[list[float]] = mapped_column(JSON(), nullable=False)
    bounds_wgs84: Mapped[list[float]] = mapped_column(JSON(), nullable=False)
    confidence_summary: Mapped[dict[str, int]] = mapped_column(JSON(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTimeType(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTimeType(), nullable=False, default=utc_now
    )


class ReconstructionReviewRecord(Base):
    __tablename__ = "reconstruction_reviews"

    review_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    reconstruction_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("drainage_reconstructions.reconstruction_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewer_type: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str] = mapped_column(Text(), nullable=False)
    checklist: Mapped[dict[str, bool]] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTimeType(), nullable=False, default=utc_now
    )

