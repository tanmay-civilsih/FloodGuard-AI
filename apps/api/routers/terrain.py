"""Read-only Sequence 6 terrain products and engineering QA endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from floodguard.registry.database import get_db_session
from floodguard.terrain.contracts import (
    TerrainProductKind,
    TerrainProductRead,
    TerrainReadiness,
)
from floodguard.terrain.factory import build_terrain_service
from floodguard.terrain.qa_viewer import QA_VIEWER_HTML
from floodguard.terrain.service import TerrainConditioningError, TerrainService

router = APIRouter(prefix="/terrain", tags=["terrain"])


def get_terrain_service(session: Session = Depends(get_db_session)) -> TerrainService:
    return build_terrain_service(session)


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
