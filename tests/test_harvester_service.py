from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from floodguard.contracts.time import utc_now
from floodguard.harvester.acquisition import AcquisitionPlanner, DownloadedObject, RemoteRequest
from floodguard.harvester.contracts import HarvestDisposition
from floodguard.harvester.models import DatasetVersionRecord
from floodguard.harvester.repository import HarvesterRepository
from floodguard.harvester.service import HarvestAccessError, HarvesterService
from floodguard.harvester.vault import ImmutableObjectExistsError, MemoryRawVault
from floodguard.registry.contracts import (
    AccessClass,
    AccessMethod,
    AuthenticationType,
    AuthorityLevel,
    SourceCategory,
    SourceRead,
    SourceStatus,
)
from floodguard.registry.models import Base


class FakeTransport:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def get_json(self, url: str, *, headers: dict[str, str]) -> dict[str, object]:
        del url, headers
        return {}

    def download(
        self,
        request: RemoteRequest,
        destination: Path,
        *,
        max_bytes: int,
        timeout_seconds: float,
    ) -> DownloadedObject:
        del timeout_seconds
        if len(self.payload) > max_bytes:
            raise RuntimeError("test payload too large")
        destination.write_bytes(self.payload)
        return DownloadedObject(
            source_url=request.url,
            filename=request.filename,
            path=destination,
            sha256=hashlib.sha256(self.payload).hexdigest(),
            byte_size=len(self.payload),
            content_type="text/csv",
            etag=None,
            last_modified=None,
        )


def source(*, automated: bool = True) -> SourceRead:
    now = utc_now()
    return SourceRead(
        source_id=uuid4(),
        provider="Test provider",
        dataset_name="Test dataset",
        city_id="kolkata",
        category=SourceCategory.WARD_BOUNDARY,
        endpoint="https://example.test/data.csv",
        access_method=AccessMethod.HTTP,
        format="CSV",
        licence="Test licence",
        redistribution_policy="Test redistribution policy",
        automation_allowed=automated,
        access_class=AccessClass.OPEN_AUTOMATED if automated else AccessClass.OPEN_MANUAL,
        authentication_type=AuthenticationType.NONE,
        authority_level=AuthorityLevel.COMMUNITY,
        refresh_policy="On demand",
        fallback_strategy="Use the last immutable version",
        status=SourceStatus.AVAILABLE,
        created_at=now,
        updated_at=now,
    )


def service(session: Session, transport: FakeTransport, vault: MemoryRawVault) -> HarvesterService:
    return HarvesterService(
        HarvesterRepository(session),
        vault,
        AcquisitionPlanner(transport),
        max_object_bytes=1024 * 1024,
        max_total_bytes=2 * 1024 * 1024,
        max_resources_per_source=10,
        timeout_seconds=5,
    )


def test_same_bytes_are_unchanged_and_changed_bytes_create_new_version() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    vault = MemoryRawVault()
    transport = FakeTransport(b"a,b\n1,2\n")

    with Session(engine) as session:
        target = source()
        harvester = service(session, transport, vault)
        first = harvester.harvest_source(target)
        assert first.disposition is HarvestDisposition.CREATED
        assert first.dataset_version_id is not None
        first_version_id = first.dataset_version_id
        first_keys = set(vault.objects)
        assert len(first_keys) == 2  # raw object + manifest

        second = harvester.harvest_source(target)
        assert second.disposition is HarvestDisposition.UNCHANGED
        assert second.dataset_version_id == first_version_id
        assert set(vault.objects) == first_keys

        transport.payload = b"a,b\n3,4\n"
        third = harvester.harvest_source(target)
        assert third.disposition is HarvestDisposition.CREATED
        assert third.dataset_version_id is not None
        assert third.dataset_version_id != first_version_id
        assert first_keys < set(vault.objects)

        latest = session.get(DatasetVersionRecord, third.dataset_version_id)
        assert latest is not None
        assert latest.previous_version_id == first_version_id
        assert latest.object_count == 1


def test_registry_governance_blocks_manual_sources() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        harvester = service(session, FakeTransport(b"data"), MemoryRawVault())
        with pytest.raises(HarvestAccessError):
            harvester.harvest_source(source(automated=False))


def test_memory_vault_never_overwrites_existing_key(tmp_path: Path) -> None:
    vault = MemoryRawVault()
    path = tmp_path / "source.bin"
    path.write_bytes(b"one")
    vault.put_file_once("raw/test/object", path)
    path.write_bytes(b"two")
    with pytest.raises(ImmutableObjectExistsError):
        vault.put_file_once("raw/test/object", path)
    assert vault.objects["raw/test/object"] == b"one"
