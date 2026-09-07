"""Additive event catalogue; existing forcing/twin rows are unchanged."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from floodguard.contracts.time import utc_now
from floodguard.registry.models import Base, UTCDateTimeType


class HistoricalEventRecord(Base):
    __tablename__ = "historical_events"
    historical_event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTimeType(), default=utc_now, nullable=False)
