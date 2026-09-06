"""Sequence 7 urban GIS products and QA endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from floodguard.registry.database import get_db_session
from floodguard.urban_gis.contracts import UrbanGisProductRead, UrbanGisReadiness
from floodguard.urban_gis.factory import build_urban_gis_service
from floodguard.urban_gis.qa_viewer import QA_VIEWER_HTML
from floodguard.urban_gis.service import UrbanGisError, UrbanGisService

router = APIRouter(prefix="/urban-gis", tags=["urban-gis"])


def get_urban_gis_service(session: Session = Depends(get_db_session)) -> UrbanGisService:
    return build_urban_gis_service(session)


@router.get("/readiness", response_model=UrbanGisReadiness)
def readiness(
    city_id: str = Query(default="kolkata", min_length=1, max_length=100),
    service: UrbanGisService = Depends(get_urban_gis_service),
) -> UrbanGisReadiness:
    return service.readiness(city_id=city_id)


@router.get("/products", response_model=list[UrbanGisProductRead])
def list_products(
    city_id: str | None = Query(default=None, min_length=1, max_length=100),
    service: UrbanGisService = Depends(get_urban_gis_service),
) -> list[UrbanGisProductRead]:
    return service.list_products(city_id=city_id)


@router.get("/products/{urban_gis_id}", response_model=UrbanGisProductRead)
def get_product(
    urban_gis_id: UUID,
    service: UrbanGisService = Depends(get_urban_gis_service),
) -> UrbanGisProductRead:
    try:
        return service.get(urban_gis_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="urban GIS product not found") from exc


def _artifact_response(
    urban_gis_id: UUID,
    kind: str,
    service: UrbanGisService,
) -> Response:
    try:
        payload = service.read_artifact(urban_gis_id, kind)
    except UrbanGisError as exc:
        raise HTTPException(status_code=409, detail="urban GIS artifact integrity check failed") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="urban GIS artifact unavailable") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="urban GIS product not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="urban GIS artifact not found") from exc
    media_type = "application/geo+json" if kind in {"visual", "hydraulic", "qa"} else "application/json"
    return Response(content=payload, media_type=media_type)


@router.get("/products/{urban_gis_id}/visual")
def get_visual(
    urban_gis_id: UUID,
    service: UrbanGisService = Depends(get_urban_gis_service),
) -> Response:
    return _artifact_response(urban_gis_id, "visual", service)


@router.get("/products/{urban_gis_id}/hydraulic")
def get_hydraulic(
    urban_gis_id: UUID,
    service: UrbanGisService = Depends(get_urban_gis_service),
) -> Response:
    return _artifact_response(urban_gis_id, "hydraulic", service)


@router.get("/products/{urban_gis_id}/roof-runoff")
def get_roof_runoff(
    urban_gis_id: UUID,
    service: UrbanGisService = Depends(get_urban_gis_service),
) -> Response:
    return _artifact_response(urban_gis_id, "roof-runoff", service)


@router.get("/products/{urban_gis_id}/qa")
def get_qa(
    urban_gis_id: UUID,
    service: UrbanGisService = Depends(get_urban_gis_service),
) -> Response:
    return _artifact_response(urban_gis_id, "qa", service)


@router.get("/products/{urban_gis_id}/audit")
def get_audit(
    urban_gis_id: UUID,
    service: UrbanGisService = Depends(get_urban_gis_service),
) -> Response:
    return _artifact_response(urban_gis_id, "audit", service)


@router.get("/qa", response_class=HTMLResponse)
def qa_viewer() -> HTMLResponse:
    return HTMLResponse(QA_VIEWER_HTML)
