"""Controlled graph fixtures; coordinates and wards do not represent real Kolkata assets."""

from hashlib import sha256

from floodguard.drainage.contracts import (
    DrainEdge,
    DrainEdgeType,
    DrainEvidenceScope,
    DrainGraphPackage,
    DrainNode,
    DrainNodeType,
    EngineeringParameter,
    ExchangeGeometry,
    ExchangeType,
    FlowDirectionCandidate,
    FlowDirectionMethod,
    ParameterUnit,
    VersionedSourceReference,
    missing_parameter,
)
from floodguard.reconstruction.contracts import ConfidenceBand
from floodguard.spatial.contracts import DatumTransformStatus, VerticalReference
from floodguard.urban_gis.contracts import EngineeringValueStatus


def assumed(value: float, unit: ParameterUnit) -> EngineeringParameter:
    return EngineeringParameter(
        value=value,
        unit=unit,
        status=EngineeringValueStatus.ASSUMED,
        source_reference="reference-fixture://drainage",
        version="fixture-v1",
        method="Controlled synthetic value for a deterministic contract test.",
    )


def node(node_id: str, kind: DrainNodeType, x: float, ward: str = "reference-ward-A") -> DrainNode:
    return DrainNode(
        drain_node_id=node_id,
        node_type=kind,
        ward_id=ward,
        geometry={"type": "Point", "coordinates": [x, 2_500_000.0]},
        source_reference="reference-fixture://drainage",
    )


def edge(edge_id: str, source: DrainNode, target: DrainNode) -> DrainEdge:
    return DrainEdge(
        drain_edge_id=edge_id,
        edge_type=DrainEdgeType.PIPE,
        from_node_id=source.drain_node_id,
        to_node_id=target.drain_node_id,
        geometry={
            "type": "LineString",
            "coordinates": [
                source.geometry["coordinates"],
                target.geometry["coordinates"],
            ],
        },
        source_reference="reference-fixture://drainage",
        direction_candidates=[
            FlowDirectionCandidate(
                from_node_id=source.drain_node_id,
                to_node_id=target.drain_node_id,
                method=FlowDirectionMethod.MUNICIPAL_ARROWS_LABELS,
                source_reference="reference-fixture://simulated-arrow",
                confidence=ConfidenceBand.HIGH,
            )
        ],
    )


def exchange(target: DrainNode) -> ExchangeGeometry:
    return ExchangeGeometry(
        exchange_id="exchange-" + target.drain_node_id,
        exchange_type=(
            ExchangeType.POINT_INLET
            if target.node_type is DrainNodeType.INLET
            else ExchangeType.MANHOLE_SURCHARGE
        ),
        drain_node_id=target.drain_node_id,
        geometry=target.geometry,
        x=target.geometry["coordinates"][0],
        y=2_500_000.0,
        rim_elevation=missing_parameter(ParameterUnit.METRE),
        opening_area=missing_parameter(ParameterUnit.SQUARE_METRE),
        inlet_type="REFERENCE_ONLY",
        discharge_coefficient=missing_parameter(ParameterUnit.DIMENSIONLESS),
        maximum_inlet_capacity=missing_parameter(ParameterUnit.DISCHARGE),
        source_reference="reference-fixture://drainage",
        confidence=ConfidenceBand.LOW,
    )


def graph() -> DrainGraphPackage:
    inlet = node("inlet", DrainNodeType.INLET, 300_000.0)
    manhole = node("manhole", DrainNodeType.MANHOLE, 300_010.0)
    outfall = node("outfall", DrainNodeType.OUTFALL, 300_020.0, "reference-ward-B")
    return DrainGraphPackage(
        city_id="reference-city",
        pilot_area_id="sequence8-reference",
        working_crs="EPSG:32645",
        evidence_scope=DrainEvidenceScope.REFERENCE_FIXTURE,
        source_references=[
            VersionedSourceReference(
                source_reference="reference-fixture://drainage",
                version="fixture-v1",
                sha256=sha256(b"Controlled three-node Sequence 8 topology fixture v1").hexdigest(),
            )
        ],
        vertical_reference=VerticalReference(
            datum_transform_status=DatumTransformStatus.UNRESOLVED
        ),
        nodes=[inlet, manhole, outfall],
        edges=[edge("pipe-a", inlet, manhole), edge("pipe-b", manhole, outfall)],
        exchanges=[exchange(inlet), exchange(manhole)],
        limitations=["Synthetic geometry and ward identifiers; no real cross-ward evidence."],
    )
