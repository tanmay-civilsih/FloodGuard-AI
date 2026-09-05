"""Dependency construction for the Sequence 6 terrain worker."""

from sqlalchemy.orm import Session

from floodguard.common.config import get_settings
from floodguard.spatial.object_store import MinioSpatialObjectStore
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
