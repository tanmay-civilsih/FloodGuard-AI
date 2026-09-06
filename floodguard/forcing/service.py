"""Content-addressed forcing packages, verified recreation and read-only eligibility."""

from __future__ import annotations

from contextlib import suppress
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from floodguard.common.integrity import verified_payload
from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.forcing.assessment import prepare
from floodguard.forcing.contracts import Assessment, BuildRequest, BuildResult, Manifest, Product
from floodguard.forcing.models import ForcingRecord
from floodguard.spatial.object_store import SpatialObjectExistsError
from floodguard.twin.contracts import BlobReference, ComponentRole, TwinManifest
from floodguard.twin.service import TwinService

NAMESPACE = UUID("c14b0dfe-3633-4e7d-bcb0-4a3f8d61ed99")
MAX_BYTES = 128 * 1024 * 1024


def reference(payload: bytes) -> BlobReference:
    digest = sha256(payload)
    return BlobReference(
        object_key=f"forcing/blobs/{digest}", sha256=digest, byte_size=len(payload)
    )


def identity(manifest: Manifest) -> tuple[UUID, str]:
    content = manifest.model_dump(mode="json", exclude={"forcing_package_id"})
    digest = sha256(canonical_bytes(content))
    return uuid5(NAMESPACE, digest), digest


