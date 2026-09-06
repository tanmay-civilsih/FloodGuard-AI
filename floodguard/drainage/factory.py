"""Construct the drain model service using the existing object store and database."""

from sqlalchemy.orm import Session

from floodguard.common.config import get_settings
from floodguard.drainage.repository import DrainRepository
from floodguard.drainage.service import DrainService
from floodguard.spatial.object_store import MinioSpatialObjectStore


def build_drain_service(session: Session) -> DrainService:
    settings = get_settings()
    return DrainService(
        DrainRepository(session),
        MinioSpatialObjectStore(
            endpoint=settings.object_store_endpoint,
            access_key=settings.object_store_access_key,
            secret_key=settings.object_store_secret_key,
            raw_bucket=settings.raw_bucket,
            spatial_bucket=settings.spatial_bucket,
            secure=settings.object_store_secure,
        ),
        working_crs=settings.working_crs,
        max_bytes=settings.spatial_max_object_bytes,
    )
