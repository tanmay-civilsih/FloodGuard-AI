"""Persistence operations for drainage reconstructions and append-only reviews."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from floodguard.reconstruction.contracts import (
    DrainageReconstructionRead,
    ReconstructionReviewRead,
)
from floodguard.reconstruction.models import (
    DrainageReconstructionRecord,
    ReconstructionReviewRecord,
)


class ReconstructionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, reconstruction_id: UUID) -> DrainageReconstructionRecord | None:
        return self.session.get(DrainageReconstructionRecord, reconstruction_id)

    def find_by_fingerprint(self, fingerprint: str) -> DrainageReconstructionRecord | None:
        statement = select(DrainageReconstructionRecord).where(
            DrainageReconstructionRecord.reconstruction_fingerprint == fingerprint
        )
        return self.session.scalars(statement).first()

    def add(
        self,
        record: DrainageReconstructionRecord,
    ) -> tuple[DrainageReconstructionRecord, bool]:
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.find_by_fingerprint(record.reconstruction_fingerprint)
            if existing is None:
                raise
            return existing, False
        self.session.refresh(record)
        return record, True

    def list_reconstructions(
        self,
        *,
        city_id: str | None = None,
    ) -> list[DrainageReconstructionRecord]:
        statement = select(DrainageReconstructionRecord)
        if city_id is not None:
            statement = statement.where(DrainageReconstructionRecord.city_id == city_id)
        statement = statement.order_by(DrainageReconstructionRecord.created_at.desc())
        return list(self.session.scalars(statement).all())

    def add_review(
        self,
        reconstruction: DrainageReconstructionRecord,
        review: ReconstructionReviewRecord,
        *,
        resulting_status: str,
    ) -> ReconstructionReviewRecord:
        self.session.add(review)
        reconstruction.status = resulting_status
        reconstruction.reviewed_by = review.reviewer
        reconstruction.reviewed_at = review.created_at
        self.session.commit()
        self.session.refresh(review)
        self.session.refresh(reconstruction)
        return review

    def list_reviews(self, reconstruction_id: UUID) -> list[ReconstructionReviewRecord]:
        statement = (
            select(ReconstructionReviewRecord)
            .where(ReconstructionReviewRecord.reconstruction_id == reconstruction_id)
            .order_by(ReconstructionReviewRecord.created_at.asc())
        )
        return list(self.session.scalars(statement).all())

    @staticmethod
    def read(record: DrainageReconstructionRecord) -> DrainageReconstructionRead:
        return DrainageReconstructionRead.model_validate(record)

    @staticmethod
    def reads(
        records: Sequence[DrainageReconstructionRecord],
    ) -> list[DrainageReconstructionRead]:
        return [DrainageReconstructionRead.model_validate(record) for record in records]

    @staticmethod
    def review_reads(
        records: Sequence[ReconstructionReviewRecord],
    ) -> list[ReconstructionReviewRead]:
        return [ReconstructionReviewRead.model_validate(record) for record in records]

