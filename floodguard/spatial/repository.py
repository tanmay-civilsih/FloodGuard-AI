"""Persistence operations for normalized spatial layers."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from floodguard.spatial.contracts import SpatialLayerRead
from floodguard.spatial.models import SpatialLayerRecord


class SpatialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, normalization_id: UUID) -> SpatialLayerRecord | None:
        return self.session.get(SpatialLayerRecord, normalization_id)

    def find_by_fingerprint(self, fingerprint: str) -> SpatialLayerRecord | None:
        statement = select(SpatialLayerRecord).where(
            SpatialLayerRecord.normalization_fingerprint == fingerprint
        )
        return self.session.scalars(statement).first()

    def add(self, record: SpatialLayerRecord) -> tuple[SpatialLayerRecord, bool]:
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.find_by_fingerprint(record.normalization_fingerprint)
            if existing is None:
                raise
            return existing, False
        self.session.refresh(record)
        return record, True

    def list_layers(
        self,
        *,
        city_id: str | None = None,
        source_id: UUID | None = None,
    ) -> list[SpatialLayerRecord]:
        statement = select(SpatialLayerRecord)
        if city_id is not None:
            statement = statement.where(SpatialLayerRecord.city_id == city_id)
        if source_id is not None:
            statement = statement.where(SpatialLayerRecord.source_id == source_id)
        statement = statement.order_by(SpatialLayerRecord.created_at.desc())
        return list(self.session.scalars(statement).all())

    def count_source_versions(self, *, city_id: str) -> int:
        value = self.session.scalar(
            select(func.count(func.distinct(SpatialLayerRecord.source_dataset_version_id))).where(
                SpatialLayerRecord.city_id == city_id
            )
        )
        return int(value or 0)

    @staticmethod
    def reads(records: Sequence[SpatialLayerRecord]) -> list[SpatialLayerRead]:
        return [SpatialLayerRead.model_validate(record) for record in records]
