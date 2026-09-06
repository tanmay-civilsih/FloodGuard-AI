"""Trace the approved pilot to a public SRTM tile, cache it, and build terrain."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from pydantic import Field
from sqlalchemy.orm import Session

from floodguard.harvester.contracts import DatasetVersionRead, DatasetVersionStatus, RawObjectRead
from floodguard.harvester.service import HarvestAccessError
from floodguard.reconstruction.repository import ReconstructionRepository
from floodguard.registry.contracts import AccessClass, AuthenticationType, SourceRead, SourceStatus
from floodguard.registry.seed import ESA_SRTM_BASE_URL, ESA_SRTM_ID
from floodguard.registry.service import RegistryService
from floodguard.terrain.assessment import TerrainAssessment
from floodguard.terrain.contracts import TerrainInput, TerrainPackage
from floodguard.terrain.download import SrtmArchive, archive_url, download_srtm, unpack_srtm
from floodguard.terrain.grid import decode_package, package_bytes, sha256
from floodguard.terrain.importer import SrtmImportRequest, SrtmImportResult, TerrainInputImporter
from floodguard.terrain.pilot import select_pilot
from floodguard.terrain.srtm import SrtmTarget, convert_srtm, required_srtm_tiles, target_grid


class TerrainAcquisitionRequest(TerrainInput):
    city_id: str = Field(default="kolkata", min_length=1, max_length=100)
    ward_id: str = Field(default="7", min_length=1, max_length=100)
    cell_size_m: float = Field(default=30.0, gt=0)


class TerrainAcquisitionPlan(TerrainInput):
    request: TerrainAcquisitionRequest
    source_id: UUID
    reconstruction_id: UUID
    boundary_reference: str
    pilot_area_id: str
    target: SrtmTarget
    tile: str
    source_url: str


class TerrainAcquisitionResult(TerrainInput):
    source_url: str
    downloaded: bool
    result: SrtmImportResult


class ArchiveDownloader(Protocol):
    def __call__(
        self, tile: str, *, max_bytes: int, timeout_seconds: float
    ) -> SrtmArchive: ...


def check_mirror(source: SourceRead) -> None:
    if (
        source.source_id != ESA_SRTM_ID or source.endpoint != ESA_SRTM_BASE_URL
        or source.access_class is not AccessClass.OPEN_AUTOMATED
        or not source.automation_allowed
        or source.authentication_type is not AuthenticationType.NONE
        or source.status is not SourceStatus.AVAILABLE
    ):
        raise HarvestAccessError("the registered ESA SRTM mirror does not permit this acquisition")


def plan_acquisition(
    session: Session, request: TerrainAcquisitionRequest, *, working_crs: str
) -> TerrainAcquisitionPlan:
    source = RegistryService(session).get_source(ESA_SRTM_ID)
    check_mirror(source)
    if source.city_id != request.city_id:
        raise ValueError("the registered SRTM mirror does not cover this configured city")
    repository = ReconstructionRepository(session)
    pilot = select_pilot(
        repository.reads(repository.list_reconstructions(city_id=request.city_id)),
        request.city_id, request.ward_id, working_crs,
    )
    target = SrtmTarget(
        working_crs=working_crs, bounds_working=pilot.bounds_working,
        cell_size_m=request.cell_size_m,
    )
    tiles = required_srtm_tiles(target)
    if len(tiles) != 1:
        raise ValueError("pilot requires multiple SRTM tiles; this adapter does not mosaic them")
    return TerrainAcquisitionPlan(
        request=request, source_id=source.source_id, reconstruction_id=pilot.reconstruction_id,
        boundary_reference=(
            f"reconstruction://{pilot.reconstruction_id}#working_sha256={pilot.working_sha256}"
        ),
        pilot_area_id=f"{request.city_id}-ward-{request.ward_id}",
        target=target, tile=tiles[0], source_url=archive_url(tiles[0]),
    )


class TerrainAcquirer:
    def __init__(
        self, importer: TerrainInputImporter, *, timeout_seconds: float,
        downloader: ArchiveDownloader = download_srtm,
    ) -> None:
        self.importer = importer
        self.timeout_seconds = timeout_seconds
        self.downloader = downloader

    def _raw_bytes(self, item: RawObjectRead) -> bytes:
        if item.byte_size > self.importer.max_object_bytes:
            raise ValueError("cached terrain input exceeds the configured size limit")
        payload = self.importer.terrain.object_store.read_raw(item.object_key)
        if len(payload) != item.byte_size or sha256(payload) != item.sha256:
            raise ValueError("cached terrain input does not match its immutable manifest")
        return payload

    def _cached(
        self, source: SourceRead, plan: TerrainAcquisitionPlan
    ) -> tuple[DatasetVersionRead | None, RawObjectRead | None, TerrainPackage | None]:
        fallback = None
        geometry = target_grid(plan.target).model_dump()
        for record in self.importer.repository.list_for_source(source.source_id):
            if record.status != DatasetVersionStatus.COMPLETE.value:
                continue
            version = DatasetVersionRead.model_validate(record)
            if not any(item.filename == f"{plan.tile}.SRTMGL1.hgt.zip" for item in version.objects):
                continue
            if fallback is None:
                fallback = version
            package_object = next(
                (item for item in version.objects if item.filename == "pilot.terrain.json"), None
            )
            if package_object is None:
                continue
            package = decode_package(self._raw_bytes(package_object))
            if (
                package.pilot_area_id == plan.pilot_area_id and package.derivation
                and package.derivation.boundary_reference == plan.boundary_reference
                and package.grid.model_dump(exclude={"elevations_m"}) == geometry
            ):
                return version, package_object, package
        return fallback, None, None

    def acquire(
        self, source: SourceRead, plan: TerrainAcquisitionPlan,
        *, assessment: TerrainAssessment | None = None, dry_run: bool = False,
        check_pilot: Callable[[], None] | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> TerrainAcquisitionResult:
        check_mirror(source)
        if source.source_id != plan.source_id or source.city_id != plan.request.city_id:
            raise ValueError("acquisition source does not match the pilot plan")
        update = progress or (lambda stage: None)
        update("Checking stored terrain")
        version, package_object, package = self._cached(source, plan)
        archive = None
        if version is not None:
            archive_object = next(
                item for item in version.objects if item.filename == f"{plan.tile}.SRTMGL1.hgt.zip"
            )
            acquired_at = version.acquired_at
            if acquired_at.tzinfo is None:
                acquired_at = acquired_at.replace(tzinfo=UTC)
            receipt_object = next(
                (item for item in version.objects if item.filename == "import-receipt.json"), None
            )
            if receipt_object:
                receipt = json.loads(self._raw_bytes(receipt_object))
                acquired_at = datetime.fromisoformat(receipt["acquisition"]["downloaded_at"])
            archive = SrtmArchive(
                source_url=archive_object.source_url, filename=archive_object.filename,
                payload=self._raw_bytes(archive_object), downloaded_at=acquired_at,
                etag=archive_object.etag, last_modified=archive_object.last_modified,
            )
        downloaded = archive is None
        if archive is None:
            update(f"Downloading {plan.tile} from ESA STEP")
            archive = self.downloader(
                plan.tile, max_bytes=self.importer.max_object_bytes,
                timeout_seconds=self.timeout_seconds,
            )
        update("Checking the original elevation file")
        filename, payload = unpack_srtm(archive, plan.tile)
        if check_pilot:
            check_pilot()  # A changed/rejected reconstruction cannot be committed after a download.
        update("Building terrain")
        if version and package_object and package and assessment is None and not dry_run:
            built = self.importer.terrain.build_from_raw(source, version, package_object)
            base = convert_srtm(
                payload, filename=filename, target=plan.target, pilot_area_id=plan.pilot_area_id,
                boundary_reference=plan.boundary_reference,
            )
            result = SrtmImportResult(
                dry_run=False, raw_sha256=sha256(payload),
                base_package_sha256=sha256(package_bytes(base)),
                package_sha256=sha256(package_bytes(package)), width=package.grid.width,
                height=package.grid.height, dataset_version_id=version.dataset_version_id,
                terrain=built,
            )
        else:
            request = SrtmImportRequest(
                filename=filename, target=plan.target, pilot_area_id=plan.pilot_area_id,
                boundary_reference=plan.boundary_reference,
                imported_by="FloodGuard automatic terrain acquisition",
                access_reference=f"Public ESA STEP mirror: {plan.source_url}",
            )
            result = self.importer.import_srtm(
                source, payload, request, archive=archive, assessment=assessment, dry_run=dry_run
            )
        return TerrainAcquisitionResult(
            source_url=plan.source_url, downloaded=downloaded, result=result
        )
