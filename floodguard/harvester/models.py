"""SQLAlchemy models owned by the Sequence 3 harvester domain."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from floodguard.contracts.time import utc_now
from floodguard.registry.models import Base, UTCDateTimeType


class DatasetVersionRecord(Base):
    __tablename__ = "harvest_dataset_versions"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "manifest_sha256",
            name="uq_harvest_source_manifest_sha256",
        ),
    )

    dataset_version_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    source_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    city_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    acquired_at: Mapped[datetime] = mapped_column(UTCDateTimeType(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    previous_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("harvest_dataset_versions.dataset_version_id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTimeType(), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTimeType(), nullable=True)

    objects: Mapped[list[RawObjectRecord]] = relationship(
        back_populates="dataset_version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class RawObjectRecord(Base):
    __tablename__ = "harvest_raw_objects"

    object_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    dataset_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("harvest_dataset_versions.dataset_version_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    object_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_modified: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTimeType(), nullable=False, default=utc_now
    )

    dataset_version: Mapped[DatasetVersionRecord] = relationship(back_populates="objects")
