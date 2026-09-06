"""Immutable twin construction, independent manifest recreation and conservative freeze gates."""

from __future__ import annotations

from contextlib import suppress
from typing import Any
from uuid import UUID, uuid5

from floodguard.common.integrity import verified_payload
from floodguard.drainage.contracts import DrainEvidenceScope
from floodguard.drainage.model_contracts import HydraulicReadiness
from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.spatial.object_store import SpatialObjectExistsError, SpatialObjectStore
from floodguard.twin.contracts import (
    TWIN_POLICY,
    BlobReference,
    ComponentRole,
    ComponentVersion,
    TwinBuildResult,
    TwinManifest,
    TwinProductRead,
    TwinReadiness,
)
from floodguard.twin.models import TwinRecord
from floodguard.twin.repository import TwinRepository
from floodguard.twin.snapshot import Snapshot, evaluate, object_data

NAMESPACE = UUID("ff25d5dc-6af4-46ad-b253-0c711b785fa7")


class TwinIntegrityError(ValueError):
    """Frozen twin identity or artifact content cannot be verified."""


def blob_reference(payload: bytes) -> BlobReference:
    digest = sha256(payload)
    return BlobReference(
        object_key=f"twins/blobs/{digest}.json", sha256=digest, byte_size=len(payload)
    )


def manifest_identity(content: dict[str, Any]) -> tuple[UUID, str]:
    core = {key: value for key, value in content.items() if key != "twin_id"}
    digest = sha256(canonical_bytes(core))
    return uuid5(NAMESPACE, digest), digest


