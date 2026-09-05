"""Explicit local SRTM import with immutable source bytes and an auditable receipt.

This is a manual ingestion path, not an automated portal downloader. The registry's
access classification is retained. An operator must supply their actual access basis.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, Field

from floodguard.contracts.time import utc_now
from floodguard.harvester.contracts import DatasetVersionRead, DatasetVersionStatus
from floodguard.harvester.repository import HarvesterRepository, RawObjectPersistence
from floodguard.harvester.service import (
    HarvestAccessError,
    HarvestConflictError,
    dataset_id_for_source,
)
from floodguard.harvester.vault import RawVault
from floodguard.registry.contracts import AccessClass, SourceCategory, SourceRead, SourceStatus
from floodguard.registry.seed import seed_id
from floodguard.terrain.contracts import TerrainBuildResult, TerrainInput
from floodguard.terrain.grid import package_bytes, sha256
from floodguard.terrain.service import TerrainService
from floodguard.terrain.srtm import SrtmTarget, convert_srtm

IMPORT_VERSION = "sequence-6-local-srtm-import-v1"


class SrtmImportRequest(TerrainInput):
    filename: str
    target: SrtmTarget
    pilot_area_id: str = Field(min_length=1, max_length=160)
    boundary_reference: str = Field(min_length=2, max_length=500)
    imported_by: str = Field(min_length=1, max_length=200)
    access_reference: str = Field(min_length=10, max_length=1000)


class SrtmImportResult(BaseModel):
    dry_run: bool
    raw_sha256: str
    package_sha256: str
    width: int
    height: int
    raw_version_created: bool = False
    dataset_version_id: UUID | None = None
    terrain: TerrainBuildResult | None = None


@dataclass(frozen=True, slots=True)
class ImportObject:
    filename: str
    payload: bytes
    content_type: str
    source_url: str


class TerrainInputImporter:
    def __init__(
        self,
        repository: HarvesterRepository,
        vault: RawVault,
        terrain: TerrainService,
        *,
        max_total_bytes: int,
        max_object_bytes: int | None = None,
    ) -> None:
        self.repository = repository
        self.vault = vault
        self.terrain = terrain
        self.max_total_bytes = max_total_bytes
        self.max_object_bytes = min(
            terrain.max_object_bytes,
            max_object_bytes if max_object_bytes is not None else terrain.max_object_bytes,
        )

    def import_srtm(
        self,
        source: SourceRead,
        payload: bytes,
        request: SrtmImportRequest,
        *,
        dry_run: bool = False,
    ) -> SrtmImportResult:
        if (
            source.source_id != seed_id("nasa-srtmgl1")
            or source.category is not SourceCategory.ELEVATION
        ):
            raise ValueError("SRTM importer requires the registered NASA SRTMGL1 source")
        if source.status is not SourceStatus.AVAILABLE or source.access_class not in {
            AccessClass.OPEN_AUTOMATED,
            AccessClass.OPEN_MANUAL,
            AccessClass.AUTHORIZATION_REQUIRED,
        }:
            raise HarvestAccessError("source governance does not permit this explicit local import")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", source.city_id):
            raise ValueError("city_id is unsafe for raw object keys")
        if request.target.working_crs != self.terrain.working_crs:
            raise ValueError("import target must match the configured metric working CRS")
        if len(payload) > self.max_object_bytes:
            raise ValueError("original elevation exceeds configured object size limit")
        package = convert_srtm(
            payload,
            filename=request.filename,
            target=request.target,
            pilot_area_id=request.pilot_area_id,
            boundary_reference=request.boundary_reference,
        )
        encoded_package = package_bytes(package)
        receipt = {
            "import_version": IMPORT_VERSION,
            "mode": "OPERATOR_SUPPLIED_LOCAL_FILE",
            "product": "SRTMGL1.003",
            "request": request.model_dump(mode="json"),
            "source_id": str(source.source_id),
            "source_reference": source.endpoint,
            "source_sha256": sha256(payload),
            "package_sha256": sha256(encoded_package),
            "access_evidence_verification": "OPERATOR_ASSERTED_NOT_INDEPENDENTLY_VERIFIED",
            "network_acquisition_performed": False,
        }
        encoded_receipt = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        derived_url = f"urn:floodguard:derived:srtmgl1:{sha256(payload)}"
        objects = [
            ImportObject(request.filename, payload, "application/octet-stream", source.endpoint),
            ImportObject("pilot.terrain.json", encoded_package, "application/json", derived_url),
            ImportObject("import-receipt.json", encoded_receipt, "application/json", derived_url),
        ]
        total_bytes = sum(len(item.payload) for item in objects)
        if total_bytes > self.max_total_bytes or any(
            len(item.payload) > self.max_object_bytes for item in objects
        ):
            raise ValueError("terrain import exceeds configured storage limits")
        result = SrtmImportResult(
            dry_run=dry_run,
            raw_sha256=sha256(payload),
            package_sha256=sha256(encoded_package),
            width=package.grid.width,
            height=package.grid.height,
        )
        if dry_run:
            return result
        version, created = self._persist(source, receipt, objects, total_bytes)
        package_object = next(
            item for item in version.objects if item.filename == "pilot.terrain.json"
        )
        built = self.terrain.build_from_raw(source, version, package_object)
        return result.model_copy(
            update={
                "dataset_version_id": version.dataset_version_id,
                "raw_version_created": created,
                "terrain": built,
            }
        )

    def _persist(
        self,
        source: SourceRead,
        receipt: dict[str, object],
        objects: list[ImportObject],
        total_bytes: int,
    ) -> tuple[DatasetVersionRead, bool]:
        snapshot = source.model_dump(mode="json")
        identity = {
            "import_version": IMPORT_VERSION,
            "source_snapshot": snapshot,
            "receipt": receipt,
            "objects": [
                {
                    "filename": item.filename,
                    "sha256": sha256(item.payload),
                    "byte_size": len(item.payload),
                }
                for item in objects
            ],
        }
        fingerprint = sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())
        existing = self.repository.find_by_manifest(source.source_id, fingerprint)
        if existing is not None:
            if existing.status != DatasetVersionStatus.COMPLETE.value:
                raise HarvestConflictError(
                    "this import has an incomplete version; inspect it before retry"
                )
            return DatasetVersionRead.model_validate(existing), False
        previous = self.repository.latest_complete(source.source_id)
        version_id = uuid4()
        record, created = self.repository.reserve_version(
            dataset_version_id=version_id,
            dataset_id=dataset_id_for_source(source.source_id),
            source_id=source.source_id,
            city_id=source.city_id,
            acquired_at=utc_now(),
            manifest_sha256=fingerprint,
            source_snapshot=snapshot,
            previous_version_id=previous.dataset_version_id if previous is not None else None,
        )
        if not created:
            if record.status == DatasetVersionStatus.COMPLETE.value:
                return DatasetVersionRead.model_validate(record), False
            raise HarvestConflictError("concurrent import reserved this manifest")
        prefix = f"raw/{source.city_id}/{source.source_id}/{version_id}"
        entries: list[RawObjectPersistence] = []
        try:
            self.vault.ensure_ready()
            for index, item in enumerate(objects):
                key = f"{prefix}/objects/{index:04d}-{item.filename}"
                self.vault.put_bytes_once(key, item.payload, content_type=item.content_type)
                entries.append(
                    RawObjectPersistence(
                        object_id=uuid5(version_id, key),
                        dataset_version_id=version_id,
                        object_key=key,
                        filename=item.filename,
                        source_url=item.source_url,
                        sha256=sha256(item.payload),
                        byte_size=len(item.payload),
                        content_type=item.content_type,
                        etag=None,
                        last_modified=None,
                    )
                )
            manifest_key = f"{prefix}/manifest.json"
            manifest = {
                **identity,
                "dataset_version_id": str(version_id),
                "manifest_sha256": fingerprint,
                "object_keys": [item.object_key for item in entries],
            }
            self.vault.put_bytes_once(
                manifest_key,
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
                content_type="application/json",
            )
            complete = self.repository.complete_version(
                version_id,
                manifest_object_key=manifest_key,
                objects=entries,
                total_bytes=total_bytes,
            )
        except Exception as exc:
            self.repository.session.rollback()
            self.repository.fail_version(version_id, str(exc))
            raise
        return DatasetVersionRead.model_validate(complete), True
