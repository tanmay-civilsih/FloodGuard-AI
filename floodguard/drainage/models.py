"""Sequence 8 immutable product metadata; scientific artifacts live in object storage."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from floodguard.contracts.time import utc_now
from floodguard.registry.models import Base, UTCDateTimeType


class DrainProductRecord(Base):
    __tablename__ = "drain_model_products"

    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pilot_area_id: Mapped[str] = mapped_column(String(160), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    product_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    working_crs: Mapped[str] = mapped_column(String(100), nullable=False)
    artifacts: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeType(), nullable=False, default=utc_now)
