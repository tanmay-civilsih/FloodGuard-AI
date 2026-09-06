"""Construct twin and input-loader services from the local configured platform."""

from pathlib import Path

from sqlalchemy.orm import Session

from floodguard import __version__
from floodguard.common.config import get_settings
from floodguard.common.release_evidence import source_fingerprint
from floodguard.drainage.factory import build_drain_service
from floodguard.spatial.factory import build_spatial_service
from floodguard.terrain.factory import build_terrain_service
from floodguard.twin.loader import TwinSourceLoader
from floodguard.twin.repository import TwinRepository
from floodguard.twin.service import TwinService
from floodguard.urban_gis.factory import build_urban_gis_service


def build_twin_service(session: Session) -> TwinService:
    settings = get_settings()
    drain = build_drain_service(session)
    return TwinService(
        TwinRepository(session),
        drain.store,
        working_crs=settings.working_crs,
        software_version=__version__,
        software_source_sha256=source_fingerprint(Path(__file__).resolve().parents[2]),
        max_bytes=settings.spatial_max_object_bytes,
    )


def build_source_loader(session: Session) -> TwinSourceLoader:
    return TwinSourceLoader(
        build_terrain_service(session),
        build_urban_gis_service(session),
        build_drain_service(session),
        build_spatial_service(session),
        max_bytes=get_settings().spatial_max_object_bytes,
    )
