"""Typed contracts for Sequence 6 terrain preparation.

The terrain worker deliberately keeps source elevation, visual terrain, and
hydraulic terrain as separate products.  A grid is a small, deterministic
interchange format for the prototype; production raster adapters can create the
same contract from a GeoTIFF/COG without changing the conditioning rules.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from floodguard.spatial.contracts import DatumTransformStatus


class SurfaceType(StrEnum):
    DSM = "DSM"
    DTM = "DTM"
    UNKNOWN = "UNKNOWN"


class VerticalQuality(StrEnum):
    UNKNOWN = "UNKNOWN"
    COARSE_GLOBAL_DEM = "COARSE_GLOBAL_DEM"
    SURVEY_CONTROLLED = "SURVEY_CONTROLLED"


class TerrainProductKind(StrEnum):
    RAW_ELEVATION = "RAW_ELEVATION"
    VISUAL_TERRAIN = "VISUAL_TERRAIN"
    HYDRAULIC_TERRAIN = "HYDRAULIC_TERRAIN"
    MULTI_LEVEL_STRUCTURE_CATALOG = "MULTI_LEVEL_STRUCTURE_CATALOG"
    QA = "QA"
    AUDIT = "AUDIT"


class TerrainReadinessStatus(StrEnum):
    NOT_READY = "NOT_READY"
    VISUAL_READY = "VISUAL_READY"
    HYDRAULIC_SCENARIO_READY = "HYDRAULIC_SCENARIO_READY"
    HYDRAULIC_VALIDATED = "HYDRAULIC_VALIDATED"


class TerrainInterventionKind(StrEnum):
    PRESERVE_DEPRESSION = "PRESERVE_DEPRESSION"
    FILL_DOCUMENTED_ARTIFACT = "FILL_DOCUMENTED_ARTIFACT"
    REMOVE_DOCUMENTED_OBSTRUCTION = "REMOVE_DOCUMENTED_OBSTRUCTION"


class MultiLevelStructureKind(StrEnum):
    FLYOVER = "FLYOVER"
    BRIDGE = "BRIDGE"
    UNDERPASS = "UNDERPASS"
    CULVERT = "CULVERT"
    ELEVATED_ROAD = "ELEVATED_ROAD"
    TUNNEL = "TUNNEL"


class ValidationCheckStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_ASSESSED = "NOT_ASSESSED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AssessmentStatus(StrEnum):
    NOT_ASSESSED = "NOT_ASSESSED"
    CATALOGUED = "CATALOGUED"
    CONFIRMED_NONE = "CONFIRMED_NONE"


class TerrainInput(BaseModel):
    """Fail closed on misspelled fields, non-finite numbers and blank evidence."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


EvidenceText = Annotated[str, Field(min_length=1)]


class TerrainGrid(TerrainInput):
    """A rectilinear metric grid with explicit source and computational shape."""

    width: int = Field(ge=1)
    height: int = Field(ge=1)
    origin_x_m: float
    origin_y_m: float
    cell_size_m: float = Field(gt=0)
    crs: str = Field(min_length=1, max_length=100)
    elevations_m: list[list[float | None]]

    @model_validator(mode="after")
    def validate_shape_and_values(self) -> TerrainGrid:
        if len(self.elevations_m) != self.height:
            raise ValueError("elevations_m row count must equal height")
        for row in self.elevations_m:
            if len(row) != self.width:
                raise ValueError("elevations_m column count must equal width")
            for value in row:
                if value is not None and not math.isfinite(value):
                    raise ValueError("elevations_m values must be finite or null")
        if not any(value is not None for row in self.elevations_m for value in row):
            raise ValueError("terrain grid must contain at least one elevation")
        if not all(math.isfinite(value) for value in self.bounds):
            raise ValueError("terrain grid bounds must be finite")
        if self.bounds[2] <= self.origin_x_m or self.bounds[3] <= self.origin_y_m:
            raise ValueError("terrain grid bounds must have positive area")
        return self

    @property
    def bounds(self) -> list[float]:
        return [
            self.origin_x_m,
            self.origin_y_m,
            self.origin_x_m + self.width * self.cell_size_m,
            self.origin_y_m + self.height * self.cell_size_m,
        ]


class TerrainIntervention(TerrainInput):
    """One explicit, provenance-backed change to the hydraulic surface."""

    row: int = Field(ge=0)
    column: int = Field(ge=0)
    kind: TerrainInterventionKind
    target_elevation_m: float | None = None
    source_reference: str = Field(min_length=2, max_length=500)
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def validate_target(self) -> TerrainIntervention:
        if self.kind is TerrainInterventionKind.PRESERVE_DEPRESSION:
            if self.target_elevation_m is not None:
                raise ValueError("preserved depressions must not provide a target elevation")
        elif self.target_elevation_m is None:
            raise ValueError("conditioning interventions require target_elevation_m")
        elif not math.isfinite(self.target_elevation_m):
            raise ValueError("target_elevation_m must be finite")
        return self


