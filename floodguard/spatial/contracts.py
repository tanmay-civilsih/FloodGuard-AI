"""Public contracts for Sequence 4 spatial normalization and QA."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpatialVariableKind(StrEnum):
    VECTOR = "VECTOR"
    CATEGORICAL = "CATEGORICAL"
    ELEVATION = "ELEVATION"
    RAINFALL = "RAINFALL"


class ResamplingPolicy(StrEnum):
    REPROJECT_NO_RESAMPLE = "REPROJECT_NO_RESAMPLE"
    NEAREST = "NEAREST"
    BILINEAR_WITH_SOURCE_UNCERTAINTY = "BILINEAR_WITH_SOURCE_UNCERTAINTY"
    AREA_CONSERVATIVE = "AREA_CONSERVATIVE"


class DatumTransformStatus(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    COMPATIBLE = "COMPATIBLE"
    TRANSFORMED = "TRANSFORMED"
    UNRESOLVED = "UNRESOLVED"


class VerticalReferenceConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class VerticalReference(BaseModel):
    vertical_datum: str | None = None
    vertical_unit: str | None = None
    vertical_offset_m: float | None = None
    datum_transform_status: DatumTransformStatus = DatumTransformStatus.NOT_APPLICABLE
    vertical_reference_confidence: VerticalReferenceConfidence = (
        VerticalReferenceConfidence.UNKNOWN
    )
    transform_method: str | None = None

    @model_validator(mode="after")
    def validate_transform(self) -> VerticalReference:
        if self.datum_transform_status is DatumTransformStatus.TRANSFORMED:
            if self.vertical_datum is None or self.vertical_unit is None:
                raise ValueError("transformed vertical references require datum and unit")
            if self.vertical_offset_m is None:
                raise ValueError("transformed vertical references require vertical_offset_m")
            if not self.transform_method:
                raise ValueError("transformed vertical references require transform_method")
        if (
            self.datum_transform_status is DatumTransformStatus.COMPATIBLE
            and (self.vertical_datum is None or self.vertical_unit is None)
        ):
            raise ValueError("compatible vertical references require datum and unit")
        return self


class ResolutionMetadata(BaseModel):
    native_resolution_m: float | None = Field(default=None, gt=0)
    computational_resolution_m: float | None = Field(default=None, gt=0)
    effective_information_resolution_m: float | None = Field(default=None, gt=0)
    source_quality: str = "UNKNOWN"

    @model_validator(mode="after")
    def validate_information_resolution(self) -> ResolutionMetadata:
        if (
            self.native_resolution_m is not None
            and self.effective_information_resolution_m is not None
            and self.effective_information_resolution_m < self.native_resolution_m
        ):
            raise ValueError(
                "effective information resolution cannot imply finer source information "
                "than native resolution"
            )
        return self


class SpatialLayerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    normalization_id: UUID
    source_dataset_version_id: UUID
    source_id: UUID
    city_id: str
    source_category: str
    layer_name: str
    variable_kind: SpatialVariableKind
    source_crs: str
    working_crs: str
    source_object_key: str
    normalized_object_key: str
    qa_object_key: str
    normalized_sha256: str
    normalization_fingerprint: str
    feature_count: int
    geometry_types: list[str]
    bounds_working: list[float]
    bounds_wgs84: list[float]
    max_roundtrip_error_m: float
    resampling_policy: ResamplingPolicy
    vertical_datum: str | None
    vertical_unit: str | None
    vertical_offset_m: float | None
    datum_transform_status: DatumTransformStatus
    vertical_reference_confidence: VerticalReferenceConfidence
    native_resolution_m: float | None
    computational_resolution_m: float | None
    effective_information_resolution_m: float | None
    source_quality: str
    created_at: datetime


class RainfallConservationResult(BaseModel):
    volume_before_m3: float
    volume_after_m3: float
    relative_error: float
    tolerance: float
    passed: bool


class SpatialReadiness(BaseModel):
    city_id: str
    working_crs: str
    normalized_layers: int
    eligible_layers: int = 0
    historical_or_unverified_layers: int = 0
    current_pipeline_version: str = ""
    numerical_roundtrip_check_passed: bool = False
    alignment_check_scope: Literal["NUMERICAL_ROUNDTRIP_ONLY"] = "NUMERICAL_ROUNDTRIP_ONLY"
    cross_layer_alignment_status: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"
    elevation_metadata_status: Literal[
        "NOT_APPLICABLE_NO_ELEVATION", "PASSED", "FAILED"
    ] = "NOT_APPLICABLE_NO_ELEVATION"
    rainfall_conservation_scope: Literal["SYNTHETIC_SELF_TEST"] = "SYNTHETIC_SELF_TEST"
    normalized_source_versions: int
    normalized_categories: list[str]
    required_core_categories: list[str]
    missing_core_categories: list[str]
    alignment_check_passed: bool
    max_roundtrip_error_m: float | None
    alignment_tolerance_m: float
    elevation_layer_count: int
    vertical_metadata_valid: bool
    rainfall_conservation: RainfallConservationResult
    spatial_bucket: str
    qa_viewer_path: str = "/spatial/qa"


class SpatialNormalizationResult(BaseModel):
    source_dataset_version_id: UUID
    created_layers: int
    reused_layers: int
    skipped_objects: int
    layer_ids: list[UUID]
