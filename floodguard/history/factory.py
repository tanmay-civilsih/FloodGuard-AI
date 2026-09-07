"""Configured event service using existing raw and scientific storage."""

from sqlalchemy.orm import Session

from floodguard.forcing.factory import build_forcing_service
from floodguard.harvester.factory import build_harvester_service
from floodguard.history.service import HistoryService


def build_history_service(session: Session) -> HistoryService:
    return HistoryService(
        session,
        build_forcing_service(session),
        build_harvester_service(session),
    )
