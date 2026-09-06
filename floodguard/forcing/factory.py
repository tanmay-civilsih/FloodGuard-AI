"""Configured forcing service."""

from sqlalchemy.orm import Session

from floodguard.forcing.service import ForcingService
from floodguard.twin.factory import build_twin_service


def build_forcing_service(session: Session) -> ForcingService:
    return ForcingService(session, build_twin_service(session))
