"""Immutable twin reads; explicit build and recreation remain operator CLI operations."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from floodguard.registry.database import get_db_session
from floodguard.twin.contracts import TwinProductRead, TwinReadiness
from floodguard.twin.factory import build_twin_service
from floodguard.twin.qa_viewer import QA_VIEWER_HTML
from floodguard.twin.service import TwinService

router = APIRouter(prefix="/twins", tags=["twins"])


def get_twin_service(session: Session = Depends(get_db_session)) -> TwinService:
    return build_twin_service(session)


@router.get("/readiness", response_model=TwinReadiness)
def readiness(
    city_id: str = Query(default="kolkata", min_length=1, max_length=100),
    service: TwinService = Depends(get_twin_service),
) -> TwinReadiness:
    return service.readiness(city_id)


@router.get("/products", response_model=list[TwinProductRead])
def products(
    city_id: str = Query(default="kolkata", min_length=1, max_length=100),
    service: TwinService = Depends(get_twin_service),
) -> list[TwinProductRead]:
    return service.list(city_id)


@router.get("/products/{twin_id}", response_model=TwinProductRead)
def product(twin_id: UUID, service: TwinService = Depends(get_twin_service)) -> TwinProductRead:
    try:
        return service.get(twin_id)
    except LookupError as exc:
        raise HTTPException(404, "twin not found") from exc


@router.get("/products/{twin_id}/{kind}")
def artifact(
    twin_id: UUID, kind: str, service: TwinService = Depends(get_twin_service)
) -> Response:
    try:
        payload = service.read_artifact(twin_id, kind)
    except FileNotFoundError as exc:
        raise HTTPException(503, "twin component unavailable") from exc
    except LookupError as exc:
        raise HTTPException(404, "twin or component not found") from exc
    except ValueError as exc:
        raise HTTPException(409, "twin identity or component integrity check failed") from exc
    return Response(payload, media_type="application/json")


@router.get("/qa", response_class=HTMLResponse)
def qa() -> HTMLResponse:
    return HTMLResponse(QA_VIEWER_HTML)
