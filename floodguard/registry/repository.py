"""Persistence operations for the data source registry."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from floodguard.registry.contracts import SourceCreate, SourceReplace
from floodguard.registry.models import SourceRecord


class RegistryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, source_id: UUID) -> SourceRecord | None:
        return self.session.get(SourceRecord, source_id)

    def list(
        self, *, city_id: str | None = None, category: str | None = None
    ) -> Sequence[SourceRecord]:
        statement = select(SourceRecord)
        if city_id is not None:
            statement = statement.where(SourceRecord.city_id == city_id)
        if category is not None:
            statement = statement.where(SourceRecord.category == category)
        statement = statement.order_by(SourceRecord.category, SourceRecord.dataset_name)
        return self.session.scalars(statement).all()

    def create(self, source: SourceCreate) -> SourceRecord:
        if self.get(source.source_id) is not None:
            raise ValueError(f"source_id already exists: {source.source_id}")
        record = SourceRecord(**source.model_dump(mode="python"))
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def replace(self, source_id: UUID, source: SourceReplace) -> SourceRecord | None:
        record = self.get(source_id)
        if record is None:
            return None
        for key, value in source.model_dump(mode="python").items():
            setattr(record, key, value)
        self.session.commit()
        self.session.refresh(record)
        return record

    def seed_if_missing(self, sources: Sequence[SourceCreate]) -> int:
        inserted = 0
        for source in sources:
            if self.get(source.source_id) is None:
                self.session.add(SourceRecord(**source.model_dump(mode="python")))
                inserted += 1
        self.session.commit()
        return inserted
