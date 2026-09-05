"""SQLAlchemy persistence models owned by Sequence 6."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Float, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from floodguard.contracts.time import utc_now
from floodguard.registry.models import Base, UTCDateTimeType


class TerrainRecord(Base):
    __tablename__ = "terrain_products"
    __table_args__ = (
        UniqueConstraint("terrain_fingerprint", name="uq_terrain_fingerprint"),
    )

    terrain_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_dataset_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    source_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    source_object_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pilot_area_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    source_object_key: Mapped[str] = mapped_column(Text(), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    terrain_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    working_crs: Mapped[str] = mapped_column(String(100), nullable=False)
    source_surface_type: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_elevation_object_key: Mapped[str] = mapped_column(Text(), nullable=False)
    visual_terrain_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    hydraulic_terrain_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    multi_level_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    qa_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    audit_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    raw_elevation_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    visual_terrain_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    hydraulic_terrain_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    multi_level_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    qa_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer(), nullable=False)
    height: Mapped[int] = mapped_column(Integer(), nullable=False)
    bounds_working: Mapped[list[float]] = mapped_column(JSON(), nullable=False)
    native_horizontal_resolution_m: Mapped[float] = mapped_column(Float(), nullable=False)
    computational_resolution_m: Mapped[float] = mapped_column(Float(), nullable=False)
    effective_information_resolution_m: Mapped[float] = mapped_column(Float(), nullable=False)
    vertical_quality: Mapped[str] = mapped_column(String(64), nullable=False)
    vertical_datum: Mapped[str | None] = mapped_column(Text(), nullable=True)
    vertical_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    datum_transform_status: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical_validation_method: Mapped[str | None] = mapped_column(Text(), nullable=True)
    vertical_rmse_m: Mapped[float | None] = mapped_column(Float(), nullable=True)
    control_point_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    road_sag_validation: Mapped[str] = mapped_column(String(32), nullable=False)
    underpass_validation: Mapped[str] = mapped_column(String(32), nullable=False)
    drain_rim_elevation_consistency: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_limitations: Mapped[list[str]] = mapped_column(JSON(), nullable=False)
    depression_assessment: Mapped[str] = mapped_column(String(32), nullable=False)
    multi_level_assessment: Mapped[str] = mapped_column(String(32), nullable=False)
    preserved_depression_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    filled_artifact_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    removed_obstruction_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    multi_level_structure_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    max_conditioning_adjustment_m: Mapped[float] = mapped_column(Float(), nullable=False)
    readiness_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    limitations: Mapped[list[str]] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTimeType(), nullable=False, default=utc_now
    )
