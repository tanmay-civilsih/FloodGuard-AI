"""Typed contracts for Sequence 7 urban GIS, hydraulic surfaces and roof runoff."""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from floodguard.spatial.geometry_validation import validate_geometry
from floodguard.spatial.reference import validate_metric_working_crs

URBAN_GIS_PACKAGE_VERSION = "sequence-7-urban-gis-v1"
SURFACE_POLICY_VERSION = "sequence-7-surface-policy-v1"
ROOF_RUNOFF_POLICY_VERSION = "sequence-7-roof-runoff-v1"
URBAN_GIS_PIPELINE_VERSION = "sequence-7-urban-gis-v1"
DEFAULT_ROOF_VOLUME_RELATIVE_TOLERANCE = 1e-9

EvidenceText = Annotated[str, Field(min_length=1, max_length=2000)]


class UrbanGisInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class HydraulicDomain(StrEnum):
    SURFACE_2D = "SURFACE_2D"
    NETWORK_1D = "NETWORK_1D"
    BOUNDARY = "BOUNDARY"
    VISUAL_ONLY = "VISUAL_ONLY"


class HydraulicSurfaceClass(StrEnum):
    ROAD = "ROAD"
    ROOF = "ROOF"
    BUILDING_BARRIER = "BUILDING_BARRIER"
    OPEN_SOIL = "OPEN_SOIL"
    PARK = "PARK"
    WATER = "WATER"
    RAILWAY = "RAILWAY"
    OTHER_IMPERVIOUS = "OTHER_IMPERVIOUS"


class VisualFeatureClass(StrEnum):
    BUILDING = "BUILDING"
    ROAD = "ROAD"
    WARD = "WARD"
    RIVER = "RIVER"
    CANAL = "CANAL"
    WATER_BODY = "WATER_BODY"
    PARK = "PARK"
    RAILWAY = "RAILWAY"
    OTHER = "OTHER"


class HydrologicLossMode(StrEnum):
    SIMPLIFIED_RUNOFF = "SIMPLIFIED_RUNOFF"
    EXPLICIT_LOSS = "EXPLICIT_LOSS"


class EngineeringValueStatus(StrEnum):
    MUNICIPAL = "MUNICIPAL"
    MEASURED = "MEASURED"
    GIS_DERIVED = "GIS_DERIVED"
    LITERATURE = "LITERATURE"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"
    CALIBRATED = "CALIBRATED"
    MISSING = "MISSING"


class RoofRunoffTargetKind(StrEnum):
    RECEIVING_GEOMETRY = "RECEIVING_GEOMETRY"
    EXPLICIT_DRAIN_TARGET = "EXPLICIT_DRAIN_TARGET"


class UrbanGisEvidenceScope(StrEnum):
    REFERENCE_FIXTURE = "REFERENCE_FIXTURE"
    REAL_PILOT_PROVISIONAL = "REAL_PILOT_PROVISIONAL"
    REAL_PILOT_REVIEWED = "REAL_PILOT_REVIEWED"


class UrbanGisReadinessStatus(StrEnum):
    NOT_READY = "NOT_READY"
    REFERENCE_READY = "REFERENCE_READY"
    REAL_PILOT_PROVISIONAL = "REAL_PILOT_PROVISIONAL"
    REAL_PILOT_REVIEWED = "REAL_PILOT_REVIEWED"


class SurfaceHydrologyPolicy(UrbanGisInput):
    loss_mode: HydrologicLossMode
    parameter_status: EngineeringValueStatus
    source_reference: str = Field(min_length=2, max_length=500)
    runoff_coefficient: float | None = Field(default=None, ge=0.0, le=1.0)
    infiltration_rate_mm_h: float | None = Field(default=None, ge=0.0)
    other_loss_rate_mm_h: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_mode(self) -> SurfaceHydrologyPolicy:
        if self.parameter_status is EngineeringValueStatus.MISSING:
            raise ValueError("an active surface policy cannot use MISSING parameters")
        if self.loss_mode is HydrologicLossMode.SIMPLIFIED_RUNOFF:
            if self.runoff_coefficient is None:
                raise ValueError("simplified runoff requires runoff_coefficient")
            if self.infiltration_rate_mm_h is not None or self.other_loss_rate_mm_h is not None:
                raise ValueError("simplified runoff cannot also configure explicit losses")
        else:
            if self.runoff_coefficient is not None:
                raise ValueError("explicit-loss mode cannot also configure runoff_coefficient")
            if self.infiltration_rate_mm_h is None or self.other_loss_rate_mm_h is None:
                raise ValueError("explicit-loss mode requires infiltration and other loss rates")
        return self


