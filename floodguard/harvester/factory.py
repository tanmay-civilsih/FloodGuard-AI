"""Dependency construction for the consolidated SIH harvester worker."""

from sqlalchemy.orm import Session

from floodguard.common.config import get_settings
from floodguard.harvester.acquisition import AcquisitionPlanner, UrlLibTransport
from floodguard.harvester.repository import HarvesterRepository
from floodguard.harvester.service import HarvesterService
from floodguard.harvester.vault import MinioRawVault


def build_harvester_service(session: Session) -> HarvesterService:
    settings = get_settings()
    vault = MinioRawVault(
        endpoint=settings.object_store_endpoint,
        access_key=settings.object_store_access_key,
        secret_key=settings.object_store_secret_key,
        bucket=settings.raw_bucket,
        secure=settings.object_store_secure,
    )
    return HarvesterService(
        HarvesterRepository(session),
        vault,
        AcquisitionPlanner(UrlLibTransport()),
        max_object_bytes=settings.harvest_max_object_bytes,
        max_total_bytes=settings.harvest_max_total_bytes,
        max_resources_per_source=settings.harvest_max_resources_per_source,
        timeout_seconds=settings.harvest_timeout_seconds,
    )
