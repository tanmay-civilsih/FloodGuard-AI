"""SQLAlchemy persistence model for immutable Sequence 7 urban GIS products."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from floodguard.contracts.time import utc_now
from floodguard.registry.models import Base, UTCDateTimeType


class UrbanGisRecord(Base):
    __tablename__ = "urban_gis_products"
    __table_args__ = (
        UniqueConstraint("urban_gis_fingerprint", name="uq_urban_gis_fingerprint"),
    )

    urban_gis_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pilot_area_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    urban_gis_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    working_crs: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    visual_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    hydraulic_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    roof_runoff_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    qa_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    audit_object_key: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    visual_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    hydraulic_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    roof_runoff_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    qa_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    visual_feature_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    hydraulic_feature_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    roof_feature_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    domain_ownership_complete: Mapped[bool] = mapped_column(Boolean(), nullable=False)
    roof_rules_complete: Mapped[bool] = mapped_column(Boolean(), nullable=False)
    readiness_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    limitations: Mapped[list[str]] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTimeType(), nullable=False, default=utc_now
    )
