"""Dependency construction for the Sequence 5 reconstruction worker."""

from sqlalchemy.orm import Session

from floodguard.common.config import get_settings
from floodguard.reconstruction.repository import ReconstructionRepository
from floodguard.reconstruction.service import ReconstructionService
from floodguard.spatial.object_store import MinioSpatialObjectStore


def build_reconstruction_service(session: Session) -> ReconstructionService:
    settings = get_settings()
    object_store = MinioSpatialObjectStore(
        endpoint=settings.object_store_endpoint,
        access_key=settings.object_store_access_key,
        secret_key=settings.object_store_secret_key,
        raw_bucket=settings.raw_bucket,
        spatial_bucket=settings.spatial_bucket,
        secure=settings.object_store_secure,
    )
    return ReconstructionService(
        ReconstructionRepository(session),
        object_store,
        working_crs=settings.working_crs,
        max_object_bytes=settings.spatial_max_object_bytes,
    )

