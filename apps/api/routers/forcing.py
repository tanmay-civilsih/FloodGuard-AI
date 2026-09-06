"""Immutable forcing reads. Build/recreation remains an explicit operator CLI action."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from floodguard.forcing.contracts import Product
from floodguard.forcing.factory import build_forcing_service
from floodguard.forcing.service import ForcingService
from floodguard.registry.database import get_db_session

router = APIRouter(prefix="/forcing", tags=["forcing"])


def get_forcing_service(session: Session = Depends(get_db_session)) -> ForcingService:
    return build_forcing_service(session)


@router.get("/readiness")
def readiness(
    city_id: str = Query(default="kolkata", min_length=1, max_length=100),
    service: ForcingService = Depends(get_forcing_service),
) -> dict[str, Any]:
    return service.readiness(city_id)


@router.get("/products", response_model=list[Product])
def products(
    city_id: str = Query(default="kolkata", min_length=1, max_length=100),
    service: ForcingService = Depends(get_forcing_service),
) -> list[Product]:
    return service.list(city_id)


@router.get("/products/{package_id}", response_model=Product)
def product(package_id: UUID, service: ForcingService = Depends(get_forcing_service)) -> Product:
    try:
        return service.get(package_id)
    except LookupError as exc:
        raise HTTPException(404, "forcing package not found") from exc


@router.get("/products/{package_id}/{kind}")
def artifact(
    package_id: UUID, kind: str, service: ForcingService = Depends(get_forcing_service)
) -> Response:
    try:
        payload = service.read_artifact(package_id, kind)
    except FileNotFoundError as exc:
        raise HTTPException(503, "forcing artifact unavailable") from exc
    except LookupError as exc:
        raise HTTPException(404, "forcing package or artifact not found") from exc
    except ValueError as exc:
        raise HTTPException(409, "forcing identity or integrity check failed") from exc
    return Response(
        payload, media_type="application/zip" if kind.endswith(".zip") else "application/json"
    )
