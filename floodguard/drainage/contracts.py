"""Sequence 8 input contracts; no hydraulic simulation or readiness promotion."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from floodguard.reconstruction.contracts import ConfidenceBand
from floodguard.spatial.contracts import DatumTransformStatus, VerticalReference
from floodguard.spatial.geometry_validation import validate_geometry
from floodguard.spatial.reference import validate_metric_working_crs
from floodguard.urban_gis.contracts import EngineeringValueStatus

DRAIN_GRAPH_PACKAGE_VERSION: Final = "sequence-8-drain-graph-v1"
EvidenceText = Annotated[str, Field(min_length=1, max_length=2000)]


class DrainInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class ParameterUnit(StrEnum):
    METRE = "m"
    SQUARE_METRE = "m2"
    CUBIC_METRE = "m3"
    DISCHARGE = "m3/s"
    DIMENSIONLESS = "1"
    MANNING = "s/m^(1/3)"


class EngineeringParameter(DrainInput):
    value: float | None = None
    unit: ParameterUnit
    status: EngineeringValueStatus
    version: str = Field(min_length=1, max_length=160)
    source_reference: str | None = Field(default=None, min_length=2, max_length=1000)
    method: str | None = Field(default=None, min_length=2, max_length=2000)
    missing_reason: str | None = Field(default=None, min_length=2, max_length=1000)
    lower_bound: float | None = None
    upper_bound: float | None = None

    @field_validator("value", "lower_bound", "upper_bound", mode="before")
    @classmethod
    def reject_boolean(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("engineering values must be numbers, not booleans")
        return value

    @model_validator(mode="after")
    def validate_evidence(self) -> EngineeringParameter:
        if self.status is EngineeringValueStatus.MISSING:
            if self.value is not None or not self.missing_reason:
                raise ValueError("MISSING parameters require a reason and no value")
        else:
            if self.value is None or not self.source_reference:
                raise ValueError("known parameters require a value and source reference")
            if self.missing_reason is not None:
                raise ValueError("known parameters cannot also claim to be missing")
            if (
                self.status
                in {
                    EngineeringValueStatus.INFERRED,
                    EngineeringValueStatus.ASSUMED,
                    EngineeringValueStatus.CALIBRATED,
                }
                and not self.method
            ):
                raise ValueError("inferred, assumed and calibrated parameters require a method")
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("parameter bounds are reversed")
        if self.value is not None:
            if self.lower_bound is not None and self.value < self.lower_bound:
                raise ValueError("parameter value is below its lower bound")
            if self.upper_bound is not None and self.value > self.upper_bound:
                raise ValueError("parameter value is above its upper bound")
        return self


def missing_parameter(unit: ParameterUnit) -> EngineeringParameter:
    return EngineeringParameter(
        unit=unit,
        status=EngineeringValueStatus.MISSING,
        version="not-supplied-v1",
        missing_reason="Not supplied by the source.",
    )


def _check_parameter(
    parameter: EngineeringParameter,
    unit: ParameterUnit,
    *,
    minimum: float | None = None,
    strictly_positive: bool = False,
) -> None:
    if parameter.unit is not unit:
        raise ValueError(f"parameter requires unit {unit.value}; implicit conversion is forbidden")
    if parameter.value is not None:
        if strictly_positive and parameter.value <= 0:
            raise ValueError("parameter must be positive when supplied")
        if minimum is not None and parameter.value < minimum:
            raise ValueError(f"parameter must be at least {minimum} when supplied")


class DrainNodeType(StrEnum):
    INLET = "INLET"
    MANHOLE = "MANHOLE"
    JUNCTION = "JUNCTION"
    STORAGE = "STORAGE"
    PUMP = "PUMP"
    OUTFALL = "OUTFALL"


class DrainEdgeType(StrEnum):
    PIPE = "PIPE"
    OPEN_DRAIN = "OPEN_DRAIN"
    CULVERT = "CULVERT"
    CANAL = "CANAL"


class FlowDirectionMethod(StrEnum):
    MUNICIPAL_ARROWS_LABELS = "MUNICIPAL_ARROWS_LABELS"
    INVERT_ELEVATIONS = "INVERT_ELEVATIONS"
    PUMP_OUTFALL_TOPOLOGY = "PUMP_OUTFALL_TOPOLOGY"
    HYDRAULIC_TOPOLOGICAL_INFERENCE = "HYDRAULIC_TOPOLOGICAL_INFERENCE"
    SURFACE_TERRAIN_FALLBACK = "SURFACE_TERRAIN_FALLBACK"


DIRECTION_PRIORITY = {method: rank for rank, method in enumerate(FlowDirectionMethod)}


class FlowDirectionCandidate(DrainInput):
    from_node_id: str = Field(min_length=1, max_length=160)
    to_node_id: str = Field(min_length=1, max_length=160)
    method: FlowDirectionMethod
    source_reference: str = Field(min_length=2, max_length=1000)
    confidence: ConfidenceBand

    @model_validator(mode="after")
    def validate_direction(self) -> FlowDirectionCandidate:
        if self.from_node_id == self.to_node_id:
            raise ValueError("direction endpoints must be distinct")
        if (
            self.method is FlowDirectionMethod.SURFACE_TERRAIN_FALLBACK
            and self.confidence is not ConfidenceBand.LOW
        ):
            raise ValueError("surface-terrain direction is a LOW-confidence fallback")
        return self


def select_flow_direction(candidates: list[FlowDirectionCandidate]) -> FlowDirectionCandidate:
    if not candidates:
        raise ValueError("flow direction requires explicit evidence")
    best_rank = min(DIRECTION_PRIORITY[item.method] for item in candidates)
    strongest = [item for item in candidates if DIRECTION_PRIORITY[item.method] == best_rank]
    if len({(item.from_node_id, item.to_node_id) for item in strongest}) != 1:
        raise ValueError("strongest-priority flow-direction evidence conflicts")
    return min(strongest, key=lambda item: (item.source_reference, item.confidence.value))


class VersionedSourceReference(DrainInput):
    source_reference: str = Field(min_length=2, max_length=1000)
    version: str = Field(min_length=1, max_length=160)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _validate_geometry(geometry: dict[str, Any], kind: str) -> None:
    validate_geometry(geometry, geographic=False)
    if geometry.get("type") != kind:
        raise ValueError(f"drain geometry requires {kind}")
    positions = [geometry["coordinates"]] if kind == "Point" else geometry["coordinates"]
    if any(len(position) != 2 for position in positions):
        raise ValueError("drain geometry is strictly x/y; elevation needs explicit datum metadata")


class DrainNode(DrainInput):
    drain_node_id: str = Field(min_length=1, max_length=160)
    node_type: DrainNodeType
    ward_id: str = Field(min_length=1, max_length=100)
    geometry: dict[str, Any]
    source_reference: str = Field(min_length=2, max_length=1000)
    invert_elevation: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.METRE)
    )
    storage_volume: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.CUBIC_METRE)
    )
    pump_definition: VersionedSourceReference | None = None
    outfall_definition: VersionedSourceReference | None = None

    @model_validator(mode="after")
    def validate_node(self) -> DrainNode:
        _validate_geometry(self.geometry, "Point")
        _check_parameter(self.invert_elevation, ParameterUnit.METRE)
        _check_parameter(self.storage_volume, ParameterUnit.CUBIC_METRE, minimum=0)
        if self.pump_definition is not None and self.node_type is not DrainNodeType.PUMP:
            raise ValueError("pump definition belongs to a PUMP node")
        if self.outfall_definition is not None and self.node_type is not DrainNodeType.OUTFALL:
            raise ValueError("outfall definition belongs to an OUTFALL node")
        return self


class CrossSectionShape(StrEnum):
    UNKNOWN = "UNKNOWN"
    CIRCULAR = "CIRCULAR"
    RECTANGULAR = "RECTANGULAR"
    TRAPEZOIDAL = "TRAPEZOIDAL"


class EdgeParameters(DrainInput):
    cross_section: CrossSectionShape = CrossSectionShape.UNKNOWN
    length: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.METRE)
    )
    diameter: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.METRE)
    )
    width: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.METRE)
    )
    height: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.METRE)
    )
    side_slope: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.DIMENSIONLESS)
    )
    slope: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.DIMENSIONLESS)
    )
    roughness: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.MANNING)
    )
    effective_capacity: EngineeringParameter = Field(
        default_factory=lambda: missing_parameter(ParameterUnit.DISCHARGE)
    )
    condition: VersionedSourceReference | None = None

    @model_validator(mode="after")
    def validate_units_and_ranges(self) -> EdgeParameters:
        for parameter in (self.length, self.diameter, self.width, self.height):
            _check_parameter(parameter, ParameterUnit.METRE, strictly_positive=True)
        _check_parameter(self.side_slope, ParameterUnit.DIMENSIONLESS, minimum=0)
        _check_parameter(self.slope, ParameterUnit.DIMENSIONLESS)
        _check_parameter(self.roughness, ParameterUnit.MANNING, strictly_positive=True)
        _check_parameter(self.effective_capacity, ParameterUnit.DISCHARGE, minimum=0)
        return self


class DrainEdge(DrainInput):
    drain_edge_id: str = Field(min_length=1, max_length=160)
    edge_type: DrainEdgeType
    hydraulic_domain: Literal["NETWORK_1D"] = "NETWORK_1D"
    from_node_id: str = Field(min_length=1, max_length=160)
    to_node_id: str = Field(min_length=1, max_length=160)
    geometry: dict[str, Any]
    source_reference: str = Field(min_length=2, max_length=1000)
    direction_candidates: list[FlowDirectionCandidate] = Field(min_length=1)
    parameters: EdgeParameters = Field(default_factory=EdgeParameters)

    @model_validator(mode="after")
    def validate_edge(self) -> DrainEdge:
        _validate_geometry(self.geometry, "LineString")
        endpoints = {self.from_node_id, self.to_node_id}
        if len(endpoints) != 2:
            raise ValueError("edge endpoints must be distinct")
        if any(
            {item.from_node_id, item.to_node_id} != endpoints for item in self.direction_candidates
        ):
            raise ValueError("direction evidence must refer to the edge's endpoint pair")
        direction = select_flow_direction(self.direction_candidates)
        if (direction.from_node_id, direction.to_node_id) != (self.from_node_id, self.to_node_id):
            raise ValueError("edge orientation conflicts with strongest-priority direction")
        return self


class ExchangeType(StrEnum):
    POINT_INLET = "POINT_INLET"
    MANHOLE_SURCHARGE = "MANHOLE_SURCHARGE"


class ExchangeGeometry(DrainInput):
    exchange_id: str = Field(min_length=1, max_length=160)
    exchange_type: ExchangeType
    drain_node_id: str = Field(min_length=1, max_length=160)
    geometry: dict[str, Any]
    x: float
    y: float
    rim_elevation: EngineeringParameter
    opening_area: EngineeringParameter
    inlet_type: str = Field(min_length=1, max_length=160)
    discharge_coefficient: EngineeringParameter
    maximum_inlet_capacity: EngineeringParameter
    source_reference: str = Field(min_length=2, max_length=1000)
    confidence: ConfidenceBand

    @model_validator(mode="after")
    def validate_exchange(self) -> ExchangeGeometry:
        _validate_geometry(self.geometry, "Point")
        if self.geometry["coordinates"] != [self.x, self.y]:
            raise ValueError("exchange x/y must match its point geometry")
        _check_parameter(self.rim_elevation, ParameterUnit.METRE)
        _check_parameter(self.opening_area, ParameterUnit.SQUARE_METRE, strictly_positive=True)
        _check_parameter(
            self.discharge_coefficient, ParameterUnit.DIMENSIONLESS, strictly_positive=True
        )
        _check_parameter(self.maximum_inlet_capacity, ParameterUnit.DISCHARGE, minimum=0)
        return self


class DrainEvidenceScope(StrEnum):
    REFERENCE_FIXTURE = "REFERENCE_FIXTURE"
    REAL_PILOT_PROVISIONAL = "REAL_PILOT_PROVISIONAL"


class DrainGraphPackage(DrainInput):
    package_version: Literal["sequence-8-drain-graph-v1"] = DRAIN_GRAPH_PACKAGE_VERSION
    city_id: str = Field(min_length=1, max_length=100)
    pilot_area_id: str = Field(min_length=1, max_length=160)
    working_crs: str = Field(min_length=1, max_length=100)
    evidence_scope: DrainEvidenceScope
    source_references: list[VersionedSourceReference] = Field(min_length=1)
    vertical_reference: VerticalReference
    endpoint_tolerance_m: float = Field(default=0.01, gt=0, le=1)
    nodes: list[DrainNode] = Field(min_length=2)
    edges: list[DrainEdge] = Field(min_length=1)
    exchanges: list[ExchangeGeometry] = Field(default_factory=list)
    limitations: list[EvidenceText] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_graph(self) -> DrainGraphPackage:
        validate_metric_working_crs(self.working_crs)
        if self.vertical_reference.vertical_unit not in {None, "m"}:
            raise ValueError("drain elevation metadata must use metres after explicit conversion")
        offset = self.vertical_reference.vertical_offset_m
        if offset is not None and not math.isfinite(offset):
            raise ValueError("vertical-reference offset must be finite")
        sources = [(item.source_reference, item.version) for item in self.source_references]
        if len(set(sources)) != len(sources):
            raise ValueError("each source reference/version must have a unique identity")
        for identifiers in (
            [item.drain_node_id for item in self.nodes],
            [item.drain_edge_id for item in self.edges],
            [item.exchange_id for item in self.exchanges],
        ):
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(
                    "node, edge and exchange IDs must be unique within each collection"
                )
        nodes = {node.drain_node_id: node for node in self.nodes}
        for edge in self.edges:
            if edge.from_node_id not in nodes or edge.to_node_id not in nodes:
                raise ValueError("edge references an unknown node")
            start, end = nodes[edge.from_node_id], nodes[edge.to_node_id]
            coordinates = edge.geometry["coordinates"]
            if (
                math.dist(coordinates[0], start.geometry["coordinates"]) > self.endpoint_tolerance_m
                or math.dist(coordinates[-1], end.geometry["coordinates"])
                > self.endpoint_tolerance_m
            ):
                raise ValueError("ordered edge geometry must meet its declared endpoint nodes")
            if select_flow_direction(edge.direction_candidates).method is (
                FlowDirectionMethod.INVERT_ELEVATIONS
            ):
                reference = self.vertical_reference
                if (
                    reference.datum_transform_status
                    not in {
                        DatumTransformStatus.COMPATIBLE,
                        DatumTransformStatus.TRANSFORMED,
                    }
                    or reference.vertical_unit != "m"
                ):
                    raise ValueError("invert-based direction requires a compatible metric datum")
                upstream, downstream = start.invert_elevation.value, end.invert_elevation.value
                if upstream is None or downstream is None or upstream <= downstream:
                    raise ValueError("invert-based direction requires known descending inverts")
        for exchange in self.exchanges:
            if exchange.drain_node_id not in nodes:
                raise ValueError("exchange references an unknown drain node")
            node = nodes[exchange.drain_node_id]
            expected = (
                DrainNodeType.INLET
                if exchange.exchange_type is ExchangeType.POINT_INLET
                else DrainNodeType.MANHOLE
            )
            if node.node_type is not expected:
                raise ValueError("exchange type must match its INLET or MANHOLE node")
            if math.dist(exchange.geometry["coordinates"], node.geometry["coordinates"]) > (
                self.endpoint_tolerance_m
            ):
                raise ValueError(
                    "exchange point must meet its drain node within endpoint tolerance"
                )
        return self
