"""Dependency construction for the Sequence 7 urban GIS service."""

from sqlalchemy.orm import Session

from floodguard.common.config import get_settings
from floodguard.spatial.object_store import MinioSpatialObjectStore
from floodguard.urban_gis.repository import UrbanGisRepository
from floodguard.urban_gis.service import UrbanGisService


def build_urban_gis_service(session: Session) -> UrbanGisService:
    settings = get_settings()
    object_store = MinioSpatialObjectStore(
        endpoint=settings.object_store_endpoint,
        access_key=settings.object_store_access_key,
        secret_key=settings.object_store_secret_key,
        raw_bucket=settings.raw_bucket,
        spatial_bucket=settings.spatial_bucket,
        secure=settings.object_store_secure,
    )
    return UrbanGisService(
        UrbanGisRepository(session),
        object_store,
        working_crs=settings.working_crs,
    )
