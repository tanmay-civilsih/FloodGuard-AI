"""Read-only Sequence 4 spatial metadata and engineering QA endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from floodguard.registry.database import get_db_session
from floodguard.spatial.contracts import SpatialLayerRead, SpatialReadiness
from floodguard.spatial.factory import build_spatial_service
from floodguard.spatial.qa_viewer import QA_VIEWER_HTML
from floodguard.spatial.service import SpatialNormalizationError, SpatialService

router = APIRouter(prefix="/spatial", tags=["spatial"])


def get_spatial_service(session: Session = Depends(get_db_session)) -> SpatialService:
    return build_spatial_service(session)


@router.get("/readiness", response_model=SpatialReadiness)
def readiness(
    city_id: str = Query(default="kolkata", min_length=1),
    service: SpatialService = Depends(get_spatial_service),
) -> SpatialReadiness:
    return service.readiness(city_id=city_id)


@router.get("/layers", response_model=list[SpatialLayerRead])
def list_layers(
    city_id: str | None = Query(default=None, min_length=1),
    source_id: UUID | None = None,
    service: SpatialService = Depends(get_spatial_service),
) -> list[SpatialLayerRead]:
    return service.list_layers(city_id=city_id, source_id=source_id)


@router.get("/layers/{normalization_id}", response_model=SpatialLayerRead)
def get_layer(
    normalization_id: UUID,
    service: SpatialService = Depends(get_spatial_service),
) -> SpatialLayerRead:
    try:
        return service.get_layer(normalization_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="normalized spatial layer not found") from exc


@router.get("/layers/{normalization_id}/geojson")
def get_layer_geojson(
    normalization_id: UUID,
    service: SpatialService = Depends(get_spatial_service),
) -> Response:
    try:
        payload = service.qa_geojson(normalization_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="normalized spatial layer not found") from exc
    except SpatialNormalizationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="spatial artifact unavailable") from exc
    return Response(content=payload, media_type="application/geo+json")


@router.get("/qa", response_class=HTMLResponse, include_in_schema=True)
def qa_viewer() -> HTMLResponse:
    return HTMLResponse(QA_VIEWER_HTML)
