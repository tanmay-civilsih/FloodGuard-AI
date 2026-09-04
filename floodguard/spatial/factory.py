"""Dependency construction for the consolidated Sequence 4 spatial worker."""

from sqlalchemy.orm import Session

from floodguard.common.config import get_settings
from floodguard.spatial.object_store import MinioSpatialObjectStore
from floodguard.spatial.repository import SpatialRepository
from floodguard.spatial.service import SpatialService


def build_spatial_service(session: Session) -> SpatialService:
    settings = get_settings()
    object_store = MinioSpatialObjectStore(
        endpoint=settings.object_store_endpoint,
        access_key=settings.object_store_access_key,
        secret_key=settings.object_store_secret_key,
        raw_bucket=settings.raw_bucket,
        spatial_bucket=settings.spatial_bucket,
        secure=settings.object_store_secure,
    )
    return SpatialService(
        SpatialRepository(session),
        object_store,
        working_crs=settings.working_crs,
        alignment_tolerance_m=settings.spatial_alignment_tolerance_m,
        rainfall_conservation_tolerance=settings.rainfall_conservation_tolerance,
        max_object_bytes=settings.spatial_max_object_bytes,
    )
