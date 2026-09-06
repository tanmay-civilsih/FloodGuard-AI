"""Versioned Sequence 8 import, hydraulic definition and product contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from floodguard.contracts.time import UtcDateTime
from floodguard.drainage.contracts import (
    DrainEvidenceScope,
    DrainGraphPackage,
    DrainInput,
    EngineeringParameter,
    EvidenceText,
    ParameterUnit,
    VersionedSourceReference,
    _check_parameter,
)
from floodguard.spatial.geometry_validation import validate_geometry
from floodguard.spatial.reference import validate_metric_working_crs
from floodguard.urban_gis.contracts import EngineeringValueStatus

DRAIN_MODEL_PIPELINE_VERSION = "sequence-8-drain-model-v1"


class HydraulicReadiness(StrEnum):
    VISUAL_ONLY = "VISUAL_ONLY"
    HYDROLOGIC_READY = "HYDROLOGIC_READY"
    HYDRAULIC_SCENARIO_READY = "HYDRAULIC_SCENARIO_READY"
    HYDRAULIC_VALIDATED = "HYDRAULIC_VALIDATED"


class DefinitionEvidence(DrainInput):
    source: VersionedSourceReference
    status: EngineeringValueStatus
    method: EvidenceText

    @model_validator(mode="after")
    def known_definition(self) -> DefinitionEvidence:
        if self.status is EngineeringValueStatus.MISSING:
            raise ValueError("a supplied definition cannot claim MISSING evidence")
        return self


class PumpCurvePoint(DrainInput):
    head_m: float = Field(ge=0)
    discharge_m3_s: float = Field(ge=0)


class PumpDefinition(DrainInput):
    drain_node_id: str = Field(min_length=1)
    evidence: DefinitionEvidence
    curve: list[PumpCurvePoint] = Field(min_length=2)
    initially_enabled: bool

    @model_validator(mode="after")
    def validate_curve(self) -> PumpDefinition:
        for previous, current in zip(self.curve, self.curve[1:], strict=False):
            if (
                current.head_m <= previous.head_m
                or current.discharge_m3_s > previous.discharge_m3_s
            ):
                raise ValueError(
                    "pump head must increase and discharge must not increase with head"
                )
        if not any(point.discharge_m3_s > 0 for point in self.curve):
            raise ValueError("pump curve must contain positive capacity")
        return self


class StorageCurvePoint(DrainInput):
    depth_m: float = Field(ge=0)
    area_m2: float = Field(gt=0)


class StorageDefinition(DrainInput):
    drain_node_id: str = Field(min_length=1)
    evidence: DefinitionEvidence
    curve: list[StorageCurvePoint] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_curve(self) -> StorageDefinition:
        if self.curve[0].depth_m != 0:
            raise ValueError("storage curve must start at zero depth")
        if any(b.depth_m <= a.depth_m for a, b in zip(self.curve, self.curve[1:], strict=False)):
            raise ValueError("storage depths must strictly increase")
        return self


class OutfallDefinition(DrainInput):
    drain_node_id: str = Field(min_length=1)
    evidence: DefinitionEvidence
    destination_id: str = Field(min_length=1)
    destination_kind: Literal["RIVER", "CANAL", "DRAIN_NETWORK", "BOUNDARY", "REFERENCE_RECEIVER"]
    receiving_geometry: dict[str, Any]
    boundary_type: Literal["FREE", "FIXED_STAGE"]
    stage_elevation: EngineeringParameter | None = None

    @model_validator(mode="after")
    def validate_destination(self) -> OutfallDefinition:
        validate_geometry(self.receiving_geometry, geographic=False)
        if self.receiving_geometry.get("type") not in {"Polygon", "MultiPolygon", "LineString"}:
            raise ValueError("outfall receiver must be polygonal or linear geometry")
        if self.boundary_type == "FIXED_STAGE":
            if self.stage_elevation is None:
                raise ValueError("fixed stage requires an explicit elevation parameter")
            _check_parameter(self.stage_elevation, ParameterUnit.METRE)
        elif self.stage_elevation is not None:
            raise ValueError("FREE boundary cannot also define a fixed stage")
        return self


class HydraulicDefinitions(DrainInput):
    pumps: list[PumpDefinition] = Field(default_factory=list)
    storages: list[StorageDefinition] = Field(default_factory=list)
    outfalls: list[OutfallDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_nodes(self) -> HydraulicDefinitions:
        for items in (self.pumps, self.storages, self.outfalls):
            identifiers = [item.drain_node_id for item in items]
            if len(set(identifiers)) != len(identifiers):
                raise ValueError("hydraulic definitions must be unique per node")
        return self


class WardBoundary(DrainInput):
    ward_id: str = Field(min_length=1, max_length=100)
    geometry: dict[str, Any]

    @model_validator(mode="after")
    def polygon(self) -> WardBoundary:
        validate_geometry(self.geometry, geographic=False)
        if self.geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("ward boundary must be polygonal")
        return self


class WardBoundarySet(DrainInput):
    working_crs: str
    evidence_scope: DrainEvidenceScope
    source: VersionedSourceReference
    boundaries: list[WardBoundary] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_identity(self) -> WardBoundarySet:
        validate_metric_working_crs(self.working_crs)
        identifiers = [ward.ward_id for ward in self.boundaries]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("ward IDs must be unique")
        return self


class DrainModelInput(DrainInput):
    graph: DrainGraphPackage
    wards: WardBoundarySet
    definitions: HydraulicDefinitions = Field(default_factory=HydraulicDefinitions)

    @model_validator(mode="after")
    def coherent_scope(self) -> DrainModelInput:
        if self.graph.working_crs != self.wards.working_crs:
            raise ValueError("graph and wards must share the metric working CRS")
        if self.graph.evidence_scope is not self.wards.evidence_scope:
            raise ValueError("graph and wards must have the same evidence scope")
        if self.wards.source not in self.graph.source_references:
            raise ValueError("the exact ward source must be present in graph lineage")
        return self


class ImportSourceInfo(DrainInput):
    city_id: str
    pilot_area_id: str
    working_crs: str
    reconstruction_id: UUID
    normalization_id: UUID
    reconstruction_source: VersionedSourceReference
    ward_source: VersionedSourceReference
    evidence_scope: DrainEvidenceScope


class ImportFeature(DrainInput):
    source_feature_id: str
    feature_kind: Literal["DRAIN", "STRUCTURE", "LABEL"]
    geometry: dict[str, Any]
    source_properties: dict[str, Any]
    intersecting_ward_ids: list[str]


class DrainImportDraft(DrainInput):
    source_info: ImportSourceInfo
    features: list[ImportFeature]
    unresolved_items: list[str]
    direction_assigned: Literal[False] = False
    connections_inferred: Literal[False] = False
    readiness_status: Literal["VISUAL_ONLY"] = "VISUAL_ONLY"


class NodeSourceBinding(DrainInput):
    drain_node_id: str
    source_feature_id: str
    location: Literal["POINT", "START", "END", "ON_LINE"]


class EdgeSourceBinding(DrainInput):
    drain_edge_id: str
    source_feature_ids: list[str] = Field(min_length=1)


class ImportBindingPlan(DrainInput):
    draft_id: UUID
    draft_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    graph: DrainGraphPackage
    definitions: HydraulicDefinitions = Field(default_factory=HydraulicDefinitions)
    node_bindings: list[NodeSourceBinding]
    edge_bindings: list[EdgeSourceBinding]


class ArtifactReference(DrainInput):
    object_key: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=0)
    media_type: str


class DrainProductRead(DrainInput):
    product_id: UUID
    city_id: str
    pilot_area_id: str
    fingerprint: str
    pipeline_version: str
    product_kind: Literal["IMPORT_DRAFT", "DIRECTED_GRAPH"]
    evidence_scope: DrainEvidenceScope
    working_crs: str
    artifacts: dict[str, ArtifactReference]
    created_at: UtcDateTime


class DrainBuildResult(DrainInput):
    product_id: UUID
    created: bool
    product_kind: Literal["IMPORT_DRAFT", "DIRECTED_GRAPH"]


class DrainReadiness(DrainInput):
    city_id: str
    current_pipeline_version: str = DRAIN_MODEL_PIPELINE_VERSION
    total_products: int
    eligible_products: int
    real_pilot_imports: int
    reference_ready: int
    provisional_real_graphs: int
    real_cross_ward_path_available: bool
    technical_development_gate_passed: bool
    final_human_acceptance_pending: Literal[True] = True
    final_completion_gate_passed: Literal[False] = False
    sequence9_real_cross_ward_gate_passed: bool
    completion_reason: str
    qa_viewer_path: str = "/drainage/qa"