class TwinService:
    def __init__(
        self,
        repository: TwinRepository,
        store: SpatialObjectStore,
        *,
        working_crs: str,
        software_version: str,
        software_source_sha256: str,
        max_bytes: int = 128 * 1024 * 1024,
    ) -> None:
        self.repository = repository
        self.store = store
        self.working_crs = working_crs
        self.software_version = software_version
        self.software_source_sha256 = software_source_sha256
        self.max_bytes = max_bytes

    def build(self, snapshot: Snapshot) -> TwinBuildResult:
        if snapshot.horizontal_crs != self.working_crs:
            raise ValueError("twin must use configured working CRS")
        blockers, compatible, real_cross = evaluate(snapshot)
        components = {}
        for role in ComponentRole:
            if role in snapshot.components:
                components[role.value] = ComponentVersion(
                    status="AVAILABLE",
                    source=snapshot.sources[role],
                    artifact=blob_reference(snapshot.components[role]),
                )
            else:
                components[role.value] = ComponentVersion(
                    status="MISSING", missing_reason=snapshot.missing[role]
                )
        values = dict(
            city_id=snapshot.city_id,
            pilot_area=snapshot.pilot_area,
            evidence_scope=snapshot.evidence_scope,
            horizontal_crs=snapshot.horizontal_crs,
            vertical_reference_status="COMPATIBLE" if compatible else "UNRESOLVED",
            hydraulic_readiness=HydraulicReadiness.VISUAL_ONLY
            if blockers
            else HydraulicReadiness.HYDRAULIC_SCENARIO_READY,
            software_version=self.software_version,
            software_source_sha256=self.software_source_sha256,
            evidence_artifacts={
                name: blob_reference(value) for name, value in snapshot.evidence.items()
            },
            readiness_blockers=blockers,
            real_cross_ward_path_available=real_cross,
            **components,
        )
        temporary = TwinManifest.model_validate({"twin_id": UUID(int=0), **values})
        twin_id, _ = manifest_identity(temporary.model_dump(mode="json"))
        manifest = TwinManifest.model_validate(
            {**temporary.model_dump(mode="json"), "twin_id": twin_id}
        )
        self.store.ensure_ready()
        for payload in [*snapshot.components.values(), *snapshot.evidence.values()]:
            self._write(blob_reference(payload), payload)
        return self.recreate(canonical_bytes(manifest.model_dump(mode="json")))

    def _write(self, reference: BlobReference, payload: bytes) -> None:
        verified_payload(
            payload,
            expected_sha256=reference.sha256,
            expected_size=reference.byte_size,
            max_bytes=self.max_bytes,
        )
        with suppress(SpatialObjectExistsError):
            self.store.put_spatial_once(
                reference.object_key, payload, content_type="application/json"
            )
        self._read(reference)

    def _read(self, reference: BlobReference) -> bytes:
        if reference.byte_size > self.max_bytes:
            raise TwinIntegrityError("twin artifact exceeds configured size limit")
        try:
            return verified_payload(
                self.store.read_spatial(reference.object_key),
                expected_sha256=reference.sha256,
                expected_size=reference.byte_size,
                max_bytes=self.max_bytes,
            )
        except ValueError as exc:
            raise TwinIntegrityError(str(exc)) from exc

    def validate_manifest(self, payload: bytes) -> TwinManifest:
        if len(payload) > self.max_bytes:
            raise TwinIntegrityError("manifest exceeds configured size limit")
        manifest = TwinManifest.model_validate(object_data(payload))
        twin_id, _ = manifest_identity(manifest.model_dump(mode="json"))
        if manifest.twin_id != twin_id:
            raise TwinIntegrityError("manifest content does not match its twin_id")
        if manifest.horizontal_crs != self.working_crs:
            raise TwinIntegrityError("manifest CRS differs from configured twin service")
        snapshot = Snapshot(
            manifest.city_id, manifest.pilot_area, manifest.horizontal_crs, manifest.evidence_scope
        )
        for role in ComponentRole:
            component = manifest.component(role)
            if component.artifact is None:
                snapshot.missing[role] = component.missing_reason or "Missing"
                continue
            if component.source is None:
                raise TwinIntegrityError("available component has no source")
            content = self._read(component.artifact)
            if component.artifact != blob_reference(content):
                raise TwinIntegrityError("component location must match its content address")
            snapshot.add(role, content, component.source)
            if snapshot.sources[role] != component.source:
                raise TwinIntegrityError("component source hash does not match artifact bytes")
        for name, reference in manifest.evidence_artifacts.items():
            value = self._read(reference)
            if reference != blob_reference(value):
                raise TwinIntegrityError("evidence location must match its content address")
            snapshot.evidence[name] = value
        blockers, compatible, real_cross = evaluate(snapshot)
        status = (
            HydraulicReadiness.VISUAL_ONLY
            if blockers
            else HydraulicReadiness.HYDRAULIC_SCENARIO_READY
        )
        if (
            manifest.readiness_blockers != blockers
            or manifest.hydraulic_readiness is not status
            or manifest.real_cross_ward_path_available != real_cross
            or manifest.vertical_reference_status != ("COMPATIBLE" if compatible else "UNRESOLVED")
        ):
            raise TwinIntegrityError(
                "manifest readiness differs from its frozen component evidence"
            )
        return manifest

    def recreate(self, payload: bytes) -> TwinBuildResult:
        """Re-register frozen bytes without querying upstream products or latest versions."""
        manifest = self.validate_manifest(payload)
        canonical = canonical_bytes(manifest.model_dump(mode="json"))
        _, fingerprint = manifest_identity(manifest.model_dump(mode="json"))
        manifest_ref = BlobReference(
            object_key=f"twins/{manifest.twin_id}/manifest.json",
            sha256=sha256(canonical),
            byte_size=len(canonical),
        )
        audit_bytes = canonical_bytes(
            {
                "pipeline_version": TWIN_POLICY,
                "twin_id": str(manifest.twin_id),
                "fingerprint": fingerprint,
                "manifest_sha256": manifest_ref.sha256,
                "software_version": manifest.software_version,
                "software_source_sha256": manifest.software_source_sha256,
                "component_recreation": "EXACT_FROZEN_BYTES_NO_LATEST_LOOKUPS",
                "final_human_acceptance": "PENDING_SEQUENCE_20",
            }
        )
        audit_ref = BlobReference(
            object_key=f"twins/{manifest.twin_id}/audit.json",
            sha256=sha256(audit_bytes),
            byte_size=len(audit_bytes),
        )
        existing = self.repository.get(manifest.twin_id)
        if existing is not None:
            self.verify(self.repository.read(existing))
            return TwinBuildResult(
                twin_id=manifest.twin_id,
                created=False,
                hydraulic_readiness=manifest.hydraulic_readiness,
            )
        self.store.ensure_ready()
        self._write(manifest_ref, canonical)
        self._write(audit_ref, audit_bytes)
        record, created = self.repository.add(
            TwinRecord(
                twin_id=manifest.twin_id,
                city_id=manifest.city_id,
                pilot_area_id=manifest.pilot_area.pilot_area_id,
                fingerprint=fingerprint,
                pipeline_version=TWIN_POLICY,
                evidence_scope=manifest.evidence_scope.value,
                hydraulic_readiness=manifest.hydraulic_readiness.value,
                manifest=manifest_ref.model_dump(mode="json"),
                audit=audit_ref.model_dump(mode="json"),
            )
        )
        self.verify(self.repository.read(record))
        return TwinBuildResult(
            twin_id=record.twin_id,
            created=created,
            hydraulic_readiness=manifest.hydraulic_readiness,
        )

    def get(self, twin_id: UUID) -> TwinProductRead:
        record = self.repository.get(twin_id)
        if record is None:
            raise LookupError(str(twin_id))
        return self.repository.read(record)

    def list(self, city_id: str) -> list[TwinProductRead]:
        return [self.repository.read(r) for r in self.repository.list(city_id)]

    def verify(self, record: TwinProductRead) -> TwinManifest:
        manifest = self.validate_manifest(self._read(record.manifest))
        _, fingerprint = manifest_identity(manifest.model_dump(mode="json"))
        if (
            record.twin_id != manifest.twin_id
            or record.city_id != manifest.city_id
            or record.pilot_area_id != manifest.pilot_area.pilot_area_id
            or record.pipeline_version != TWIN_POLICY
            or record.fingerprint != fingerprint
            or record.evidence_scope is not manifest.evidence_scope
            or record.hydraulic_readiness is not manifest.hydraulic_readiness
            or record.manifest.object_key != f"twins/{manifest.twin_id}/manifest.json"
            or record.audit.object_key != f"twins/{manifest.twin_id}/audit.json"
        ):
            raise TwinIntegrityError("twin metadata differs from immutable manifest")
        audit = object_data(self._read(record.audit))
        if (
            audit.get("twin_id") != str(manifest.twin_id)
            or audit.get("fingerprint") != fingerprint
            or audit.get("manifest_sha256") != record.manifest.sha256
            or audit.get("software_source_sha256") != manifest.software_source_sha256
            or audit.get("pipeline_version") != TWIN_POLICY
        ):
            raise TwinIntegrityError("twin audit differs from manifest")
        return manifest

    def read_artifact(self, twin_id: UUID, name: str) -> bytes:
        record = self.get(twin_id)
        manifest = self.verify(record)
        if name == "manifest":
            return self._read(record.manifest)
        if name == "audit":
            return self._read(record.audit)
        try:
            role = ComponentRole(name)
        except ValueError as exc:
            raise LookupError(name) from exc
        component = manifest.component(role)
        if component.artifact is None:
            raise LookupError("component is explicitly missing")
        return self._read(component.artifact)

    def readiness(self, city_id: str) -> TwinReadiness:
        records = self.list(city_id)
        verified = references = real = cross = 0
        for record in records:
            try:
                manifest = self.verify(record)
            except (ValueError, KeyError, FileNotFoundError):
                continue
            verified += 1
            is_real = manifest.evidence_scope is DrainEvidenceScope.REAL_PILOT_PROVISIONAL
            real += int(is_real)
            cross += int(is_real and manifest.real_cross_ward_path_available)
            references += int(
                not is_real
                and manifest.hydraulic_readiness is HydraulicReadiness.HYDRAULIC_SCENARIO_READY
            )
        assembly = references > 0 and real > 0
        blockers = []
        if not assembly:
            blockers.append(
                "A recreated scenario-ready reference and real provisional twin are required."
            )
        if not cross:
            blockers.append(
                "DATA-08-01: genuine source-bound adjacent-ward drainage is still required."
            )
        return TwinReadiness(
            city_id=city_id,
            total_twins=len(records),
            verified_twins=verified,
            reference_scenario_ready=references,
            provisional_real_twins=real,
            real_cross_ward_twins=cross,
            assembly_development_gate_passed=assembly,
            technical_development_gate_passed=not blockers,
            checkpoint_a_status="PROVISIONAL_REAL_READY"
            if cross
            else "REFERENCE_ONLY"
            if references
            else "NOT_READY",
            freeze_blockers=blockers,
        )
