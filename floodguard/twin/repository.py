"""Exact-version persistence without mutable latest pointers."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from floodguard.twin.contracts import TwinProductRead
from floodguard.twin.models import TwinRecord


class TwinRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, twin_id: UUID) -> TwinRecord | None:
        return self.session.get(TwinRecord, twin_id)

    def list(self, city_id: str) -> list[TwinRecord]:
        return list(
            self.session.scalars(
                select(TwinRecord)
                .where(TwinRecord.city_id == city_id)
                .order_by(TwinRecord.created_at.desc(), TwinRecord.twin_id)
            ).all()
        )

    def add(self, record: TwinRecord) -> tuple[TwinRecord, bool]:
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.get(record.twin_id)
            if existing is None or existing.fingerprint != record.fingerprint:
                raise
            return existing, False
        self.session.refresh(record)
        return record, True

    @staticmethod
    def read(record: TwinRecord) -> TwinProductRead:
        return TwinProductRead.model_validate(record, from_attributes=True)
