"""HTTP API for the Sequence-2 data source registry."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from floodguard.registry.contracts import (
    RegistryReadiness,
    SourceCategory,
    SourceCreate,
    SourceRead,
    SourceReplace,
)
from floodguard.registry.database import get_db_session
from floodguard.registry.service import (
    InvalidFallbackError,
    RegistryService,
    SourceNotFoundError,
)

router = APIRouter(prefix="/registry", tags=["registry"])


def get_registry_service(session: Session = Depends(get_db_session)) -> RegistryService:
    return RegistryService(session)


@router.get("/sources", response_model=list[SourceRead])
def list_sources(
    city_id: str | None = None,
    category: SourceCategory | None = None,
    registry: RegistryService = Depends(get_registry_service),
) -> list[SourceRead]:
    return registry.list_sources(city_id=city_id, category=category)


@router.get("/sources/{source_id}", response_model=SourceRead)
def get_source(
    source_id: UUID,
    registry: RegistryService = Depends(get_registry_service),
) -> SourceRead:
    try:
        return registry.get_source(source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc


@router.post(
    "/sources",
    response_model=SourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    source: SourceCreate,
    registry: RegistryService = Depends(get_registry_service),
) -> SourceRead:
    try:
        return registry.create_source(source)
    except InvalidFallbackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/sources/{source_id}", response_model=SourceRead)
def replace_source(
    source_id: UUID,
    source: SourceReplace,
    registry: RegistryService = Depends(get_registry_service),
) -> SourceRead:
    try:
        return registry.replace_source(source_id, source)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc
    except InvalidFallbackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/readiness", response_model=RegistryReadiness)
def readiness(
    city_id: str = Query(default="kolkata", min_length=1),
    registry: RegistryService = Depends(get_registry_service),
) -> RegistryReadiness:
    return registry.readiness(city_id=city_id)
