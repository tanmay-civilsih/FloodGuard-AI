"""Sequence 3 orchestration: governance gate, change detection, and raw-vault writes."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid4, uuid5

from floodguard.contracts.time import utc_now
from floodguard.harvester.acquisition import AcquisitionPlanner, DownloadedObject
from floodguard.harvester.contracts import (
    DatasetVersionRead,
    DatasetVersionStatus,
    HarvestDisposition,
    HarvestReadiness,
    HarvestResult,
)
from floodguard.harvester.repository import HarvesterRepository, RawObjectPersistence
from floodguard.harvester.vault import RawVault
from floodguard.registry.contracts import (
    AccessClass,
    AuthenticationType,
    SourceRead,
    SourceStatus,
)

HARVEST_NAMESPACE = UUID("6871d123-22f0-44d4-b17a-2cf9813e6396")
_OBJECT_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
_USER_AGENT = "FloodGuard-AI/0.3 (+https://github.com/tanmay-civilsih/FloodGuard-AI)"


class HarvestAccessError(PermissionError):
    pass


class CredentialResolutionError(HarvestAccessError):
    pass


class HarvestConflictError(RuntimeError):
    pass


class TotalDownloadLimitError(RuntimeError):
    pass


def dataset_id_for_source(source_id: UUID) -> UUID:
    return uuid5(HARVEST_NAMESPACE, f"dataset:{source_id}")


def _source_snapshot(source: SourceRead) -> dict[str, object]:
    return dict(source.model_dump(mode="json"))


def _material_provenance(source: SourceRead) -> dict[str, object]:
    return {
        "provider": source.provider,
        "dataset_name": source.dataset_name,
        "endpoint": source.endpoint,
        "access_method": source.access_method.value,
        "format": source.format,
        "licence": source.licence,
        "redistribution_policy": source.redistribution_policy,
        "authority_level": source.authority_level.value,
        "horizontal_crs": source.horizontal_crs,
        "vertical_datum": source.vertical_datum,
        "spatial_resolution": source.spatial_resolution,
        "temporal_resolution": source.temporal_resolution,
    }


def _safe_object_segment(value: str, *, field: str) -> str:
    if not _OBJECT_SEGMENT.fullmatch(value):
        raise ValueError(f"{field} contains characters unsafe for raw object keys")
    return value


def _resolve_credential(credential_ref: str) -> str:
    if credential_ref.startswith("env://"):
        name = credential_ref.removeprefix("env://")
        value = os.environ.get(name)
        if not value:
            raise CredentialResolutionError(
                f"credential environment variable is not set: {name}"
            )
        return value
    if credential_ref.startswith("docker-secret://"):
        name = credential_ref.removeprefix("docker-secret://")
        path = Path("/run/secrets") / name
        if not path.is_file():
            raise CredentialResolutionError(f"Docker secret is not mounted: {name}")
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise CredentialResolutionError(f"Docker secret is empty: {name}")
        return value
    raise CredentialResolutionError(
        "secret:// references require a future secrets-manager adapter and cannot be resolved here"
    )


def _authorization_headers(
    source: SourceRead,
    *,
    include_authorized: bool,
    parameters: Mapping[str, object],
) -> dict[str, str]:
    headers = {"User-Agent": _USER_AGENT}
    if source.authentication_type is AuthenticationType.NONE:
        return headers
    if not include_authorized:
        raise HarvestAccessError(
            "authorized source skipped unless include_authorized is explicitly enabled"
        )
    if source.credential_ref is None:
        raise CredentialResolutionError("authenticated source has no credential_ref")
    credential = _resolve_credential(source.credential_ref)
    if source.authentication_type in {
        AuthenticationType.BEARER_TOKEN,
        AuthenticationType.OAUTH2,
        AuthenticationType.EARTHDATA_LOGIN,
    }:
        headers["Authorization"] = f"Bearer {credential}"
        return headers
    if source.authentication_type is AuthenticationType.API_KEY:
        header_value = parameters.get("api_key_header")
        if not isinstance(header_value, str) or not header_value.strip():
            raise CredentialResolutionError(
                "API_KEY acquisition requires an explicit api_key_header parameter"
            )
        headers[header_value] = credential
        return headers
    raise CredentialResolutionError(
        f"authentication type {source.authentication_type.value} has no generic adapter"
    )


def _manifest_fingerprint(source: SourceRead, objects: list[DownloadedObject]) -> str:
    payload = {
        "source_id": str(source.source_id),
        "source_provenance": _material_provenance(source),
        "objects": [
            {
                "filename": item.filename,
                "source_url": item.source_url,
                "sha256": item.sha256,
                "byte_size": item.byte_size,
            }
            for item in sorted(objects, key=lambda value: (value.source_url, value.filename))
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class HarvesterService:
    def __init__(
        self,
        repository: HarvesterRepository,
        vault: RawVault,
        planner: AcquisitionPlanner,
        *,
        max_object_bytes: int,
        max_total_bytes: int,
        max_resources_per_source: int,
        timeout_seconds: float,
    ) -> None:
        self.repository = repository
        self.vault = vault
        self.planner = planner
        self.max_object_bytes = max_object_bytes
        self.max_total_bytes = max_total_bytes
        self.max_resources_per_source = max_resources_per_source
        self.timeout_seconds = timeout_seconds

    def harvest_source(
        self,
        source: SourceRead,
        *,
        parameters: Mapping[str, object] | None = None,
        include_authorized: bool = False,
    ) -> HarvestResult:
        params = parameters or {}
        self._enforce_governance(source, include_authorized=include_authorized)
        headers = _authorization_headers(
            source,
            include_authorized=include_authorized,
            parameters=params,
        )
        requests = self.planner.plan(source, parameters=params, headers=headers)
        if len(requests) > self.max_resources_per_source:
            raise TotalDownloadLimitError(
                f"source exposes {len(requests)} resources; configured limit is "
                f"{self.max_resources_per_source}"
            )

        self.vault.ensure_ready()
        with tempfile.TemporaryDirectory(prefix="floodguard-harvest-") as directory:
            workspace = Path(directory)
            downloaded: list[DownloadedObject] = []
            total_bytes = 0
            for index, request in enumerate(requests):
                destination = workspace / f"{index:04d}-{request.filename}"
                item = self.planner.transport.download(
                    request,
                    destination,
                    max_bytes=self.max_object_bytes,
                    timeout_seconds=self.timeout_seconds,
                )
                total_bytes += item.byte_size
                if total_bytes > self.max_total_bytes:
                    raise TotalDownloadLimitError(
                        "source download exceeded configured total limit of "
                        f"{self.max_total_bytes} bytes"
                    )
                downloaded.append(item)
            return self._persist_downloads(source, downloaded, total_bytes=total_bytes)

    def _persist_downloads(
        self,
        source: SourceRead,
        downloaded: list[DownloadedObject],
        *,
        total_bytes: int,
    ) -> HarvestResult:
        manifest_sha256 = _manifest_fingerprint(source, downloaded)
        dataset_id = dataset_id_for_source(source.source_id)
        existing = self.repository.find_by_manifest(source.source_id, manifest_sha256)
        if existing is not None:
            if existing.status == DatasetVersionStatus.COMPLETE.value:
                return HarvestResult(
                    source_id=source.source_id,
                    dataset_id=dataset_id,
                    dataset_version_id=existing.dataset_version_id,
                    disposition=HarvestDisposition.UNCHANGED,
                    reason="upstream bytes match an existing immutable version",
                    manifest_sha256=manifest_sha256,
                    object_count=existing.object_count,
                    total_bytes=existing.total_bytes,
                )
            raise HarvestConflictError(
                "the same upstream manifest already has a non-complete version; "
                "inspect it before retry"
            )

        previous = self.repository.latest_complete(source.source_id)
        dataset_version_id = uuid4()
        acquired_at = utc_now()
        record, created = self.repository.reserve_version(
            dataset_version_id=dataset_version_id,
            dataset_id=dataset_id,
            source_id=source.source_id,
            city_id=source.city_id,
            acquired_at=acquired_at,
            manifest_sha256=manifest_sha256,
            previous_version_id=previous.dataset_version_id if previous is not None else None,
            source_snapshot=_source_snapshot(source),
        )
        if not created:
            if record.status == DatasetVersionStatus.COMPLETE.value:
                return HarvestResult(
                    source_id=source.source_id,
                    dataset_id=dataset_id,
                    dataset_version_id=record.dataset_version_id,
                    disposition=HarvestDisposition.UNCHANGED,
                    reason="concurrent harvest already persisted these bytes",
                    manifest_sha256=manifest_sha256,
                    object_count=record.object_count,
                    total_bytes=record.total_bytes,
                )
            raise HarvestConflictError("concurrent harvest reserved this manifest")

        city_segment = _safe_object_segment(source.city_id, field="city_id")
        prefix = f"raw/{city_segment}/{source.source_id}/{dataset_version_id}"
        persisted: list[RawObjectPersistence] = []
        try:
            for index, item in enumerate(downloaded):
                object_key = f"{prefix}/objects/{index:04d}-{item.filename}"
                self.vault.put_file_once(
                    object_key,
                    item.path,
                    content_type=item.content_type,
                )
                persisted.append(
                    RawObjectPersistence(
                        object_id=uuid5(dataset_version_id, object_key),
                        dataset_version_id=dataset_version_id,
                        object_key=object_key,
                        filename=item.filename,
                        source_url=item.source_url,
                        sha256=item.sha256,
                        byte_size=item.byte_size,
                        content_type=item.content_type,
                        etag=item.etag,
                        last_modified=item.last_modified,
                    )
                )

            manifest_object_key = f"{prefix}/manifest.json"
            manifest_payload = {
                "schema_version": 1,
                "dataset_id": str(dataset_id),
                "dataset_version_id": str(dataset_version_id),
                "source_id": str(source.source_id),
                "city_id": source.city_id,
                "acquired_at": acquired_at.isoformat(),
                "previous_version_id": (
                    str(previous.dataset_version_id) if previous is not None else None
                ),
                "manifest_sha256": manifest_sha256,
                "source_snapshot": _source_snapshot(source),
                "objects": [
                    {
                        "object_key": item.object_key,
                        "filename": item.filename,
                        "source_url": item.source_url,
                        "sha256": item.sha256,
                        "byte_size": item.byte_size,
                        "content_type": item.content_type,
                        "etag": item.etag,
                        "last_modified": item.last_modified,
                    }
                    for item in persisted
                ],
            }
            encoded_manifest = json.dumps(
                manifest_payload,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
            self.vault.put_bytes_once(
                manifest_object_key,
                encoded_manifest,
                content_type="application/json",
            )
            completed = self.repository.complete_version(
                dataset_version_id,
                manifest_object_key=manifest_object_key,
                objects=persisted,
                total_bytes=total_bytes,
            )
        except Exception as exc:
            self.repository.fail_version(dataset_version_id, str(exc))
            raise

        return HarvestResult(
            source_id=source.source_id,
            dataset_id=dataset_id,
            dataset_version_id=completed.dataset_version_id,
            disposition=HarvestDisposition.CREATED,
            manifest_sha256=manifest_sha256,
            object_count=completed.object_count,
            total_bytes=completed.total_bytes,
        )

    def get_version(self, dataset_version_id: UUID) -> DatasetVersionRead:
        record = self.repository.get_version(dataset_version_id)
        if record is None:
            raise LookupError(str(dataset_version_id))
        return DatasetVersionRead.model_validate(record)

    def list_source_versions(self, source_id: UUID) -> list[DatasetVersionRead]:
        return [
            DatasetVersionRead.model_validate(record)
            for record in self.repository.list_for_source(source_id)
        ]

    def readiness(
        self,
        *,
        city_id: str,
        sources: list[SourceRead],
        raw_bucket: str,
    ) -> HarvestReadiness:
        permitted = [
            source
            for source in sources
            if source.city_id == city_id
            and source.automation_allowed
            and source.status is SourceStatus.AVAILABLE
            and source.access_class
            in {AccessClass.OPEN_AUTOMATED, AccessClass.AUTHORIZATION_REQUIRED}
        ]
        harvested = self.repository.harvested_source_ids(city_id=city_id)
        complete_versions, failed_versions = self.repository.readiness_counts(city_id=city_id)
        permitted_ids = {source.source_id for source in permitted}
        return HarvestReadiness(
            city_id=city_id,
            automation_permitted_sources=len(permitted),
            harvested_sources=len(permitted_ids & harvested),
            complete_versions=complete_versions,
            failed_versions=failed_versions,
            unharvested_source_ids=sorted(permitted_ids - harvested, key=str),
            raw_bucket=raw_bucket,
        )

    @staticmethod
    def _enforce_governance(source: SourceRead, *, include_authorized: bool) -> None:
        if source.status is not SourceStatus.AVAILABLE:
            raise HarvestAccessError(f"source status is {source.status.value}, not AVAILABLE")
        if not source.automation_allowed:
            raise HarvestAccessError("registry does not permit automated acquisition")
        if source.access_class is AccessClass.OPEN_AUTOMATED:
            return
        if source.access_class is AccessClass.AUTHORIZATION_REQUIRED and include_authorized:
            return
        raise HarvestAccessError(
            f"access class {source.access_class.value} is not enabled for this harvest"
        )
