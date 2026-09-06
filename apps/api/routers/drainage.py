"""Read-only Sequence 8 products, integrity-checked artifacts and geometry QA."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from floodguard.drainage.factory import build_drain_service
from floodguard.drainage.model_contracts import DrainProductRead, DrainReadiness
from floodguard.drainage.qa_viewer import QA_VIEWER_HTML
from floodguard.drainage.service import DrainIntegrityError, DrainService
from floodguard.registry.database import get_db_session

router = APIRouter(prefix="/drainage", tags=["drainage"])


def get_drain_service(session: Session = Depends(get_db_session)) -> DrainService:
    return build_drain_service(session)


@router.get("/readiness", response_model=DrainReadiness)
def readiness(
    city_id: str = Query(default="kolkata", min_length=1, max_length=100),
    service: DrainService = Depends(get_drain_service),
) -> DrainReadiness:
    return service.readiness(city_id)


@router.get("/products", response_model=list[DrainProductRead])
def products(
    city_id: str = Query(default="kolkata", min_length=1, max_length=100),
    service: DrainService = Depends(get_drain_service),
) -> list[DrainProductRead]:
    return service.list_products(city_id)


@router.get("/products/{product_id}", response_model=DrainProductRead)
def product(
    product_id: UUID,
    service: DrainService = Depends(get_drain_service),
) -> DrainProductRead:
    try:
        return service.get(product_id)
    except LookupError as exc:
        raise HTTPException(404, "drain product not found") from exc


@router.get("/products/{product_id}/{kind}")
def artifact(
    product_id: UUID,
    kind: str,
    service: DrainService = Depends(get_drain_service),
) -> Response:
    try:
        record = service.get(product_id)
        if kind not in record.artifacts:
            raise LookupError(kind)
        service.verify(record)
        payload = service.read_artifact(product_id, kind)
    except DrainIntegrityError as exc:
        raise HTTPException(409, "drain product integrity check failed") from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, "drain artifact unavailable") from exc
    except LookupError as exc:
        raise HTTPException(404, "drain product or artifact not found") from exc
    return Response(content=payload, media_type="application/json")


@router.get("/qa", response_class=HTMLResponse)
def qa() -> HTMLResponse:
    return HTMLResponse(QA_VIEWER_HTML)
