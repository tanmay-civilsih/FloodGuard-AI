"""Read-only historical evidence and lightweight rainfall preview."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from floodguard.history.contracts import HistoricalEventManifest
from floodguard.history.factory import build_history_service
from floodguard.history.preview import render_preview
from floodguard.history.service import HistoryService
from floodguard.registry.database import get_db_session

router = APIRouter(prefix="/history", tags=["historical evidence"])


def get_history_service(session: Session = Depends(get_db_session)) -> HistoryService:
    return build_history_service(session)


@router.get("/preview", response_class=HTMLResponse)
def preview() -> str:
    return render_preview()


@router.get("/events")
def events(
    city_id: str = Query(default="kolkata", min_length=1, max_length=100),
    service: HistoryService = Depends(get_history_service),
) -> list[dict[str, Any]]:
    return service.list_events(city_id)


@router.get("/events/{event_id}", response_model=HistoricalEventManifest)
def event(
    event_id: UUID,
    service: HistoryService = Depends(get_history_service),
) -> HistoricalEventManifest:
    try:
        return service.get(event_id)
    except FileNotFoundError as exc:
        raise HTTPException(503, "historical artifact unavailable") from exc
    except LookupError as exc:
        raise HTTPException(404, "historical event not found") from exc
    except ValueError as exc:
        raise HTTPException(409, "historical event integrity check failed") from exc


@router.get("/events/{event_id}/view")
def view(event_id: UUID, service: HistoryService = Depends(get_history_service)) -> dict[str, Any]:
    try:
        return service.view(event_id)
    except FileNotFoundError as exc:
        raise HTTPException(503, "historical artifact unavailable") from exc
    except LookupError as exc:
        raise HTTPException(404, "historical event not found") from exc
    except ValueError as exc:
        raise HTTPException(409, "historical event integrity check failed") from exc
