"""Immutable forcing package registry."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from floodguard.contracts.time import utc_now
from floodguard.registry.models import Base, UTCDateTimeType


class ForcingRecord(Base):
    __tablename__ = "forcing_packages"
    forcing_package_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    twin_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeType(), nullable=False, default=utc_now)