class VisualFeature(UrbanGisInput):
    feature_id: str = Field(min_length=1, max_length=160)
    visual_class: VisualFeatureClass
    geometry: dict[str, Any]
    source_reference: str = Field(min_length=2, max_length=500)
    height_m: float | None = Field(default=None, ge=0.0)


class HydraulicFeature(UrbanGisInput):
    feature_id: str = Field(min_length=1, max_length=160)
    surface_class: HydraulicSurfaceClass
    hydraulic_domain: HydraulicDomain
    geometry: dict[str, Any]
    source_reference: str = Field(min_length=2, max_length=500)
    hydrology: SurfaceHydrologyPolicy | None = None

    @model_validator(mode="after")
    def validate_class_domain(self) -> HydraulicFeature:
        if self.hydraulic_domain is HydraulicDomain.VISUAL_ONLY:
            raise ValueError("hydraulic features cannot be owned by VISUAL_ONLY")
        if self.hydraulic_domain is HydraulicDomain.NETWORK_1D:
            raise ValueError("Sequence 7 surface features cannot claim NETWORK_1D ownership")
        if self.surface_class is HydraulicSurfaceClass.WATER:
            if self.hydraulic_domain not in {HydraulicDomain.SURFACE_2D, HydraulicDomain.BOUNDARY}:
                raise ValueError("WATER must be SURFACE_2D or BOUNDARY")
        elif self.hydraulic_domain is not HydraulicDomain.SURFACE_2D:
            raise ValueError("non-water hydraulic surface classes belong to SURFACE_2D")

        requires_hydrology = self.surface_class in {
            HydraulicSurfaceClass.ROAD,
            HydraulicSurfaceClass.ROOF,
            HydraulicSurfaceClass.OPEN_SOIL,
            HydraulicSurfaceClass.PARK,
            HydraulicSurfaceClass.RAILWAY,
            HydraulicSurfaceClass.OTHER_IMPERVIOUS,
        }
        if requires_hydrology != (self.hydrology is not None):
            requirement = "requires" if requires_hydrology else "must not define"
            raise ValueError(f"{self.surface_class.value} {requirement} a surface hydrology policy")
        return self


class RoofReceivingGeometry(UrbanGisInput):
    receiving_geometry_id: str = Field(min_length=1, max_length=160)
    version: int = Field(ge=1)
    geometry: dict[str, Any]
    source_reference: str = Field(min_length=2, max_length=500)
    hydraulic_domain: HydraulicDomain = HydraulicDomain.SURFACE_2D

    @model_validator(mode="after")
    def validate_owner(self) -> RoofReceivingGeometry:
        if self.hydraulic_domain is not HydraulicDomain.SURFACE_2D:
            raise ValueError("roof receiving geometry must belong to SURFACE_2D")
        return self


class RoofRunoffRule(UrbanGisInput):
    roof_feature_id: str = Field(min_length=1, max_length=160)
    target_kind: RoofRunoffTargetKind
    receiving_geometry: RoofReceivingGeometry | None = None
    explicit_drain_target: str | None = Field(default=None, min_length=2, max_length=500)
    target_source_reference: str = Field(min_length=2, max_length=500)
    relative_volume_tolerance: float = Field(
        default=DEFAULT_ROOF_VOLUME_RELATIVE_TOLERANCE, ge=0.0, le=1e-3
    )

    @model_validator(mode="after")
    def validate_target(self) -> RoofRunoffRule:
        if self.target_kind is RoofRunoffTargetKind.RECEIVING_GEOMETRY:
            if self.receiving_geometry is None or self.explicit_drain_target is not None:
                raise ValueError("receiving-geometry target requires only receiving_geometry")
        elif self.explicit_drain_target is None or self.receiving_geometry is not None:
            raise ValueError("explicit drain target requires only explicit_drain_target")
        return self


