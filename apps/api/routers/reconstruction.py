"""Sequence 5 drainage reconstruction metadata, QA, and human-review endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from floodguard.common.auth_viewer import with_operator_credentials
from floodguard.reconstruction.contracts import (
    DrainageReconstructionRead,
    ReconstructionReadiness,
    ReconstructionReviewCreate,
    ReconstructionReviewRead,
)
from floodguard.reconstruction.factory import build_reconstruction_service
from floodguard.reconstruction.qa_viewer import QA_VIEWER_HTML
from floodguard.reconstruction.service import ReconstructionError, ReconstructionService
from floodguard.registry.database import get_db_session

router = APIRouter(prefix="/reconstruction", tags=["reconstruction"])


def get_reconstruction_service(
    session: Session = Depends(get_db_session),
) -> ReconstructionService:
    return build_reconstruction_service(session)


@router.get("/readiness", response_model=ReconstructionReadiness)
def readiness(
    city_id: str = Query(default="kolkata", min_length=1),
    service: ReconstructionService = Depends(get_reconstruction_service),
) -> ReconstructionReadiness:
    return service.readiness(city_id=city_id)


@router.get("/maps", response_model=list[DrainageReconstructionRead])
def list_maps(
    city_id: str | None = Query(default=None, min_length=1),
    service: ReconstructionService = Depends(get_reconstruction_service),
) -> list[DrainageReconstructionRead]:
    return service.list_reconstructions(city_id=city_id)


@router.get("/maps/{reconstruction_id}", response_model=DrainageReconstructionRead)
def get_map(
    reconstruction_id: UUID,
    service: ReconstructionService = Depends(get_reconstruction_service),
) -> DrainageReconstructionRead:
    try:
        return service.get(reconstruction_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="reconstruction not found") from exc


@router.get("/maps/{reconstruction_id}/geojson")
def get_map_geojson(
    reconstruction_id: UUID,
    service: ReconstructionService = Depends(get_reconstruction_service),
) -> Response:
    try:
        payload = service.qa_geojson(reconstruction_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="reconstruction not found") from exc
    return Response(content=payload, media_type="application/geo+json")


@router.post(
    "/maps/{reconstruction_id}/reviews",
    response_model=ReconstructionReviewRead,
    status_code=201,
)
def create_review(
    reconstruction_id: UUID,
    request: ReconstructionReviewCreate,
    service: ReconstructionService = Depends(get_reconstruction_service),
) -> ReconstructionReviewRead:
    try:
        return service.review(reconstruction_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="reconstruction not found") from exc
    except ReconstructionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/maps/{reconstruction_id}/reviews",
    response_model=list[ReconstructionReviewRead],
)
def list_reviews(
    reconstruction_id: UUID,
    service: ReconstructionService = Depends(get_reconstruction_service),
) -> list[ReconstructionReviewRead]:
    try:
        return service.list_reviews(reconstruction_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="reconstruction not found") from exc


@router.get("/qa", response_class=HTMLResponse)
def qa_viewer() -> HTMLResponse:
    return HTMLResponse(with_operator_credentials(QA_VIEWER_HTML))
