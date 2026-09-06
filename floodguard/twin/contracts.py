"""Typed twin assembly requests and immutable, explicit component versions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from floodguard.contracts.time import UtcDateTime
from floodguard.drainage.contracts import DrainEvidenceScope, DrainInput
from floodguard.drainage.model_contracts import HydraulicReadiness
from floodguard.spatial.geometry_validation import validate_geometry
from floodguard.spatial.reference import validate_metric_working_crs

TWIN_POLICY: Literal["sequence-9-twin-v1"] = "sequence-9-twin-v1"


class ComponentRole(StrEnum):
    VISUAL_TERRAIN = "visual_terrain_version"
    HYDRAULIC_TERRAIN = "hydraulic_terrain_version"
    VISUAL_CITY = "visual_city_version"
    HYDRAULIC_SURFACE = "hydraulic_surface_version"
    ROOF_RUNOFF = "roof_runoff_geometry_version"
    DRAIN_GRAPH = "drain_graph_version"
    EXCHANGE = "exchange_geometry_version"
    PARAMETERS = "hydraulic_parameter_set_version"
    WARD = "ward_version"
    CATCHMENT = "catchment_version"
    WATERBODY = "waterbody_version"
    PUMP = "pump_asset_version"


class PilotArea(DrainInput):
    pilot_area_id: str = Field(min_length=1, max_length=160)
    geometry: dict[str, Any]
    ward_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_geometry(self) -> PilotArea:
        validate_geometry(self.geometry, geographic=False)
        if self.geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("pilot area must be polygonal")
        if len(set(self.ward_ids)) != len(self.ward_ids) or any(
            not w.strip() for w in self.ward_ids
        ):
            raise ValueError("pilot ward IDs must be nonempty and unique")
        return self


class SourceVersion(DrainInput):
    domain: Literal["TERRAIN", "URBAN_GIS", "DRAINAGE", "SPATIAL", "REFERENCE", "ASSEMBLY"]
    product_id: str = Field(min_length=1)
    pipeline_version: str = Field(min_length=1)
    evidence_scope: DrainEvidenceScope
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class BlobReference(DrainInput):
    object_key: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(gt=0)


class ComponentVersion(DrainInput):
    status: Literal["AVAILABLE", "MISSING"]
    source: SourceVersion | None = None
    artifact: BlobReference | None = None
    missing_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def explicit_state(self) -> ComponentVersion:
        if self.status == "AVAILABLE":
            if self.source is None or self.artifact is None or self.missing_reason is not None:
                raise ValueError("available components require exact source and artifact identity")
        elif self.source is not None or self.artifact is not None or self.missing_reason is None:
            raise ValueError("missing components require a reason and no placeholder version")
        return self


class TwinManifest(DrainInput):
    manifest_version: Literal["sequence-9-twin-v1"] = TWIN_POLICY
    twin_id: UUID
    city_id: str = Field(min_length=1, max_length=100)
    pilot_area: PilotArea
    evidence_scope: DrainEvidenceScope
    visual_terrain_version: ComponentVersion
    hydraulic_terrain_version: ComponentVersion
    visual_city_version: ComponentVersion
    hydraulic_surface_version: ComponentVersion
    roof_runoff_geometry_version: ComponentVersion
    drain_graph_version: ComponentVersion
    exchange_geometry_version: ComponentVersion
    hydraulic_parameter_set_version: ComponentVersion
    ward_version: ComponentVersion
    catchment_version: ComponentVersion
    waterbody_version: ComponentVersion
    pump_asset_version: ComponentVersion
    horizontal_crs: str
    vertical_reference_status: Literal["COMPATIBLE", "UNRESOLVED"]
    hydraulic_readiness: HydraulicReadiness
    software_version: str = Field(min_length=1)
    software_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_artifacts: dict[str, BlobReference]
    readiness_blockers: list[str]
    real_cross_ward_path_available: bool
    final_human_acceptance_pending: Literal[True] = True
    hydraulic_validation_claimed: Literal[False] = False

    @model_validator(mode="after")
    def validate_manifest(self) -> TwinManifest:
        validate_metric_working_crs(self.horizontal_crs)
        if self.hydraulic_readiness is HydraulicReadiness.HYDRAULIC_VALIDATED:
            raise ValueError("Sequence 9 cannot create independent hydraulic validation evidence")
        for role in ComponentRole:
            component = self.component(role)
            if (
                component.source is not None
                and component.source.evidence_scope is not self.evidence_scope
            ):
                raise ValueError("a twin cannot mix reference and real evidence")
        if (
            self.evidence_scope is DrainEvidenceScope.REFERENCE_FIXTURE
            and self.real_cross_ward_path_available
        ):
            raise ValueError("a reference twin cannot claim a real cross-ward path")
        return self

    def component(self, role: ComponentRole) -> ComponentVersion:
        value: ComponentVersion = getattr(self, role.value)
        return value


class TwinBuildRequest(DrainInput):
    city_id: str = Field(min_length=1, max_length=100)
    pilot_area: PilotArea
    horizontal_crs: str
    terrain_id: UUID | None
    urban_gis_id: UUID | None
    drain_product_id: UUID | None
    ward_id: UUID
    catchment_id: UUID
    waterbody_id: UUID
    missing_reasons: dict[Literal["terrain", "urban_gis", "drainage"], str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def explicit_selection(self) -> TwinBuildRequest:
        validate_metric_working_crs(self.horizontal_crs)
        selections: list[tuple[Literal["terrain", "urban_gis", "drainage"], UUID | None]] = [
            ("terrain", self.terrain_id),
            ("urban_gis", self.urban_gis_id),
            ("drainage", self.drain_product_id),
        ]
        for name, value in selections:
            reason = self.missing_reasons.get(name)
            if value is None and (not reason or not reason.strip()):
                raise ValueError(f"missing {name} requires an explicit reason")
            if value is not None and reason is not None:
                raise ValueError(f"selected {name} cannot also claim missing")
        return self


class TwinProductRead(DrainInput):
    twin_id: UUID
    city_id: str
    pilot_area_id: str
    fingerprint: str
    pipeline_version: str
    evidence_scope: DrainEvidenceScope
    hydraulic_readiness: HydraulicReadiness
    manifest: BlobReference
    audit: BlobReference
    created_at: UtcDateTime


class TwinBuildResult(DrainInput):
    twin_id: UUID
    created: bool
    hydraulic_readiness: HydraulicReadiness


class TwinReadiness(DrainInput):
    city_id: str
    current_pipeline_version: str = TWIN_POLICY
    total_twins: int
    verified_twins: int
    reference_scenario_ready: int
    provisional_real_twins: int
    real_cross_ward_twins: int
    assembly_development_gate_passed: bool
    technical_development_gate_passed: bool
    checkpoint_a_status: Literal["REFERENCE_ONLY", "PROVISIONAL_REAL_READY", "NOT_READY"]
    freeze_blockers: list[str]
    final_human_acceptance_pending: Literal[True] = True
    final_completion_gate_passed: Literal[False] = False
    qa_viewer_path: str = "/twins/qa"