class ForcingService:
    def __init__(self, session: Session, twins: TwinService) -> None:
        self.session = session
        self.twins = twins
        self.store = twins.store

    def read_blob(self, ref: BlobReference) -> bytes:
        if ref.byte_size > MAX_BYTES:
            raise ValueError("forcing artifact exceeds prototype size bound")
        return verified_payload(
            self.store.read_spatial(ref.object_key),
            expected_sha256=ref.sha256,
            expected_size=ref.byte_size,
            max_bytes=MAX_BYTES,
        )

    def write_blob(self, payload: bytes) -> BlobReference:
        ref = reference(payload)
        if len(payload) > MAX_BYTES:
            raise ValueError("forcing artifact exceeds prototype size bound")
        with suppress(SpatialObjectExistsError):
            self.store.put_spatial_once(
                ref.object_key, payload, content_type="application/octet-stream"
            )
        self.read_blob(ref)
        return ref

    def twin_inputs(self, manifest: TwinManifest) -> dict[str, bytes]:
        inputs = {}
        terrain = manifest.component(ComponentRole.HYDRAULIC_TERRAIN).artifact
        if terrain is not None:
            inputs[ComponentRole.HYDRAULIC_TERRAIN.value] = self.read_blob(terrain)
        if "drain-input" in manifest.evidence_artifacts:
            inputs["drain-input"] = self.read_blob(manifest.evidence_artifacts["drain-input"])
        return inputs

    def preview(self, request: BuildRequest) -> Assessment:
        request = BuildRequest.model_validate_json(request.model_dump_json())
        manifest = self.twins.verify(self.twins.get(request.twin_id))
        return prepare(request, manifest, self.twin_inputs(manifest), encode=False)[0]

    def build(self, request: BuildRequest) -> BuildResult:
        # Revalidate even when a caller constructed/mutated a Pydantic model without validation.
        request = BuildRequest.model_validate_json(request.model_dump_json())
        twin_bytes = self.twins.read_artifact(request.twin_id, "manifest")
        twin = TwinManifest.model_validate_json(twin_bytes)
        assessment, artifacts = prepare(request, twin, self.twin_inputs(twin))
        artifacts["request.json"] = canonical_bytes(request.model_dump(mode="json"))
        artifacts["twin-manifest.json"] = twin_bytes
        self.store.ensure_ready()
        manifest = Manifest(
            forcing_package_id=UUID(int=0),
            twin_id=twin.twin_id,
            city_id=twin.city_id,
            issue_time=request.issue_time,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            software_version=self.twins.software_version,
            software_source_sha256=self.twins.software_source_sha256,
            artifacts={name: self.write_blob(payload) for name, payload in artifacts.items()},
            quality_summary=assessment,
        )
        manifest.forcing_package_id = identity(manifest)[0]
        return self.recreate(canonical_bytes(manifest.model_dump(mode="json")))

    def validate(self, payload: bytes) -> Manifest:
        if len(payload) > MAX_BYTES:
            raise ValueError("forcing manifest exceeds size bound")
        manifest = Manifest.model_validate_json(payload)
        if identity(manifest)[0] != manifest.forcing_package_id:
            raise ValueError("forcing manifest identity mismatch")
        artifacts = {name: self.read_blob(ref) for name, ref in manifest.artifacts.items()}
        if any(reference(artifacts[name]) != ref for name, ref in manifest.artifacts.items()):
            raise ValueError("forcing artifact address mismatch")
        if not {"request.json", "twin-manifest.json"}.issubset(artifacts):
            raise ValueError("forcing package lacks immutable input evidence")
        request = BuildRequest.model_validate_json(artifacts["request.json"])
        twin = self.twins.validate_manifest(artifacts["twin-manifest.json"])
        if (
            manifest.twin_id != request.twin_id
            or manifest.city_id != twin.city_id
            or manifest.issue_time != request.issue_time
            or manifest.valid_from != request.valid_from
            or manifest.valid_to != request.valid_to
        ):
            raise ValueError("forcing manifest identity/window differs from frozen inputs")
        assessment, expected = prepare(request, twin, self.twin_inputs(twin))
        if assessment != manifest.quality_summary:
            raise ValueError("forcing assessment differs from immutable inputs")
        if set(artifacts) != {*expected, "request.json", "twin-manifest.json"}:
            raise ValueError("forcing artifact inventory differs from immutable inputs")
        if any(artifacts[name] != value for name, value in expected.items()):
            raise ValueError("forcing artifacts differ from deterministic input computation")
        return manifest

    def recreate(self, payload: bytes) -> BuildResult:
        manifest = self.validate(payload)
        _, digest = identity(manifest)
        self.store.ensure_ready()
        ref = self.write_blob(canonical_bytes(manifest.model_dump(mode="json")))
        existing = self.session.get(ForcingRecord, manifest.forcing_package_id)
        created = existing is None
        if existing is None:
            self.session.add(
                ForcingRecord(
                    forcing_package_id=manifest.forcing_package_id,
                    twin_id=manifest.twin_id,
                    city_id=manifest.city_id,
                    fingerprint=digest,
                    manifest=ref.model_dump(mode="json"),
                )
            )
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                if self.session.get(ForcingRecord, manifest.forcing_package_id) is None:
                    raise
                created = False
        self.verify(self.get(manifest.forcing_package_id))
        return BuildResult(
            forcing_package_id=manifest.forcing_package_id,
            created=created,
            quality_summary=manifest.quality_summary,
        )

    def get(self, package_id: UUID) -> Product:
        record = self.session.get(ForcingRecord, package_id)
        if record is None:
            raise LookupError(str(package_id))
        return Product.model_validate(record, from_attributes=True)

    def list(self, city_id: str) -> list[Product]:
        records = self.session.scalars(
            select(ForcingRecord)
            .where(ForcingRecord.city_id == city_id)
            .order_by(ForcingRecord.created_at.desc())
        )
        return [Product.model_validate(r, from_attributes=True) for r in records]

    def verify(self, product: Product) -> Manifest:
        payload = self.read_blob(product.manifest)
        manifest = self.validate(payload)
        if (
            identity(manifest)[1] != product.fingerprint
            or manifest.twin_id != product.twin_id
            or manifest.city_id != product.city_id
            or reference(payload) != product.manifest
            or manifest.forcing_package_id != product.forcing_package_id
        ):
            raise ValueError("forcing registry identity differs from manifest")
        return manifest

    def read_artifact(self, package_id: UUID, name: str) -> bytes:
        product = self.get(package_id)
        manifest = self.verify(product)
        if name == "manifest":
            return self.read_blob(product.manifest)
        if name not in manifest.artifacts:
            raise LookupError(name)
        return self.read_blob(manifest.artifacts[name])

    def require_hydraulic_use(self, package_id: UUID, twin_id: UUID) -> Manifest:
        manifest = self.verify(self.get(package_id))
        if manifest.twin_id != twin_id or not manifest.quality_summary.hydraulic_use_eligible:
            raise ValueError("forcing package is ineligible for this twin/hydraulic horizon")
        return manifest

    def readiness(self, city_id: str) -> dict[str, Any]:
        products = self.list(city_id)
        verified, eligible, failures = 0, 0, []
        for product in products:
            try:
                manifest = self.verify(product)
                verified += 1
                eligible += int(manifest.quality_summary.hydraulic_use_eligible)
            except (ValueError, FileNotFoundError, LookupError) as exc:
                failures.append(f"{product.forcing_package_id}: {type(exc).__name__}")
        return dict(
            city_id=city_id,
            total_packages=len(products),
            verified_packages=verified,
            eligible_packages=eligible,
            integrity_failures=failures,
            assembly_development_gate_passed=eligible > 0 and not failures,
            inherited_freeze_blockers=self.twins.readiness(city_id).freeze_blockers,
            final_human_acceptance_pending=True,
            operational_validation_claimed=False,
        )