class UrbanGisPackage(UrbanGisInput):
    package_version: Literal["sequence-7-urban-gis-v1"] = URBAN_GIS_PACKAGE_VERSION
    city_id: str = Field(min_length=1, max_length=100)
    pilot_area_id: str = Field(min_length=1, max_length=160)
    working_crs: str = Field(min_length=1, max_length=100)
    evidence_scope: UrbanGisEvidenceScope
    source_references: list[EvidenceText] = Field(min_length=1)
    surface_policy_version: Literal["sequence-7-surface-policy-v1"] = SURFACE_POLICY_VERSION
    roof_runoff_policy_version: Literal["sequence-7-roof-runoff-v1"] = ROOF_RUNOFF_POLICY_VERSION
    visual_features: list[VisualFeature] = Field(min_length=1)
    hydraulic_features: list[HydraulicFeature] = Field(min_length=1)
    roof_runoff_rules: list[RoofRunoffRule] = Field(default_factory=list)
    limitations: list[EvidenceText] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_package(self) -> UrbanGisPackage:
        validate_metric_working_crs(self.working_crs)
        visual_ids = [item.feature_id for item in self.visual_features]
        hydraulic_ids = [item.feature_id for item in self.hydraulic_features]
        rule_ids = [item.roof_feature_id for item in self.roof_runoff_rules]
        if len(set(visual_ids)) != len(visual_ids):
            raise ValueError("visual feature IDs must be unique")
        if len(set(hydraulic_ids)) != len(hydraulic_ids):
            raise ValueError("hydraulic feature IDs must be unique")
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("each roof may have only one runoff rule")

        for feature in [*self.visual_features, *self.hydraulic_features]:
            validate_geometry(feature.geometry, geographic=False)
            if feature.geometry.get("type") not in {"Polygon", "MultiPolygon"}:
                raise ValueError("Sequence 7 city surface features must be polygonal")
        for rule in self.roof_runoff_rules:
            if rule.receiving_geometry is not None:
                validate_geometry(rule.receiving_geometry.geometry, geographic=False)
                if rule.receiving_geometry.geometry.get("type") not in {"Polygon", "MultiPolygon"}:
                    raise ValueError("roof receiving geometry must be polygonal")

        roofs = {
            feature.feature_id
            for feature in self.hydraulic_features
            if feature.surface_class is HydraulicSurfaceClass.ROOF
        }
        if roofs != set(rule_ids):
            missing = roofs - set(rule_ids)
            extra = set(rule_ids) - roofs
            raise ValueError(
                f"roof runoff rules must match ROOF features exactly; missing={sorted(missing)}, "
                f"extra={sorted(extra)}"
            )
        return self


class UrbanGisBuildResult(UrbanGisInput):
    urban_gis_id: UUID
    created: bool
    readiness_status: UrbanGisReadinessStatus
    visual_feature_count: int
    hydraulic_feature_count: int
    roof_feature_count: int


class UrbanGisProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    urban_gis_id: UUID
    city_id: str
    pilot_area_id: str
    urban_gis_fingerprint: str
    pipeline_version: str
    working_crs: str
    evidence_scope: UrbanGisEvidenceScope
    visual_object_key: str
    hydraulic_object_key: str
    roof_runoff_object_key: str
    qa_object_key: str
    audit_object_key: str
    visual_sha256: str
    hydraulic_sha256: str
    roof_runoff_sha256: str
    qa_sha256: str
    audit_sha256: str
    visual_feature_count: int
    hydraulic_feature_count: int
    roof_feature_count: int
    domain_ownership_complete: bool
    roof_rules_complete: bool
    readiness_status: UrbanGisReadinessStatus
    limitations: list[str]


class UrbanGisReadiness(UrbanGisInput):
    city_id: str
    current_pipeline_version: str
    total_packages: int
    eligible_packages: int
    reference_ready: int
    provisional_real_ready: int
    reviewed_real_ready: int
    technical_development_gate_passed: bool
    final_human_acceptance_pending: bool
    final_completion_gate_passed: bool
    completion_reason: str
    qa_viewer_path: str = "/urban-gis/qa"
