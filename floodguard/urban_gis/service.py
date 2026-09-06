"""Immutable Sequence 7 visual-city, hydraulic-surface and roof-policy products."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID, uuid5

from floodguard.spatial.object_store import SpatialObjectExistsError, SpatialObjectStore
from floodguard.urban_gis.contracts import (
    URBAN_GIS_PIPELINE_VERSION,
    HydraulicDomain,
    HydraulicFeature,
    HydraulicSurfaceClass,
    UrbanGisBuildResult,
    UrbanGisEvidenceScope,
    UrbanGisPackage,
    UrbanGisProductRead,
    UrbanGisReadiness,
    UrbanGisReadinessStatus,
    VisualFeature,
)
from floodguard.urban_gis.models import UrbanGisRecord
from floodguard.urban_gis.repository import UrbanGisRepository

URBAN_GIS_NAMESPACE = UUID("5a91b4c3-d321-4c24-8956-b9dd9e7a5ea1")


class UrbanGisError(RuntimeError):
    """Raised when a Sequence 7 product violates immutable or integrity rules."""


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def package_bytes(package: UrbanGisPackage) -> bytes:
    return _json_bytes(package.model_dump(mode="json"))


def _put_idempotent(
    object_store: SpatialObjectStore,
    object_key: str,
    payload: bytes,
    *,
    content_type: str,
) -> None:
    try:
        object_store.put_spatial_once(object_key, payload, content_type=content_type)
    except SpatialObjectExistsError as exc:
        if object_store.read_spatial(object_key) != payload:
            raise UrbanGisError(
                f"immutable urban GIS key exists with different bytes: {object_key}"
            ) from exc


def _feature_geojson(
    feature: VisualFeature | HydraulicFeature,
    representation: Literal["VISUAL", "HYDRAULIC"],
) -> dict[str, object]:
    properties: dict[str, object] = {
        "feature_id": feature.feature_id,
        "source_reference": feature.source_reference,
        "representation": representation,
    }
    if isinstance(feature, VisualFeature):
        if representation != "VISUAL":
            raise ValueError("visual feature cannot be serialized as hydraulic")
        properties.update(
            visual_class=feature.visual_class.value,
            height_m=feature.height_m,
        )
    else:
        if representation != "HYDRAULIC":
            raise ValueError("hydraulic feature cannot be serialized as visual")
        properties.update(
            surface_class=feature.surface_class.value,
            hydraulic_domain=feature.hydraulic_domain.value,
            hydrology=(
                feature.hydrology.model_dump(mode="json")
                if feature.hydrology is not None
                else None
            ),
        )
    return {
        "type": "Feature",
        "id": feature.feature_id,
        "properties": properties,
        "geometry": feature.geometry,
    }


def _readiness_status(package: UrbanGisPackage) -> UrbanGisReadinessStatus:
    mapping = {
        UrbanGisEvidenceScope.REFERENCE_FIXTURE: UrbanGisReadinessStatus.REFERENCE_READY,
        UrbanGisEvidenceScope.REAL_PILOT_PROVISIONAL: (
            UrbanGisReadinessStatus.REAL_PILOT_PROVISIONAL
        ),
        UrbanGisEvidenceScope.REAL_PILOT_REVIEWED: UrbanGisReadinessStatus.REAL_PILOT_REVIEWED,
    }
    return mapping[package.evidence_scope]


class UrbanGisService:
    def __init__(
        self,
        repository: UrbanGisRepository,
        object_store: SpatialObjectStore,
        *,
        working_crs: str,
    ) -> None:
        self.repository = repository
        self.object_store = object_store
        self.working_crs = working_crs

    def build(self, package: UrbanGisPackage) -> UrbanGisBuildResult:
        if package.working_crs != self.working_crs:
            raise UrbanGisError("urban GIS package must use the configured working CRS")
        self.object_store.ensure_ready()

        fingerprint = sha256(
            _json_bytes(
                {
                    "pipeline_version": URBAN_GIS_PIPELINE_VERSION,
                    "package_sha256": sha256(package_bytes(package)),
                }
            )
        )
        existing = self.repository.find_by_fingerprint(fingerprint)
        if existing is not None:
            self._verify_artifacts(existing)
            return UrbanGisBuildResult(
                urban_gis_id=existing.urban_gis_id,
                created=False,
                readiness_status=UrbanGisReadinessStatus(existing.readiness_status),
                visual_feature_count=existing.visual_feature_count,
                hydraulic_feature_count=existing.hydraulic_feature_count,
                roof_feature_count=existing.roof_feature_count,
            )

        urban_gis_id = uuid5(URBAN_GIS_NAMESPACE, fingerprint)
        prefix = f"urban-gis/{package.city_id}/{package.pilot_area_id}/{urban_gis_id}"

        visual_bytes = _json_bytes(
            {
                "type": "FeatureCollection",
                "features": [
                    _feature_geojson(feature, "VISUAL") for feature in package.visual_features
                ],
                "floodguard_crs": package.working_crs,
            }
        )
        hydraulic_bytes = _json_bytes(
            {
                "type": "FeatureCollection",
                "features": [
                    _feature_geojson(feature, "HYDRAULIC")
                    for feature in package.hydraulic_features
                ],
                "floodguard_crs": package.working_crs,
            }
        )
        roof_bytes = _json_bytes(
            {
                "policy_version": package.roof_runoff_policy_version,
                "surface_cell_binding": "DEFERRED_TO_LATER_SEQUENCE",
                "rules": [rule.model_dump(mode="json") for rule in package.roof_runoff_rules],
            }
        )

        qa_features: list[dict[str, object]] = [
            *[_feature_geojson(feature, "VISUAL") for feature in package.visual_features],
            *[
                _feature_geojson(feature, "HYDRAULIC")
                for feature in package.hydraulic_features
            ],
        ]
        for rule in package.roof_runoff_rules:
            receiving = rule.receiving_geometry
            if receiving is not None:
                qa_features.append(
                    {
                        "type": "Feature",
                        "id": receiving.receiving_geometry_id,
                        "properties": {
                            "representation": "ROOF_RECEIVING_GEOMETRY",
                            "roof_feature_id": rule.roof_feature_id,
                            "version": receiving.version,
                        },
                        "geometry": receiving.geometry,
                    }
                )
        qa_bytes = _json_bytes(
            {
                "type": "FeatureCollection",
                "features": qa_features,
                "floodguard_crs": package.working_crs,
            }
        )

        roof_count = sum(
            feature.surface_class is HydraulicSurfaceClass.ROOF
            for feature in package.hydraulic_features
        )
        domain_ownership_complete = all(
            feature.hydraulic_domain is not HydraulicDomain.VISUAL_ONLY
            for feature in package.hydraulic_features
        )
        roof_rules_complete = roof_count == len(package.roof_runoff_rules)
        readiness_status = _readiness_status(package)
        audit_bytes = _json_bytes(
            {
                "artifact_version": "sequence-7-urban-gis-audit-v1",
                "urban_gis_id": str(urban_gis_id),
                "pipeline_version": URBAN_GIS_PIPELINE_VERSION,
                "fingerprint": fingerprint,
                "evidence_scope": package.evidence_scope.value,
                "policies": {
                    "surface": package.surface_policy_version,
                    "roof_runoff": package.roof_runoff_policy_version,
                },
                "invariants": {
                    "domain_ownership_complete": domain_ownership_complete,
                    "roof_rules_complete": roof_rules_complete,
                    "surface_cell_ids_assigned": False,
                },
                "source_references": package.source_references,
                "limitations": package.limitations,
            }
        )

        keys = {
            "visual": f"{prefix}/visual_city.geojson",
            "hydraulic": f"{prefix}/hydraulic_surface.geojson",
            "roof": f"{prefix}/roof_runoff.json",
            "qa": f"{prefix}/qa.geojson",
            "audit": f"{prefix}/audit.json",
        }
        for object_key, payload, content_type in (
            (keys["visual"], visual_bytes, "application/geo+json"),
            (keys["hydraulic"], hydraulic_bytes, "application/geo+json"),
            (keys["roof"], roof_bytes, "application/json"),
            (keys["qa"], qa_bytes, "application/geo+json"),
            (keys["audit"], audit_bytes, "application/json"),
        ):
            _put_idempotent(
                self.object_store,
                object_key,
                payload,
                content_type=content_type,
            )

        record = UrbanGisRecord(
            urban_gis_id=urban_gis_id,
            city_id=package.city_id,
            pilot_area_id=package.pilot_area_id,
            urban_gis_fingerprint=fingerprint,
            pipeline_version=URBAN_GIS_PIPELINE_VERSION,
            working_crs=package.working_crs,
            evidence_scope=package.evidence_scope.value,
            visual_object_key=keys["visual"],
            hydraulic_object_key=keys["hydraulic"],
            roof_runoff_object_key=keys["roof"],
            qa_object_key=keys["qa"],
            audit_object_key=keys["audit"],
            visual_sha256=sha256(visual_bytes),
            hydraulic_sha256=sha256(hydraulic_bytes),
            roof_runoff_sha256=sha256(roof_bytes),
            qa_sha256=sha256(qa_bytes),
            audit_sha256=sha256(audit_bytes),
            visual_feature_count=len(package.visual_features),
            hydraulic_feature_count=len(package.hydraulic_features),
            roof_feature_count=roof_count,
            domain_ownership_complete=domain_ownership_complete,
            roof_rules_complete=roof_rules_complete,
            readiness_status=readiness_status.value,
            limitations=list(package.limitations),
        )
        persisted, created = self.repository.add(record)
        self._verify_artifacts(persisted)
        return UrbanGisBuildResult(
            urban_gis_id=persisted.urban_gis_id,
            created=created,
            readiness_status=UrbanGisReadinessStatus(persisted.readiness_status),
            visual_feature_count=persisted.visual_feature_count,
            hydraulic_feature_count=persisted.hydraulic_feature_count,
            roof_feature_count=persisted.roof_feature_count,
        )

    def get(self, urban_gis_id: UUID) -> UrbanGisProductRead:
        record = self.repository.get(urban_gis_id)
        if record is None:
            raise LookupError(str(urban_gis_id))
        return self.repository.read(record)

    def list_products(self, *, city_id: str | None = None) -> list[UrbanGisProductRead]:
        return self.repository.reads(self.repository.list_products(city_id=city_id))

    def read_artifact(self, urban_gis_id: UUID, kind: str) -> bytes:
        record = self.repository.get(urban_gis_id)
        if record is None:
            raise LookupError(str(urban_gis_id))
        artifacts: dict[str, tuple[str, str]] = {
            "visual": (record.visual_object_key, record.visual_sha256),
            "hydraulic": (record.hydraulic_object_key, record.hydraulic_sha256),
            "roof-runoff": (record.roof_runoff_object_key, record.roof_runoff_sha256),
            "qa": (record.qa_object_key, record.qa_sha256),
            "audit": (record.audit_object_key, record.audit_sha256),
        }
        if kind not in artifacts:
            raise ValueError("unsupported urban GIS artifact")
        object_key, expected_sha = artifacts[kind]
        payload = self.object_store.read_spatial(object_key)
        if sha256(payload) != expected_sha:
            raise UrbanGisError("urban GIS artifact failed its SHA-256 integrity check")
        return payload

    def _verify_artifacts(self, record: UrbanGisRecord) -> None:
        for kind in ("visual", "hydraulic", "roof-runoff", "qa", "audit"):
            self.read_artifact(record.urban_gis_id, kind)

    def readiness(self, *, city_id: str) -> UrbanGisReadiness:
        all_records = self.repository.list_products(city_id=city_id)
        records: list[UrbanGisRecord] = []
        for record in all_records:
            if (
                record.pipeline_version != URBAN_GIS_PIPELINE_VERSION
                or record.working_crs != self.working_crs
                or not record.domain_ownership_complete
                or not record.roof_rules_complete
            ):
                continue
            try:
                self._verify_artifacts(record)
            except (UrbanGisError, FileNotFoundError):
                continue
            records.append(record)
        counts = {status: 0 for status in UrbanGisReadinessStatus}
        for record in records:
            counts[UrbanGisReadinessStatus(record.readiness_status)] += 1

        ready_count = (
            counts[UrbanGisReadinessStatus.REFERENCE_READY]
            + counts[UrbanGisReadinessStatus.REAL_PILOT_PROVISIONAL]
            + counts[UrbanGisReadinessStatus.REAL_PILOT_REVIEWED]
        )
        technical_passed = ready_count > 0
        final_passed = counts[UrbanGisReadinessStatus.REAL_PILOT_REVIEWED] > 0
        if final_passed:
            reason = (
                "A reviewed real-pilot package satisfies the final Sequence 7 "
                "representation gate."
            )
        elif technical_passed:
            reason = (
                "Automated Sequence 7 contracts are exercised; final real-pilot human "
                "acceptance remains deferred to Sequence 20."
            )
        else:
            reason = "No current-pipeline urban GIS package is ready."
        return UrbanGisReadiness(
            city_id=city_id,
            current_pipeline_version=URBAN_GIS_PIPELINE_VERSION,
            total_packages=len(all_records),
            eligible_packages=len(records),
            reference_ready=counts[UrbanGisReadinessStatus.REFERENCE_READY],
            provisional_real_ready=counts[UrbanGisReadinessStatus.REAL_PILOT_PROVISIONAL],
            reviewed_real_ready=counts[UrbanGisReadinessStatus.REAL_PILOT_REVIEWED],
            technical_development_gate_passed=technical_passed,
            final_human_acceptance_pending=technical_passed and not final_passed,
            final_completion_gate_passed=final_passed,
            completion_reason=reason,
        )
