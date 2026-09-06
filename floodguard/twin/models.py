"""Twin-owned immutable manifest metadata."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from floodguard.contracts.time import utc_now
from floodguard.registry.models import Base, UTCDateTimeType


class TwinRecord(Base):
    __tablename__ = "twin_versions"

    twin_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pilot_area_id: Mapped[str] = mapped_column(String(160), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    hydraulic_readiness: Mapped[str] = mapped_column(String(40), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    audit: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeType(), nullable=False, default=utc_now)
