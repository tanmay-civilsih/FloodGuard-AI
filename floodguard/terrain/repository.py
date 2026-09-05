"""Persistence operations for immutable terrain products."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from floodguard.terrain.contracts import TerrainProductRead
from floodguard.terrain.models import TerrainRecord


class TerrainRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, terrain_id: UUID) -> TerrainRecord | None:
        return self.session.get(TerrainRecord, terrain_id)

    def find_by_fingerprint(self, fingerprint: str) -> TerrainRecord | None:
        statement = select(TerrainRecord).where(TerrainRecord.terrain_fingerprint == fingerprint)
        return self.session.scalars(statement).first()

    def add(self, record: TerrainRecord) -> tuple[TerrainRecord, bool]:
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.find_by_fingerprint(record.terrain_fingerprint)
            if existing is None:
                raise
            return existing, False
        self.session.refresh(record)
        return record, True

    def list_products(
        self,
        *,
        city_id: str | None = None,
    ) -> list[TerrainRecord]:
        statement = select(TerrainRecord)
        if city_id is not None:
            statement = statement.where(TerrainRecord.city_id == city_id)
        statement = statement.order_by(TerrainRecord.created_at.desc())
        return list(self.session.scalars(statement).all())

    @staticmethod
    def read(record: TerrainRecord) -> TerrainProductRead:
        return TerrainProductRead.model_validate(record)

    @staticmethod
    def reads(records: Sequence[TerrainRecord]) -> list[TerrainProductRead]:
        return [TerrainProductRead.model_validate(record) for record in records]

