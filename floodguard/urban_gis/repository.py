"""Persistence operations for immutable Sequence 7 urban GIS products."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from floodguard.urban_gis.contracts import UrbanGisProductRead
from floodguard.urban_gis.models import UrbanGisRecord


class UrbanGisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, urban_gis_id: UUID) -> UrbanGisRecord | None:
        return self.session.get(UrbanGisRecord, urban_gis_id)

    def find_by_fingerprint(self, fingerprint: str) -> UrbanGisRecord | None:
        statement = select(UrbanGisRecord).where(
            UrbanGisRecord.urban_gis_fingerprint == fingerprint
        )
        return self.session.scalars(statement).first()

    def add(self, record: UrbanGisRecord) -> tuple[UrbanGisRecord, bool]:
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.find_by_fingerprint(record.urban_gis_fingerprint)
            if existing is None:
                raise
            return existing, False
        self.session.refresh(record)
        return record, True

    def list_products(self, *, city_id: str | None = None) -> list[UrbanGisRecord]:
        statement = select(UrbanGisRecord)
        if city_id is not None:
            statement = statement.where(UrbanGisRecord.city_id == city_id)
        statement = statement.order_by(
            UrbanGisRecord.created_at.desc(), UrbanGisRecord.urban_gis_id.desc()
        )
        return list(self.session.scalars(statement).all())

    @staticmethod
    def read(record: UrbanGisRecord) -> UrbanGisProductRead:
        return UrbanGisProductRead.model_validate(record)

    @staticmethod
    def reads(records: Sequence[UrbanGisRecord]) -> list[UrbanGisProductRead]:
        return [UrbanGisProductRead.model_validate(record) for record in records]
