"""Registry domain rules and readiness evaluation."""

from uuid import UUID

from sqlalchemy.orm import Session

from floodguard.registry.contracts import (
    RegistryReadiness,
    SourceCategory,
    SourceCreate,
    SourceRead,
    SourceReplace,
    SourceStatus,
)
from floodguard.registry.repository import RegistryRepository
from floodguard.registry.seed import PROTOTYPE_REQUIRED_CATEGORIES


class SourceNotFoundError(LookupError):
    pass


class InvalidFallbackError(ValueError):
    pass


class RegistryService:
    def __init__(self, session: Session) -> None:
        self.repository = RegistryRepository(session)

    def list_sources(
        self, *, city_id: str | None = None, category: SourceCategory | None = None
    ) -> list[SourceRead]:
        records = self.repository.list(
            city_id=city_id,
            category=category.value if category is not None else None,
        )
        return [SourceRead.model_validate(record) for record in records]

    def get_source(self, source_id: UUID) -> SourceRead:
        record = self.repository.get(source_id)
        if record is None:
            raise SourceNotFoundError(str(source_id))
        return SourceRead.model_validate(record)

    def create_source(self, source: SourceCreate) -> SourceRead:
        self._validate_fallback(source.source_id, source.fallback_source_id)
        return SourceRead.model_validate(self.repository.create(source))

    def replace_source(self, source_id: UUID, source: SourceReplace) -> SourceRead:
        self._validate_fallback(source_id, source.fallback_source_id)
        record = self.repository.replace(source_id, source)
        if record is None:
            raise SourceNotFoundError(str(source_id))
        return SourceRead.model_validate(record)

    def readiness(self, *, city_id: str = "kolkata") -> RegistryReadiness:
        sources = self.list_sources(city_id=city_id)
        documented = {source.category for source in sources}
        required = set(PROTOTYPE_REQUIRED_CATEGORIES)
        missing = required - documented
        available = {
            source.category for source in sources if source.status is SourceStatus.AVAILABLE
        }
        blocked = documented - available
        return RegistryReadiness(
            catalogue_complete=not missing,
            required_categories=sorted(required, key=str),
            documented_categories=sorted(documented, key=str),
            missing_categories=sorted(missing, key=str),
            available_categories=sorted(available, key=str),
            blocked_or_planned_categories=sorted(blocked, key=str),
            total_sources=len(sources),
        )

    def _validate_fallback(self, source_id: UUID, fallback_source_id: UUID | None) -> None:
        if fallback_source_id is None:
            return
        if fallback_source_id == source_id:
            raise InvalidFallbackError("a source cannot fall back to itself")
        if self.repository.get(fallback_source_id) is None:
            raise InvalidFallbackError("fallback_source_id must reference an existing source")
