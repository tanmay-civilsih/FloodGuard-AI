"""SQLAlchemy models owned by the Sequence 4 spatial domain."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Float, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from floodguard.contracts.time import utc_now
from floodguard.registry.models import Base, UTCDateTimeType


class SpatialLayerRecord(Base):
    __tablename__ = "spatial_layers"
    __table_args__ = (
        UniqueConstraint(
            "normalization_fingerprint",
            name="uq_spatial_normalization_fingerprint",
        ),
    )

    normalization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_dataset_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    source_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    layer_name: Mapped[str] = mapped_column(String(240), nullable=False)
    variable_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_crs: Mapped[str] = mapped_column(String(100), nullable=False)
    working_crs: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_object_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    qa_object_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    normalized_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    normalization_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    bounds_working: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    bounds_wgs84: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    max_roundtrip_error_m: Mapped[float] = mapped_column(Float, nullable=False)
    resampling_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    vertical_datum: Mapped[str | None] = mapped_column(Text, nullable=True)
    vertical_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    vertical_offset_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    datum_transform_status: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical_reference_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    native_resolution_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    computational_resolution_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_information_resolution_m: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    source_quality: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTimeType(), nullable=False, default=utc_now
    )