class MultiLevelStructure(TerrainInput):
    """A separately catalogued upper/lower level affecting hydraulic connectivity."""

    structure_id: str = Field(min_length=1, max_length=160)
    kind: MultiLevelStructureKind
    bounds_working: list[float] = Field(min_length=4, max_length=4)
    lower_elevation_m: float
    upper_elevation_m: float
    upper_level_role: str = Field(min_length=1, max_length=120)
    lower_level_role: str = Field(min_length=1, max_length=120)
    source_reference: str = Field(min_length=2, max_length=500)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_levels_and_bounds(self) -> MultiLevelStructure:
        minimum_x, minimum_y, maximum_x, maximum_y = self.bounds_working
        if minimum_x >= maximum_x or minimum_y >= maximum_y:
            raise ValueError("multi-level structure bounds must have positive area")
        if self.lower_elevation_m >= self.upper_elevation_m:
            raise ValueError("lower level must be below upper level")
        return self


class TerrainControlPoint(TerrainInput):
    """An independently supplied elevation observation at a declared grid-cell centre."""

    control_id: str = Field(min_length=1, max_length=160)
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    reference_elevation_m: float
    vertical_datum: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=2, max_length=500)
    measured_at: AwareDatetime

    @field_validator("measured_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class VerticalValidation(TerrainInput):
    """Evidence used to distinguish scenario-ready from hydraulically validated terrain."""

    method: str | None = Field(default=None, min_length=1, max_length=300)
    rmse_m: float | None = Field(default=None, ge=0)
    control_point_count: int = Field(default=0, ge=0)
    control_points: list[TerrainControlPoint] = Field(default_factory=list)
    rmse_limit_m: float = Field(default=5.0, gt=0)
    road_sag_validation: ValidationCheckStatus = ValidationCheckStatus.NOT_ASSESSED
    underpass_validation: ValidationCheckStatus = ValidationCheckStatus.NOT_ASSESSED
    drain_rim_elevation_consistency: ValidationCheckStatus = (
        ValidationCheckStatus.NOT_ASSESSED
    )
    limitations: list[EvidenceText] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_metrics(self) -> VerticalValidation:
        if self.rmse_m is not None and not math.isfinite(self.rmse_m):
            raise ValueError("vertical_rmse_m must be finite")
        if self.control_points:
            if not self.method:
                raise ValueError("control observations require a survey method")
            if self.control_point_count not in {0, len(self.control_points)}:
                raise ValueError("reported control count must match supplied observations")
            ids = [point.control_id for point in self.control_points]
            cells = [(point.row, point.column) for point in self.control_points]
            if len(set(ids)) != len(ids) or len(set(cells)) != len(cells):
                raise ValueError("control observations require unique IDs and cells")
        if self.rmse_m is not None and not (self.control_point_count or self.control_points):
            raise ValueError("vertical RMSE requires at least one control point")
        if self.method is not None and not (self.control_point_count or self.control_points):
            raise ValueError("vertical validation method requires control points")
        return self


class TerrainDerivation(TerrainInput):
    """Trace a converted grid to an original elevation object in the same raw manifest."""

    adapter_version: Literal["srtmgl1-nearest-v1"]
    source_filename: str = Field(min_length=1, max_length=100)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_format: Literal["SRTMGL1_HGT"] = "SRTMGL1_HGT"
    source_crs: Literal["EPSG:4326"] = "EPSG:4326"
    sampling_method: Literal["NEAREST_POST"] = "NEAREST_POST"
    boundary_reference: str = Field(min_length=2, max_length=500)
    vertical_metadata_reference: str = Field(min_length=2, max_length=500)


class TerrainPackage(TerrainInput):
    """Immutable input package consumed by the terrain worker."""

    pilot_area_id: str = Field(min_length=1, max_length=160)
    derivation: TerrainDerivation | None = None
    grid: TerrainGrid
    source_surface_type: SurfaceType
    vertical_datum: str | None = Field(default=None, min_length=1)
    vertical_unit: str | None = Field(default=None, min_length=1)
    datum_transform_status: DatumTransformStatus = DatumTransformStatus.UNRESOLVED
    vertical_quality: VerticalQuality = VerticalQuality.UNKNOWN
    native_horizontal_resolution_m: float = Field(gt=0)
    computational_resolution_m: float = Field(gt=0)
    effective_information_resolution_m: float = Field(gt=0)
    depression_assessment: AssessmentStatus = AssessmentStatus.NOT_ASSESSED
    multi_level_assessment: AssessmentStatus = AssessmentStatus.NOT_ASSESSED
    interventions: list[TerrainIntervention] = Field(default_factory=list)
    multi_level_structures: list[MultiLevelStructure] = Field(default_factory=list)
    vertical_validation: VerticalValidation
    max_conditioning_adjustment_m: float = Field(default=10.0, gt=0)
    limitations: list[EvidenceText] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_resolution_and_reference(self) -> TerrainPackage:
        if self.effective_information_resolution_m < max(
            self.native_horizontal_resolution_m, self.computational_resolution_m
        ):
            raise ValueError(
                "effective_information_resolution_m cannot imply finer source or grid information"
            )
        if self.grid.cell_size_m != self.computational_resolution_m:
            raise ValueError("grid cell_size_m must equal computational_resolution_m")
        if self.vertical_quality is not VerticalQuality.UNKNOWN and (
            not self.vertical_datum or not self.vertical_unit
        ):
            raise ValueError("known vertical quality requires datum and unit")
        if self.vertical_unit is not None and self.vertical_unit.lower() not in {
            "m", "metre", "meter", "metres", "meters",
        }:
            raise ValueError("terrain elevation units must be metres")
        if self.multi_level_assessment is AssessmentStatus.CATALOGUED and not (
            self.multi_level_structures
        ):
            raise ValueError("catalogued multi-level assessment requires a structure catalog")
        if self.multi_level_structures and self.multi_level_assessment is not (
            AssessmentStatus.CATALOGUED
        ):
            raise ValueError("structure catalog requires CATALOGUED assessment")
        structure_ids = [item.structure_id for item in self.multi_level_structures]
        if len(structure_ids) != len(set(structure_ids)):
            raise ValueError("structure IDs must be unique")
        xmin, ymin, xmax, ymax = self.grid.bounds
        for structure in self.multi_level_structures:
            sxmin, symin, sxmax, symax = structure.bounds_working
            if sxmax <= xmin or symax <= ymin or sxmin >= xmax or symin >= ymax:
                raise ValueError("structure bounds must intersect the terrain grid")
        preserved = any(
            item.kind is TerrainInterventionKind.PRESERVE_DEPRESSION
            for item in self.interventions
        )
        if (self.depression_assessment is AssessmentStatus.CATALOGUED) != preserved:
            raise ValueError("catalogued depression assessment requires preserved depression cells")
        return self


class TerrainProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    terrain_id: UUID
    source_dataset_version_id: UUID
    source_id: UUID
    source_object_id: UUID
    city_id: str
    pilot_area_id: str
    source_object_key: str
    source_filename: str
    source_sha256: str
    terrain_fingerprint: str
    pipeline_version: str
    working_crs: str
    source_surface_type: SurfaceType
    raw_elevation_object_key: str
    visual_terrain_object_key: str
    hydraulic_terrain_object_key: str
    multi_level_object_key: str
    qa_object_key: str
    audit_object_key: str
    raw_elevation_sha256: str
    visual_terrain_sha256: str
    hydraulic_terrain_sha256: str
    multi_level_sha256: str
    qa_sha256: str
    audit_sha256: str
    width: int
    height: int
    bounds_working: list[float]
    native_horizontal_resolution_m: float
    computational_resolution_m: float
    effective_information_resolution_m: float
    vertical_quality: VerticalQuality
    vertical_datum: str | None
    vertical_unit: str | None
    datum_transform_status: DatumTransformStatus
    vertical_validation_method: str | None
    vertical_rmse_m: float | None
    control_point_count: int
    road_sag_validation: ValidationCheckStatus
    underpass_validation: ValidationCheckStatus
    drain_rim_elevation_consistency: ValidationCheckStatus
    validation_limitations: list[str]
    depression_assessment: AssessmentStatus
    multi_level_assessment: AssessmentStatus
    preserved_depression_count: int
    filled_artifact_count: int
    removed_obstruction_count: int
    multi_level_structure_count: int
    max_conditioning_adjustment_m: float
    readiness_status: TerrainReadinessStatus
    limitations: list[str]
    created_at: datetime


class TerrainBuildResult(BaseModel):
    terrain_id: UUID
    created: bool
    readiness_status: TerrainReadinessStatus
    width: int
    height: int
    preserved_depression_count: int
    filled_artifact_count: int
    removed_obstruction_count: int
    multi_level_structure_count: int


class TerrainReadiness(BaseModel):
    city_id: str
    current_pipeline_version: str = ""
    total_terrains: int
    eligible_terrains: int = 0
    historical_terrains: int = 0
    not_ready: int
    visual_ready: int
    hydraulic_scenario_ready: int
    hydraulically_validated: int
    best_readiness_status: TerrainReadinessStatus
    completion_gate_passed: bool
    completion_gate_reason: str
    qa_viewer_path: str = "/terrain/qa"
