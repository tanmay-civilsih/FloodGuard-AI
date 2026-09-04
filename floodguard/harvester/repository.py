"""Persistence operations for immutable raw dataset versions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from floodguard.contracts.time import utc_now
from floodguard.harvester.contracts import DatasetVersionStatus
from floodguard.harvester.models import DatasetVersionRecord, RawObjectRecord


@dataclass(frozen=True, slots=True)
class RawObjectPersistence:
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


class HarvesterRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_version(self, dataset_version_id: UUID) -> DatasetVersionRecord | None:
        return self.session.get(DatasetVersionRecord, dataset_version_id)

    def find_by_manifest(
        self,
        source_id: UUID,
        manifest_sha256: str,
    ) -> DatasetVersionRecord | None:
        statement = select(DatasetVersionRecord).where(
            DatasetVersionRecord.source_id == source_id,
            DatasetVersionRecord.manifest_sha256 == manifest_sha256,
        )
        return self.session.scalars(statement).first()

    def latest_complete(self, source_id: UUID) -> DatasetVersionRecord | None:
        statement = (
            select(DatasetVersionRecord)
            .where(
                DatasetVersionRecord.source_id == source_id,
                DatasetVersionRecord.status == DatasetVersionStatus.COMPLETE.value,
            )
            .order_by(DatasetVersionRecord.acquired_at.desc())
            .limit(1)
        )
        return self.session.scalars(statement).first()

    def list_for_source(self, source_id: UUID) -> list[DatasetVersionRecord]:
        statement = (
            select(DatasetVersionRecord)
            .where(DatasetVersionRecord.source_id == source_id)
            .order_by(DatasetVersionRecord.acquired_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def harvested_source_ids(self, *, city_id: str) -> set[UUID]:
        statement = select(DatasetVersionRecord.source_id).where(
            DatasetVersionRecord.city_id == city_id,
            DatasetVersionRecord.status == DatasetVersionStatus.COMPLETE.value,
        )
        return set(self.session.scalars(statement).all())

    def reserve_version(
        self,
        *,
        dataset_version_id: UUID,
        dataset_id: UUID,
        source_id: UUID,
        city_id: str,
        acquired_at: datetime,
        manifest_sha256: str,
        previous_version_id: UUID | None,
        source_snapshot: dict[str, object],
    ) -> tuple[DatasetVersionRecord, bool]:
        record = DatasetVersionRecord(
            dataset_version_id=dataset_version_id,
            dataset_id=dataset_id,
            source_id=source_id,
            city_id=city_id,
            acquired_at=acquired_at,
            status=DatasetVersionStatus.PENDING.value,
            manifest_sha256=manifest_sha256,
            previous_version_id=previous_version_id,
            source_snapshot=source_snapshot,
            object_count=0,
            total_bytes=0,
        )
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.find_by_manifest(source_id, manifest_sha256)
            if existing is None:
                raise
            return existing, False
        self.session.refresh(record)
        return record, True

    def complete_version(
        self,
        dataset_version_id: UUID,
        *,
        manifest_object_key: str,
        objects: list[RawObjectPersistence],
        total_bytes: int,
    ) -> DatasetVersionRecord:
        record = self.get_version(dataset_version_id)
        if record is None:
            raise LookupError(str(dataset_version_id))
        if record.status != DatasetVersionStatus.PENDING.value:
            raise ValueError("only PENDING dataset versions can be completed")
        for item in objects:
            self.session.add(RawObjectRecord(**asdict(item)))
        record.manifest_object_key = manifest_object_key
        record.object_count = len(objects)
        record.total_bytes = total_bytes
        record.status = DatasetVersionStatus.COMPLETE.value
        record.completed_at = utc_now()
        self.session.commit()
        self.session.refresh(record)
        return record

    def fail_version(self, dataset_version_id: UUID, error_message: str) -> None:
        record = self.get_version(dataset_version_id)
        if record is None:
            return
        record.status = DatasetVersionStatus.FAILED.value
        record.error_message = error_message[:4000]
        record.completed_at = utc_now()
        self.session.commit()

    def readiness_counts(self, *, city_id: str) -> tuple[int, int]:
        complete = self.session.scalar(
            select(func.count()).select_from(DatasetVersionRecord).where(
                DatasetVersionRecord.city_id == city_id,
                DatasetVersionRecord.status == DatasetVersionStatus.COMPLETE.value,
            )
        )
        failed = self.session.scalar(
            select(func.count()).select_from(DatasetVersionRecord).where(
                DatasetVersionRecord.city_id == city_id,
                DatasetVersionRecord.status == DatasetVersionStatus.FAILED.value,
            )
        )
        return int(complete or 0), int(failed or 0)
