"""Dependency construction for the Sequence 6 terrain worker."""

from sqlalchemy.orm import Session

from floodguard.common.config import get_settings
from floodguard.harvester.factory import build_harvester_service
from floodguard.harvester.repository import HarvesterRepository
from floodguard.spatial.object_store import MinioSpatialObjectStore
from floodguard.terrain.acquisition import TerrainAcquirer
from floodguard.terrain.importer import TerrainInputImporter
from floodguard.terrain.repository import TerrainRepository
from floodguard.terrain.service import TerrainService


def build_terrain_service(session: Session) -> TerrainService:
    settings = get_settings()
    object_store = MinioSpatialObjectStore(
        endpoint=settings.object_store_endpoint,
        access_key=settings.object_store_access_key,
        secret_key=settings.object_store_secret_key,
        raw_bucket=settings.raw_bucket,
        spatial_bucket=settings.spatial_bucket,
        secure=settings.object_store_secure,
    )
    return TerrainService(
        TerrainRepository(session),
        object_store,
        working_crs=settings.working_crs,
        max_object_bytes=settings.spatial_max_object_bytes,
    )


def build_terrain_acquirer(session: Session) -> TerrainAcquirer:
    settings = get_settings()
    return TerrainAcquirer(
        TerrainInputImporter(
            HarvesterRepository(session), build_harvester_service(session).vault,
            build_terrain_service(session), max_total_bytes=settings.harvest_max_total_bytes,
            max_object_bytes=settings.harvest_max_object_bytes,
        ),
        timeout_seconds=settings.harvest_timeout_seconds,
    )
