"""Public contracts for Sequence 3 acquisition and immutable raw-data versioning."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DatasetVersionStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class HarvestDisposition(StrEnum):
    CREATED = "CREATED"
    UNCHANGED = "UNCHANGED"
    SKIPPED = "SKIPPED"


class RawObjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    object_id: UUID
    dataset_version_id: UUID
    object_key: str
    filename: str
    source_url: str
    sha256: str
    byte_size: int
    content_type: str | None
    etag: str | None
    last_modified: str | None
    created_at: datetime


class DatasetVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset_version_id: UUID
    dataset_id: UUID
    source_id: UUID
    city_id: str
    acquired_at: datetime
    status: DatasetVersionStatus
    manifest_sha256: str
    manifest_object_key: str | None
    object_count: int
    total_bytes: int
    previous_version_id: UUID | None
    source_snapshot: dict[str, object]
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    objects: list[RawObjectRead] = Field(default_factory=list)


class HarvestResult(BaseModel):
    source_id: UUID
    dataset_id: UUID
    dataset_version_id: UUID | None = None
    disposition: HarvestDisposition
    reason: str | None = None
    manifest_sha256: str | None = None
    object_count: int = 0
    total_bytes: int = 0


class HarvestReadiness(BaseModel):
    city_id: str
    automation_permitted_sources: int
    harvested_sources: int
    complete_versions: int
    failed_versions: int
    unharvested_source_ids: list[UUID]
    raw_bucket: str
    raw_prefix_pattern: str = "raw/{city_id}/{source_id}/{dataset_version_id}/..."
