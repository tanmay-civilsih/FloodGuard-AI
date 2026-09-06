"""Sequence 4 spatial normalization orchestration and readiness."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from uuid import UUID, uuid5

from floodguard.common.integrity import (
    PayloadIntegrityError,
    verified_payload,
    verified_spatial_pair,
)
from floodguard.contracts.time import utc_now
from floodguard.harvester.contracts import DatasetVersionRead, DatasetVersionStatus, RawObjectRead
from floodguard.registry.contracts import SourceCategory, SourceRead
from floodguard.spatial.contracts import (
    DatumTransformStatus,
    ResamplingPolicy,
    SpatialLayerRead,
    SpatialNormalizationResult,
    SpatialReadiness,
    SpatialVariableKind,
    VerticalReferenceConfidence,
)
from floodguard.spatial.models import SpatialLayerRecord
from floodguard.spatial.object_store import (
    SpatialObjectExistsError,
    SpatialObjectStore,
)
from floodguard.spatial.reference import validate_metric_working_crs
from floodguard.spatial.repository import SpatialRepository
from floodguard.spatial.resampling import reference_rainfall_conservation_check
from floodguard.spatial.vector import VectorNormalizationError, normalize_vector

SPATIAL_NAMESPACE = UUID("2ea3b742-7747-4ca8-b627-e89b3dc2c454")
SPATIAL_PIPELINE_VERSION = "sequence-4-v3"
_VECTOR_SUFFIXES = {".kml", ".geojson", ".json"}
_LAYER_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")
CORE_KOLKATA_CATEGORIES = {
    SourceCategory.WARD_BOUNDARY,
    SourceCategory.CATCHMENT,
    SourceCategory.WATER_BODY,
}


class SpatialNormalizationError(RuntimeError):
    pass


def _put_idempotent(
    object_store: SpatialObjectStore,
    object_key: str,
    payload: bytes,
    *,
    content_type: str,
) -> None:
    try:
        object_store.put_spatial_once(
            object_key,
            payload,
            content_type=content_type,
        )
    except SpatialObjectExistsError as exc:
        if object_store.read_spatial(object_key) != payload:
            raise SpatialNormalizationError(
                f"immutable spatial key exists with different bytes: {object_key}"
            ) from exc


def _layer_name(filename: str) -> str:
    stem = Path(filename).stem.strip() or "layer"
    cleaned = _LAYER_SEGMENT.sub("_", stem).strip("._")
    return cleaned[:200] or "layer"


def _variable_kind(source: SourceRead) -> SpatialVariableKind:
    if source.category is SourceCategory.ELEVATION:
        return SpatialVariableKind.ELEVATION
    if source.category in {
        SourceCategory.RAINFALL_OBSERVATION,
        SourceCategory.HISTORICAL_RAINFALL,
        SourceCategory.RAINFALL_NOWCAST,
        SourceCategory.RADAR,
    }:
        return SpatialVariableKind.RAINFALL
    return SpatialVariableKind.VECTOR


def _fingerprint(
    *,
    source: SourceRead,
    dataset_version: DatasetVersionRead,
    raw_object: RawObjectRead,
    working_crs: str,
) -> str:
    payload = {
        "pipeline_version": SPATIAL_PIPELINE_VERSION,
        "source_id": str(source.source_id),
        "source_category": source.category.value,
        "source_dataset_version_id": str(dataset_version.dataset_version_id),
        "source_object_key": raw_object.object_key,
        "source_sha256": raw_object.sha256,
        "working_crs": working_crs,
        "vertical_datum": source.vertical_datum,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SpatialService:
    def __init__(
        self,
        repository: SpatialRepository,
        object_store: SpatialObjectStore,
        *,
        working_crs: str,
        alignment_tolerance_m: float,
        rainfall_conservation_tolerance: float,
        max_object_bytes: int,
    ) -> None:
        validate_metric_working_crs(working_crs)
        if not math.isfinite(alignment_tolerance_m) or alignment_tolerance_m < 0:
            raise ValueError("alignment_tolerance_m must be non-negative")
        if (
            not math.isfinite(rainfall_conservation_tolerance)
            or rainfall_conservation_tolerance < 0
        ):
            raise ValueError("rainfall_conservation_tolerance must be non-negative")
        if max_object_bytes < 1:
            raise ValueError("max_object_bytes must be positive")
        self.repository = repository
        self.object_store = object_store
        self.working_crs = working_crs
        self.alignment_tolerance_m = alignment_tolerance_m
        self.rainfall_conservation_tolerance = rainfall_conservation_tolerance
        self.max_object_bytes = max_object_bytes

    def normalize_dataset(
        self,
        source: SourceRead,
        dataset_version: DatasetVersionRead,
    ) -> SpatialNormalizationResult:
        if dataset_version.status is not DatasetVersionStatus.COMPLETE:
            raise SpatialNormalizationError("only COMPLETE raw dataset versions can be normalized")
        if dataset_version.source_id != source.source_id:
            raise SpatialNormalizationError(
                "dataset version source_id does not match registry source"
            )
        if dataset_version.city_id != source.city_id:
            raise SpatialNormalizationError(
                "dataset version city_id does not match registry source"
            )

        variable_kind = _variable_kind(source)
        if variable_kind is not SpatialVariableKind.VECTOR:
            raise SpatialNormalizationError(
                "this bootstrap normalizer handles vector source objects only; "
                "raster resampling is provided by the variable-specific resampling module"
            )

        self.object_store.ensure_ready()
        created_layers = 0
        reused_layers = 0
        skipped_objects = 0
        layer_ids: list[UUID] = []
        for raw_object in dataset_version.objects:
            suffix = Path(raw_object.filename).suffix.lower()
            if suffix not in _VECTOR_SUFFIXES:
                skipped_objects += 1
                continue
            if raw_object.byte_size > self.max_object_bytes:
                raise SpatialNormalizationError(
                    f"raw object exceeds spatial normalization limit: {raw_object.filename}"
                )
            if raw_object.dataset_version_id != dataset_version.dataset_version_id:
                raise SpatialNormalizationError("raw object belongs to another dataset version")
            payload = self.object_store.read_raw(raw_object.object_key)
            try:
                verified_payload(
                    payload, expected_sha256=raw_object.sha256,
                    expected_size=raw_object.byte_size, max_bytes=self.max_object_bytes,
                )
            except PayloadIntegrityError as exc:
                raise SpatialNormalizationError(str(exc)) from exc
            fingerprint = _fingerprint(
                source=source,
                dataset_version=dataset_version,
                raw_object=raw_object,
                working_crs=self.working_crs,
            )
            existing = self.repository.find_by_fingerprint(fingerprint)
            if existing is not None:
                self.qa_geojson(existing.normalization_id)
                reused_layers += 1
                layer_ids.append(existing.normalization_id)
                continue

            repair_self_intersections = source.category is SourceCategory.WARD_BOUNDARY
            try:
                normalized = normalize_vector(
                    payload,
                    raw_object.filename,
                    working_crs=self.working_crs,
                    repair_self_intersections=repair_self_intersections,
                )
            except VectorNormalizationError as exc:
                raise SpatialNormalizationError(
                    f"failed to normalize {raw_object.filename}: {exc}"
                ) from exc

            normalization_id = uuid5(SPATIAL_NAMESPACE, fingerprint)
            prefix = (
                f"normalized/{source.city_id}/{source.source_id}/"
                f"{dataset_version.dataset_version_id}/{normalization_id}"
            )
            internal_key = f"{prefix}/working.json"
            qa_key = f"{prefix}/qa.geojson"
            qa_bytes = json.dumps(
                normalized.qa_feature_collection,
                sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
            normalized.internal_feature_collection["floodguard_integrity"] = {
                "pipeline_version": SPATIAL_PIPELINE_VERSION,
                "source_sha256": raw_object.sha256,
                "source_byte_size": raw_object.byte_size,
                "qa_sha256": hashlib.sha256(qa_bytes).hexdigest(),
                "qa_byte_size": len(qa_bytes),
                "topology_repair_policy": (
                    "LINEWORK_SELF_INTERSECTION_ONLY_V1"
                    if repair_self_intersections else "DISABLED"
                ),
            }
            internal_bytes = json.dumps(
                normalized.internal_feature_collection,
                sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
            if max(len(internal_bytes), len(qa_bytes)) > self.max_object_bytes:
                raise SpatialNormalizationError("normalized artifacts exceed configured size limit")
            normalized_sha256 = hashlib.sha256(internal_bytes).hexdigest()
            _put_idempotent(
                self.object_store,
                internal_key,
                internal_bytes,
                content_type="application/json",
            )
            _put_idempotent(
                self.object_store,
                qa_key,
                qa_bytes,
                content_type="application/geo+json",
            )
            record = SpatialLayerRecord(
                normalization_id=normalization_id,
                source_dataset_version_id=dataset_version.dataset_version_id,
                source_id=source.source_id,
                city_id=source.city_id,
                source_category=source.category.value,
                layer_name=_layer_name(raw_object.filename),
                variable_kind=variable_kind.value,
                source_crs=normalized.source_crs,
                working_crs=self.working_crs,
                source_object_key=raw_object.object_key,
                normalized_object_key=internal_key,
                qa_object_key=qa_key,
                normalized_sha256=normalized_sha256,
                normalization_fingerprint=fingerprint,
                feature_count=normalized.feature_count,
                geometry_types=normalized.geometry_types,
                bounds_working=normalized.bounds_working,
                bounds_wgs84=normalized.bounds_wgs84,
                max_roundtrip_error_m=normalized.max_roundtrip_error_m,
                resampling_policy=ResamplingPolicy.REPROJECT_NO_RESAMPLE.value,
                vertical_datum=None,
                vertical_unit=None,
                vertical_offset_m=None,
                datum_transform_status=DatumTransformStatus.NOT_APPLICABLE.value,
                vertical_reference_confidence=VerticalReferenceConfidence.UNKNOWN.value,
                native_resolution_m=None,
                computational_resolution_m=None,
                effective_information_resolution_m=None,
                source_quality=source.authority_level.value,
                created_at=utc_now(),
            )
            persisted, created = self.repository.add(record)
            if created:
                created_layers += 1
            else:
                reused_layers += 1
            layer_ids.append(persisted.normalization_id)

        return SpatialNormalizationResult(
            source_dataset_version_id=dataset_version.dataset_version_id,
            created_layers=created_layers,
            reused_layers=reused_layers,
            skipped_objects=skipped_objects,
            layer_ids=layer_ids,
        )

    def get_layer(self, normalization_id: UUID) -> SpatialLayerRead:
        record = self.repository.get(normalization_id)
        if record is None:
            raise LookupError(str(normalization_id))
        return SpatialLayerRead.model_validate(record)

    def list_layers(
        self,
        *,
        city_id: str | None = None,
        source_id: UUID | None = None,
    ) -> list[SpatialLayerRead]:
        return self.repository.reads(
            self.repository.list_layers(city_id=city_id, source_id=source_id)
        )

    def qa_geojson(self, normalization_id: UUID) -> bytes:
        layer = self.get_layer(normalization_id)
        working = self.object_store.read_spatial(layer.normalized_object_key)
        qa = self.object_store.read_spatial(layer.qa_object_key)
        try:
            verified_spatial_pair(
                working, qa, working_sha256=layer.normalized_sha256,
                pipeline_version=SPATIAL_PIPELINE_VERSION, max_bytes=self.max_object_bytes,
            )
        except PayloadIntegrityError as exc:
            raise SpatialNormalizationError(str(exc)) from exc
        return qa

    def readiness(self, *, city_id: str) -> SpatialReadiness:
        all_records = self.repository.list_layers(city_id=city_id)
        records = []
        for record in all_records:
            if record.working_crs != self.working_crs:
                continue
            try:
                self.qa_geojson(record.normalization_id)
            except (SpatialNormalizationError, FileNotFoundError):
                continue
            records.append(record)
        categories = sorted({record.source_category for record in records})
        required = sorted(category.value for category in CORE_KOLKATA_CATEGORIES)
        missing = sorted(set(required) - set(categories))
        max_error = max(
            (record.max_roundtrip_error_m for record in records),
            default=None,
        )
        alignment_passed = (
            bool(records)
            and not missing
            and max_error is not None
            and math.isfinite(max_error)
            and all(math.isfinite(record.max_roundtrip_error_m) for record in records)
            and max_error <= self.alignment_tolerance_m
        )
        elevation_records = [
            record
            for record in records
            if record.variable_kind == SpatialVariableKind.ELEVATION.value
        ]
        vertical_valid = all(
            record.vertical_datum is not None
            and record.vertical_unit is not None
            and record.datum_transform_status
            in {DatumTransformStatus.COMPATIBLE.value, DatumTransformStatus.TRANSFORMED.value}
            for record in elevation_records
        )
        rainfall = reference_rainfall_conservation_check(
            tolerance=self.rainfall_conservation_tolerance
        )
        return SpatialReadiness(
            city_id=city_id,
            working_crs=self.working_crs,
            normalized_layers=len(all_records),
            eligible_layers=len(records),
            historical_or_unverified_layers=len(all_records) - len(records),
            current_pipeline_version=SPATIAL_PIPELINE_VERSION,
            normalized_source_versions=self.repository.count_source_versions(city_id=city_id),
            normalized_categories=categories,
            required_core_categories=required,
            missing_core_categories=missing,
            alignment_check_passed=alignment_passed,
            numerical_roundtrip_check_passed=alignment_passed,
            cross_layer_alignment_status="NOT_ASSESSED",
            max_roundtrip_error_m=max_error,
            alignment_tolerance_m=self.alignment_tolerance_m,
            elevation_layer_count=len(elevation_records),
            vertical_metadata_valid=vertical_valid,
            elevation_metadata_status=(
                "NOT_APPLICABLE_NO_ELEVATION" if not elevation_records
                else "PASSED" if vertical_valid else "FAILED"
            ),
            rainfall_conservation=rainfall,
            spatial_bucket=self.object_store.spatial_bucket,
        )
