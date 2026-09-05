"""Sequence 6 terrain conditioning orchestration and readiness."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid5

from floodguard.contracts.time import utc_now
from floodguard.harvester.contracts import (
    DatasetVersionRead,
    DatasetVersionStatus,
    RawObjectRead,
)
from floodguard.registry.contracts import SourceCategory, SourceRead
from floodguard.spatial.object_store import SpatialObjectExistsError, SpatialObjectStore
from floodguard.spatial.reference import validate_metric_working_crs
from floodguard.terrain.conditioning import condition_package
from floodguard.terrain.contracts import (
    AssessmentStatus,
    TerrainBuildResult,
    TerrainPackage,
    TerrainProductKind,
    TerrainProductRead,
    TerrainReadiness,
    TerrainReadinessStatus,
    ValidationCheckStatus,
    VerticalQuality,
)
from floodguard.terrain.grid import (
    artifact_bytes,
    decode_package,
    package_bytes,
    qa_geojson,
    sha256,
)
from floodguard.terrain.models import TerrainRecord
from floodguard.terrain.repository import TerrainRepository
from floodguard.terrain.srtm import (
    SRTM_INFORMATION_FLOOR_M,
    decode_hgt,
    native_post_spacing_m,
    sample_hgt_grid,
)
from floodguard.terrain.validation import VerticalEvaluation, evaluate_vertical_controls

TERRAIN_NAMESPACE = UUID("8bb3b744-5f90-4a2b-a2a5-e1a11e8c2c1a")
TERRAIN_PIPELINE_VERSION = "sequence-6-terrain-v5"


class TerrainConditioningError(RuntimeError):
    """Raised when an elevation package cannot satisfy the terrain contract."""


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
            raise TerrainConditioningError(
                f"immutable terrain key exists with different bytes: {object_key}"
            ) from exc


def _fingerprint(
    *,
    source: SourceRead,
    dataset_version: DatasetVersionRead,
    raw_object: RawObjectRead,
    package: TerrainPackage,
    working_crs: str,
) -> str:
    payload = {
        "pipeline_version": TERRAIN_PIPELINE_VERSION,
        "source_id": str(source.source_id),
        "source_category": source.category.value,
        "source_dataset_version_id": str(dataset_version.dataset_version_id),
        "source_object_id": str(raw_object.object_id),
        "source_object_key": raw_object.object_key,
        "source_sha256": raw_object.sha256,
        "package_sha256": sha256(package_bytes(package)),
        "working_crs": working_crs,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _readiness_status(
    package: TerrainPackage, evaluation: VerticalEvaluation | None = None
) -> TerrainReadinessStatus:
    vertical_is_usable = (
        package.source_surface_type.value in {"DSM", "DTM"}
        and package.vertical_quality is not VerticalQuality.UNKNOWN
        and package.vertical_datum is not None
        and package.vertical_unit is not None
        # A TRANSFORMED label alone does not establish transformation provenance.
        and package.datum_transform_status.value == "COMPATIBLE"
    )
    assessments_complete = package.depression_assessment in {
        AssessmentStatus.CATALOGUED,
        AssessmentStatus.CONFIRMED_NONE,
    } and package.multi_level_assessment in {
        AssessmentStatus.CATALOGUED,
        AssessmentStatus.CONFIRMED_NONE,
    }
    if not vertical_is_usable or not assessments_complete:
        return TerrainReadinessStatus.VISUAL_READY

    validation = package.vertical_validation
    checks_failed = any(
        check is ValidationCheckStatus.FAILED
        for check in (
            validation.road_sag_validation,
            validation.underpass_validation,
            validation.drain_rim_elevation_consistency,
        )
    )
    if (
        checks_failed
        or (evaluation and evaluation.status is ValidationCheckStatus.FAILED)
        or (validation.rmse_m is not None and validation.rmse_m > validation.rmse_limit_m)
    ):
        return TerrainReadinessStatus.VISUAL_READY
    # Summary metadata is not independently recomputed validation evidence.
    return TerrainReadinessStatus.HYDRAULIC_SCENARIO_READY


class TerrainService:
    def __init__(
        self,
        repository: TerrainRepository,
        object_store: SpatialObjectStore,
        *,
        working_crs: str,
        max_object_bytes: int,
    ) -> None:
        validate_metric_working_crs(working_crs)
        if max_object_bytes < 1:
            raise ValueError("max_object_bytes must be positive")
        self.repository = repository
        self.object_store = object_store
        self.working_crs = working_crs
        self.max_object_bytes = max_object_bytes

    def _original_elevation(
        self, package: TerrainPackage, version: DatasetVersionRead, package_object: RawObjectRead
    ) -> RawObjectRead:
        derivation = package.derivation
        if derivation is None:
            return package_object
        candidates = [
            item
            for item in version.objects
            if item.filename == derivation.source_filename
            and item.sha256 == derivation.source_sha256
        ]
        if len(candidates) != 1:
            raise TerrainConditioningError(
                "derived package requires one matching original elevation object"
            )
        original = candidates[0]
        if original.dataset_version_id != version.dataset_version_id:
            raise TerrainConditioningError(
                "original elevation does not belong to this dataset version"
            )
        if original.byte_size > self.max_object_bytes:
            raise TerrainConditioningError(
                "original elevation object exceeds configured size limit"
            )
        payload = self.object_store.read_raw(original.object_key)
        if len(payload) != original.byte_size or sha256(payload) != original.sha256:
            raise TerrainConditioningError(
                "original elevation bytes do not match the immutable manifest"
            )
        tile = decode_hgt(payload, original.filename)
        grid = package.grid
        reproduced = sample_hgt_grid(
            tile,
            width=grid.width,
            height=grid.height,
            origin_x_m=grid.origin_x_m,
            origin_y_m=grid.origin_y_m,
            cell_size_m=grid.cell_size_m,
            crs=grid.crs,
        )
        if reproduced != grid:
            raise TerrainConditioningError(
                "derived grid does not reproduce the original elevation bytes"
            )
        if (
            package.source_surface_type.value != "DSM"
            or package.vertical_datum != "EGM96"
            or package.vertical_quality is not VerticalQuality.COARSE_GLOBAL_DEM
            or package.native_horizontal_resolution_m != native_post_spacing_m(tile)
            or package.effective_information_resolution_m < SRTM_INFORMATION_FLOOR_M
        ):
            raise TerrainConditioningError(
                "derived SRTM metadata overstates or changes source information"
            )
        return original

    def build_from_raw(
        self,
        source: SourceRead,
        dataset_version: DatasetVersionRead,
        raw_object: RawObjectRead,
    ) -> TerrainBuildResult:
        if source.category is not SourceCategory.ELEVATION:
            raise TerrainConditioningError("terrain worker requires an ELEVATION registry source")
        if dataset_version.status is not DatasetVersionStatus.COMPLETE:
            raise TerrainConditioningError("only COMPLETE elevation versions can build terrain")
        if dataset_version.source_id != source.source_id:
            raise TerrainConditioningError("dataset version source does not match registry source")
        if dataset_version.city_id != source.city_id:
            raise TerrainConditioningError("dataset version city does not match registry source")
        if raw_object.dataset_version_id != dataset_version.dataset_version_id:
            raise TerrainConditioningError("raw object does not belong to the dataset version")
        if raw_object not in dataset_version.objects:
            raise TerrainConditioningError("raw object does not match the immutable manifest entry")
        if raw_object.byte_size > self.max_object_bytes:
            raise TerrainConditioningError("raw elevation object exceeds configured size limit")

        self.object_store.ensure_ready()
        payload = self.object_store.read_raw(raw_object.object_key)
        if len(payload) != raw_object.byte_size or sha256(payload) != raw_object.sha256:
            raise TerrainConditioningError(
                "raw elevation bytes do not match the immutable manifest"
            )
        try:
            package = decode_package(payload)
        except ValueError as exc:
            raise TerrainConditioningError(str(exc)) from exc
        if package.grid.crs != self.working_crs:
            raise TerrainConditioningError(
                "terrain package must be in the configured metric working CRS; "
                "run the raster reference-system adapter before conditioning"
            )
        original_elevation = self._original_elevation(package, dataset_version, raw_object)

        fingerprint = _fingerprint(
            source=source,
            dataset_version=dataset_version,
            raw_object=raw_object,
            package=package,
            working_crs=self.working_crs,
        )
        existing = self.repository.find_by_fingerprint(fingerprint)
        if existing is not None:
            return TerrainBuildResult(
                terrain_id=existing.terrain_id,
                created=False,
                readiness_status=TerrainReadinessStatus(existing.readiness_status),
                width=existing.width,
                height=existing.height,
                preserved_depression_count=existing.preserved_depression_count,
                filled_artifact_count=existing.filled_artifact_count,
                removed_obstruction_count=existing.removed_obstruction_count,
                multi_level_structure_count=existing.multi_level_structure_count,
            )

        conditioned = condition_package(package)
        evaluation = evaluate_vertical_controls(package, conditioned.hydraulic)
        terrain_id = uuid5(TERRAIN_NAMESPACE, fingerprint)
        prefix = (
            f"terrain/{source.city_id}/{source.source_id}/{dataset_version.dataset_version_id}/"
            f"{terrain_id}"
        )
        visual_key = f"{prefix}/visual_terrain.json"
        hydraulic_key = f"{prefix}/hydraulic_terrain.json"
        structure_key = f"{prefix}/multi_level_structures.json"
        qa_key = f"{prefix}/qa.geojson"
        audit_key = f"{prefix}/audit.json"
        visual_bytes = artifact_bytes(
            product=TerrainProductKind.VISUAL_TERRAIN.value,
            terrain_id=str(terrain_id),
            package=package,
            grid=conditioned.visual,
        )
        hydraulic_bytes = artifact_bytes(
            product=TerrainProductKind.HYDRAULIC_TERRAIN.value,
            terrain_id=str(terrain_id),
            package=package,
            grid=conditioned.hydraulic,
        )
        structure_bytes = json.dumps(
            {
                "artifact_version": "sequence-6-structure-catalog-v1",
                "terrain_id": str(terrain_id),
                "structures": [
                    item.model_dump(mode="json") for item in package.multi_level_structures
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        qa_bytes = json.dumps(
            qa_geojson(
                package=package,
                visual=conditioned.visual,
                hydraulic=conditioned.hydraulic,
                terrain_id=str(terrain_id),
            ),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        readiness_status = _readiness_status(package, evaluation)
        validation = package.vertical_validation
        audit = {
            "artifact_version": "sequence-6-audit-v2",
            "terrain_id": str(terrain_id),
            "terrain_fingerprint": fingerprint,
            "pipeline_version": TERRAIN_PIPELINE_VERSION,
            "source": {
                "source_id": str(source.source_id),
                "dataset_version_id": str(dataset_version.dataset_version_id),
                "source_object_id": str(raw_object.object_id),
                "source_object_key": raw_object.object_key,
                "source_sha256": raw_object.sha256,
            },
            "products": {
                "raw_elevation": original_elevation.object_key,
                "visual_terrain": visual_key,
                "hydraulic_terrain": hydraulic_key,
                "multi_level_structure_catalog": structure_key,
                "qa": qa_key,
            },
            "conditioning": {
                "preserved_depressions": conditioned.preserved_depression_count,
                "filled_artifacts": conditioned.filled_artifact_count,
                "removed_obstructions": conditioned.removed_obstruction_count,
                "max_adjustment_m": conditioned.max_adjustment_m,
                "automatic_sink_filling": False,
                "automatic_dsm_to_dtm_conversion": False,
            },
            "readiness_status": readiness_status.value,
            "derivation": package.derivation.model_dump(mode="json")
            if package.derivation
            else None,
            "original_elevation": {
                "object_id": str(original_elevation.object_id),
                "object_key": original_elevation.object_key,
                "sha256": original_elevation.sha256,
            },
            "vertical_validation": {
                "method": validation.method,
                "rmse_m": evaluation.rmse_m,
                "control_point_count": evaluation.control_point_count,
                "rmse_limit_m": validation.rmse_limit_m,
                "road_sag_validation": validation.road_sag_validation.value,
                "underpass_validation": validation.underpass_validation.value,
                "drain_rim_elevation_consistency": (
                    validation.drain_rim_elevation_consistency.value
                ),
                "limitations": evaluation.limitations,
                "reported_summary": {
                    "rmse_m": validation.rmse_m,
                    "control_point_count": validation.control_point_count,
                },
                "control_observations": [
                    point.model_dump(mode="json") for point in validation.control_points
                ],
                "computed_evaluation": evaluation.model_dump(mode="json"),
            },
            "limitations": package.limitations,
        }
        audit_bytes = json.dumps(audit, sort_keys=True, separators=(",", ":")).encode("utf-8")
        _put_idempotent(
            self.object_store,
            visual_key,
            visual_bytes,
            content_type="application/json",
        )
        _put_idempotent(
            self.object_store,
            hydraulic_key,
            hydraulic_bytes,
            content_type="application/json",
        )
        _put_idempotent(
            self.object_store,
            structure_key,
            structure_bytes,
            content_type="application/json",
        )
        _put_idempotent(
            self.object_store,
            qa_key,
            qa_bytes,
            content_type="application/geo+json",
        )
        _put_idempotent(
            self.object_store,
            audit_key,
            audit_bytes,
            content_type="application/json",
        )
        record = TerrainRecord(
            terrain_id=terrain_id,
            source_dataset_version_id=dataset_version.dataset_version_id,
            source_id=source.source_id,
            source_object_id=raw_object.object_id,
            city_id=source.city_id,
            pilot_area_id=package.pilot_area_id,
            source_object_key=raw_object.object_key,
            source_filename=raw_object.filename,
            source_sha256=raw_object.sha256,
            terrain_fingerprint=fingerprint,
            pipeline_version=TERRAIN_PIPELINE_VERSION,
            working_crs=self.working_crs,
            source_surface_type=package.source_surface_type.value,
            raw_elevation_object_key=original_elevation.object_key,
            visual_terrain_object_key=visual_key,
            hydraulic_terrain_object_key=hydraulic_key,
            multi_level_object_key=structure_key,
            qa_object_key=qa_key,
            audit_object_key=audit_key,
            raw_elevation_sha256=original_elevation.sha256,
            visual_terrain_sha256=sha256(visual_bytes),
            hydraulic_terrain_sha256=sha256(hydraulic_bytes),
            multi_level_sha256=sha256(structure_bytes),
            qa_sha256=sha256(qa_bytes),
            audit_sha256=sha256(audit_bytes),
            width=package.grid.width,
            height=package.grid.height,
            bounds_working=package.grid.bounds,
            native_horizontal_resolution_m=package.native_horizontal_resolution_m,
            computational_resolution_m=package.computational_resolution_m,
            effective_information_resolution_m=package.effective_information_resolution_m,
            vertical_quality=package.vertical_quality.value,
            vertical_datum=package.vertical_datum,
            vertical_unit=package.vertical_unit,
            datum_transform_status=package.datum_transform_status.value,
            vertical_validation_method=validation.method,
            vertical_rmse_m=evaluation.rmse_m,
            control_point_count=evaluation.control_point_count,
            road_sag_validation=validation.road_sag_validation.value,
            underpass_validation=validation.underpass_validation.value,
            drain_rim_elevation_consistency=validation.drain_rim_elevation_consistency.value,
            validation_limitations=evaluation.limitations,
            depression_assessment=package.depression_assessment.value,
            multi_level_assessment=package.multi_level_assessment.value,
            preserved_depression_count=conditioned.preserved_depression_count,
            filled_artifact_count=conditioned.filled_artifact_count,
            removed_obstruction_count=conditioned.removed_obstruction_count,
            multi_level_structure_count=len(package.multi_level_structures),
            max_conditioning_adjustment_m=conditioned.max_adjustment_m,
            readiness_status=readiness_status.value,
            limitations=package.limitations,
            created_at=utc_now(),
        )
        persisted, created = self.repository.add(record)
        return TerrainBuildResult(
            terrain_id=persisted.terrain_id,
            created=created,
            readiness_status=TerrainReadinessStatus(persisted.readiness_status),
            width=persisted.width,
            height=persisted.height,
            preserved_depression_count=persisted.preserved_depression_count,
            filled_artifact_count=persisted.filled_artifact_count,
            removed_obstruction_count=persisted.removed_obstruction_count,
            multi_level_structure_count=persisted.multi_level_structure_count,
        )

    def get(self, terrain_id: UUID) -> TerrainProductRead:
        record = self.repository.get(terrain_id)
        if record is None:
            raise LookupError(str(terrain_id))
        return self.repository.read(record)

    def list_products(self, *, city_id: str | None = None) -> list[TerrainProductRead]:
        return self.repository.reads(self.repository.list_products(city_id=city_id))

    def read_artifact(self, terrain_id: UUID, product: TerrainProductKind | str) -> bytes:
        product = TerrainProductKind(product)
        record = self.repository.get(terrain_id)
        if record is None:
            raise LookupError(str(terrain_id))
        if product is TerrainProductKind.RAW_ELEVATION:
            payload = self.object_store.read_raw(record.raw_elevation_object_key)
            expected_sha = record.raw_elevation_sha256
        else:
            artifacts = {
                TerrainProductKind.VISUAL_TERRAIN: (
                    record.visual_terrain_object_key,
                    record.visual_terrain_sha256,
                ),
                TerrainProductKind.HYDRAULIC_TERRAIN: (
                    record.hydraulic_terrain_object_key,
                    record.hydraulic_terrain_sha256,
                ),
                TerrainProductKind.MULTI_LEVEL_STRUCTURE_CATALOG: (
                    record.multi_level_object_key,
                    record.multi_level_sha256,
                ),
                TerrainProductKind.QA: (record.qa_object_key, record.qa_sha256),
                TerrainProductKind.AUDIT: (record.audit_object_key, record.audit_sha256),
            }
            key, expected_sha = artifacts[product]
            payload = self.object_store.read_spatial(key)
        if sha256(payload) != expected_sha:
            raise TerrainConditioningError("terrain artifact failed its SHA-256 integrity check")
        return payload

    def readiness(self, *, city_id: str) -> TerrainReadiness:
        records = self.repository.list_products(city_id=city_id)
        # Preserve old artifacts but never let obsolete policy or superseded results pass a gate.
        latest_by_pilot: dict[str, TerrainRecord] = {}
        for record in records:
            if record.pipeline_version == TERRAIN_PIPELINE_VERSION:
                latest_by_pilot.setdefault(record.pilot_area_id, record)
        eligible = list(latest_by_pilot.values())
        counts = {
            TerrainReadinessStatus.NOT_READY: 0,
            TerrainReadinessStatus.VISUAL_READY: 0,
            TerrainReadinessStatus.HYDRAULIC_SCENARIO_READY: 0,
            TerrainReadinessStatus.HYDRAULIC_VALIDATED: 0,
        }
        for record in eligible:
            counts[TerrainReadinessStatus(record.readiness_status)] += 1
        rank = {
            TerrainReadinessStatus.NOT_READY: 0,
            TerrainReadinessStatus.VISUAL_READY: 1,
            TerrainReadinessStatus.HYDRAULIC_SCENARIO_READY: 2,
            TerrainReadinessStatus.HYDRAULIC_VALIDATED: 3,
        }
        available_statuses = [status for status, count in counts.items() if count]
        best = (
            max(available_statuses, key=lambda item: rank[item])
            if available_statuses
            else TerrainReadinessStatus.NOT_READY
        )
        completion = (
            counts[TerrainReadinessStatus.HYDRAULIC_SCENARIO_READY] > 0
            or counts[TerrainReadinessStatus.HYDRAULIC_VALIDATED] > 0
        )
        reason = (
            "At least one current-pipeline pilot terrain has explicit visual/hydraulic products, "
            "preserved depression decisions, multi-level metadata, and conservative readiness."
            if completion
            else "No current-pipeline terrain is scenario-ready; rebuild a versioned metric "
            "elevation package and complete depression, multi-level, and vertical assessments."
        )
        return TerrainReadiness(
            city_id=city_id,
            current_pipeline_version=TERRAIN_PIPELINE_VERSION,
            total_terrains=len(records),
            eligible_terrains=len(eligible),
            historical_terrains=len(records) - len(eligible),
            not_ready=counts[TerrainReadinessStatus.NOT_READY],
            visual_ready=counts[TerrainReadinessStatus.VISUAL_READY],
            hydraulic_scenario_ready=counts[TerrainReadinessStatus.HYDRAULIC_SCENARIO_READY],
            hydraulically_validated=counts[TerrainReadinessStatus.HYDRAULIC_VALIDATED],
            best_readiness_status=best,
            completion_gate_passed=completion,
            completion_gate_reason=reason,
        )
