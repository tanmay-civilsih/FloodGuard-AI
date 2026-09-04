"""SQLAlchemy persistence model for registry-owned data."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from floodguard.contracts.time import utc_now


class UTCDateTimeType(TypeDecorator[datetime]):
    """Timezone-aware UTC datetime that also survives SQLite test round-trips."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("database datetime must be timezone-aware")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class SourceRecord(Base):
    __tablename__ = "registry_sources"

    source_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(300), nullable=False)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    access_method: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(100), nullable=False)
    licence: Mapped[str] = mapped_column(Text, nullable=False)
    redistribution_policy: Mapped[str] = mapped_column(Text, nullable=False)
    automation_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    access_class: Mapped[str] = mapped_column(String(64), nullable=False)
    authentication_type: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority_level: Mapped[str] = mapped_column(String(64), nullable=False)
    horizontal_crs: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vertical_datum: Mapped[str | None] = mapped_column(String(200), nullable=True)
    spatial_resolution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    temporal_resolution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    refresh_policy: Mapped[str] = mapped_column(Text, nullable=False)
    fallback_source_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("registry_sources.source_id", ondelete="SET NULL"),
        nullable=True,
    )
    fallback_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    terms_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTimeType(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTimeType(), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTimeType(), nullable=False, default=utc_now, onupdate=utc_now
    )
