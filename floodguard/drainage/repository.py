"""Drain-model-owned database access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from floodguard.drainage.model_contracts import DrainProductRead
from floodguard.drainage.models import DrainProductRecord


class DrainRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, product_id: UUID) -> DrainProductRecord | None:
        return self.session.get(DrainProductRecord, product_id)

    def find(self, fingerprint: str) -> DrainProductRecord | None:
        return self.session.scalar(
            select(DrainProductRecord).where(DrainProductRecord.fingerprint == fingerprint)
        )

    def list_products(self, city_id: str) -> list[DrainProductRecord]:
        return list(
            self.session.scalars(
                select(DrainProductRecord)
                .where(DrainProductRecord.city_id == city_id)
                .order_by(DrainProductRecord.created_at.desc(), DrainProductRecord.product_id)
            ).all()
        )

    def add(self, record: DrainProductRecord) -> tuple[DrainProductRecord, bool]:
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.find(record.fingerprint)
            if existing is None:
                raise
            return existing, False
        self.session.refresh(record)
        return record, True

    @staticmethod
    def read(record: DrainProductRecord) -> DrainProductRead:
        return DrainProductRead.model_validate(record, from_attributes=True)
