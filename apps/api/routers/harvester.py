"""Read-only API for Sequence 3 raw dataset-version metadata.

Network harvesting is intentionally not executed inside HTTP request handlers. Use the
harvester worker/bootstrap command for acquisition.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from floodguard.common.config import get_settings
from floodguard.harvester.contracts import DatasetVersionRead, HarvestReadiness
from floodguard.harvester.factory import build_harvester_service
from floodguard.harvester.service import HarvesterService
from floodguard.registry.database import get_db_session
from floodguard.registry.service import RegistryService

router = APIRouter(prefix="/harvester", tags=["harvester"])


def get_harvester_service(session: Session = Depends(get_db_session)) -> HarvesterService:
    return build_harvester_service(session)


@router.get("/sources/{source_id}/versions", response_model=list[DatasetVersionRead])
def source_versions(
    source_id: UUID,
    harvester: HarvesterService = Depends(get_harvester_service),
) -> list[DatasetVersionRead]:
    return harvester.list_source_versions(source_id)


@router.get("/versions/{dataset_version_id}", response_model=DatasetVersionRead)
def get_version(
    dataset_version_id: UUID,
    harvester: HarvesterService = Depends(get_harvester_service),
) -> DatasetVersionRead:
    try:
        return harvester.get_version(dataset_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="dataset version not found") from exc


@router.get("/readiness", response_model=HarvestReadiness)
def readiness(
    city_id: str = Query(default="kolkata", min_length=1),
    session: Session = Depends(get_db_session),
) -> HarvestReadiness:
    registry = RegistryService(session)
    harvester = build_harvester_service(session)
    settings = get_settings()
    return harvester.readiness(
        city_id=city_id,
        sources=registry.list_sources(city_id=city_id),
        raw_bucket=settings.raw_bucket,
    )
