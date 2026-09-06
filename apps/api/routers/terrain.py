"""Sequence 6 terrain products, acquisition jobs and engineering QA endpoints."""

from typing import cast
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from floodguard.common.config import get_settings
from floodguard.harvester.service import HarvestAccessError
from floodguard.registry.database import get_db_session
from floodguard.terrain.acquisition import (
    TerrainAcquisitionPlan,
    TerrainAcquisitionRequest,
    plan_acquisition,
)
from floodguard.terrain.contracts import (
    TerrainProductKind,
    TerrainProductRead,
    TerrainReadiness,
)
from floodguard.terrain.factory import build_terrain_service
from floodguard.terrain.jobs import (
    AcquisitionBusyError,
    TerrainAcquisitionJob,
    TerrainJobStore,
    run_acquisition,
)
from floodguard.terrain.qa_viewer import QA_VIEWER_HTML
from floodguard.terrain.service import TerrainConditioningError, TerrainService

router = APIRouter(prefix="/terrain", tags=["terrain"])


def get_terrain_service(session: Session = Depends(get_db_session)) -> TerrainService:
    return build_terrain_service(session)


def get_terrain_jobs(request: Request) -> TerrainJobStore:
    return cast(TerrainJobStore, request.app.state.terrain_jobs)


def _plan(session: Session, request: TerrainAcquisitionRequest) -> TerrainAcquisitionPlan:
    try:
        return plan_acquisition(session, request, working_crs=get_settings().working_crs)
    except HarvestAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/acquisition/plan", response_model=TerrainAcquisitionPlan)
def acquisition_plan(
    city_id: str = Query(default="kolkata", min_length=1, max_length=100),
    ward_id: str = Query(default="7", min_length=1, max_length=100),
    cell_size_m: float = Query(default=30.0, gt=0, allow_inf_nan=False),
    session: Session = Depends(get_db_session),
) -> TerrainAcquisitionPlan:
    return _plan(session, TerrainAcquisitionRequest(
        city_id=city_id, ward_id=ward_id, cell_size_m=cell_size_m,
    ))


@router.post("/acquisitions", response_model=TerrainAcquisitionJob, status_code=202)
def acquire_terrain(
    request: TerrainAcquisitionRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db_session),
    jobs: TerrainJobStore = Depends(get_terrain_jobs),
) -> TerrainAcquisitionJob:
    plan = _plan(session, request)
    try:
        job, created = jobs.reserve(plan)
    except AcquisitionBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if created:
        background_tasks.add_task(run_acquisition, job.job_id, jobs)
    return job


@router.get("/acquisitions/{job_id}", response_model=TerrainAcquisitionJob)
def acquisition_status(
    job_id: UUID, jobs: TerrainJobStore = Depends(get_terrain_jobs),
) -> TerrainAcquisitionJob:
    try:
        return jobs.get(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/readiness", response_model=TerrainReadiness)
def readiness(
    city_id: str = Query(default="kolkata", min_length=1),
    service: TerrainService = Depends(get_terrain_service),
) -> TerrainReadiness:
    return service.readiness(city_id=city_id)


@router.get("/products", response_model=list[TerrainProductRead])
def list_products(
    city_id: str | None = Query(default=None, min_length=1),
    service: TerrainService = Depends(get_terrain_service),
) -> list[TerrainProductRead]:
    return service.list_products(city_id=city_id)


@router.get("/products/{terrain_id}", response_model=TerrainProductRead)
def get_product(
    terrain_id: UUID,
    service: TerrainService = Depends(get_terrain_service),
) -> TerrainProductRead:
    try:
        return service.get(terrain_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="terrain product not found") from exc


def _artifact_response(
    terrain_id: UUID,
    product: TerrainProductKind,
    service: TerrainService,
) -> Response:
    try:
        payload = service.read_artifact(terrain_id, product)
    except TerrainConditioningError as exc:
        raise HTTPException(
            status_code=409, detail="terrain artifact integrity check failed"
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="terrain artifact unavailable") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="terrain product not found") from exc
    media_type = "application/geo+json" if product is TerrainProductKind.QA else "application/json"
    if product is TerrainProductKind.RAW_ELEVATION and service.get(
        terrain_id
    ).raw_elevation_object_key.lower().endswith(".hgt"):
        media_type = "application/octet-stream"
    return Response(content=payload, media_type=media_type)


@router.get("/products/{terrain_id}/raw")
def get_raw_elevation(
    terrain_id: UUID,
    service: TerrainService = Depends(get_terrain_service),
) -> Response:
    return _artifact_response(terrain_id, TerrainProductKind.RAW_ELEVATION, service)


@router.get("/products/{terrain_id}/visual")
def get_visual_terrain(
    terrain_id: UUID,
    service: TerrainService = Depends(get_terrain_service),
) -> Response:
    return _artifact_response(terrain_id, TerrainProductKind.VISUAL_TERRAIN, service)


@router.get("/products/{terrain_id}/hydraulic")
def get_hydraulic_terrain(
    terrain_id: UUID,
    service: TerrainService = Depends(get_terrain_service),
) -> Response:
    return _artifact_response(terrain_id, TerrainProductKind.HYDRAULIC_TERRAIN, service)


@router.get("/products/{terrain_id}/multi-level-structures")
def get_multi_level_structures(
    terrain_id: UUID,
    service: TerrainService = Depends(get_terrain_service),
) -> Response:
    return _artifact_response(
        terrain_id,
        TerrainProductKind.MULTI_LEVEL_STRUCTURE_CATALOG,
        service,
    )


@router.get("/products/{terrain_id}/qa")
def get_qa_geojson(
    terrain_id: UUID,
    service: TerrainService = Depends(get_terrain_service),
) -> Response:
    return _artifact_response(terrain_id, TerrainProductKind.QA, service)


@router.get("/qa", response_class=HTMLResponse)
def qa_viewer() -> HTMLResponse:
    return HTMLResponse(QA_VIEWER_HTML)


@router.get("/products/{terrain_id}/audit")
def get_audit(
    terrain_id: UUID,
    service: TerrainService = Depends(get_terrain_service),
) -> Response:
    return _artifact_response(terrain_id, TerrainProductKind.AUDIT, service)
