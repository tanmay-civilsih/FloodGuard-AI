"""Controlled six-node reference, never evidence of real Kolkata drainage connectivity."""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from floodguard.drainage.contracts import (
    CrossSectionShape,
    DrainEdge,
    DrainEdgeType,
    DrainEvidenceScope,
    DrainGraphPackage,
    DrainNode,
    DrainNodeType,
    EdgeParameters,
    EngineeringParameter,
    ExchangeGeometry,
    ExchangeType,
    FlowDirectionCandidate,
    FlowDirectionMethod,
    ParameterUnit,
    VersionedSourceReference,
)
from floodguard.drainage.model_contracts import (
    DefinitionEvidence,
    DrainModelInput,
    HydraulicDefinitions,
    OutfallDefinition,
    PumpCurvePoint,
    PumpDefinition,
    StorageCurvePoint,
    StorageDefinition,
    WardBoundary,
    WardBoundarySet,
)
from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.reconstruction.contracts import ConfidenceBand
from floodguard.spatial.contracts import DatumTransformStatus, VerticalReference
from floodguard.urban_gis.contracts import EngineeringValueStatus


def rectangle(x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def parameter(value: float, unit: ParameterUnit) -> EngineeringParameter:
    return EngineeringParameter(
        value=value,
        unit=unit,
        status=EngineeringValueStatus.ASSUMED,
        version="reference-v1",
        source_reference="reference-fixture://sequence8",
        method="Controlled synthetic benchmark value.",
    )


def reference_model(city_id: str = "kolkata", working_crs: str = "EPSG:32645") -> DrainModelInput:
    x, y = 300000.0, 2500000.0
    boundary_values = [
        WardBoundary(ward_id="reference-A", geometry=rectangle(x - 10, y - 20, x + 25, y + 20)),
        WardBoundary(ward_id="reference-B", geometry=rectangle(x + 25, y - 20, x + 70, y + 20)),
    ]
    ward_source = VersionedSourceReference(
        source_reference="reference-fixture://sequence8-wards",
        version="v1",
        sha256=sha256(canonical_bytes([item.model_dump(mode="json") for item in boundary_values])),
    )
    source = VersionedSourceReference(
        source_reference="reference-fixture://sequence8-engineering",
        version="v1",
        sha256=sha256(b"Sequence 8 controlled static engineering definitions v1"),
    )
    evidence = DefinitionEvidence(
        source=source,
        status=EngineeringValueStatus.ASSUMED,
        method="Synthetic fixture; no real assets or observations.",
    )
    nodes = [
        DrainNode(
            drain_node_id=kind.value.lower(),
            node_type=kind,
            ward_id="reference-A" if index < 3 else "reference-B",
            geometry={"type": "Point", "coordinates": [x + 10 * index, y]},
            source_reference=source.source_reference,
            invert_elevation=parameter(5 - index * 0.1, ParameterUnit.METRE),
            storage_volume=parameter(
                20 if kind is DrainNodeType.STORAGE else 0, ParameterUnit.CUBIC_METRE
            ),
            pump_definition=source if kind is DrainNodeType.PUMP else None,
            outfall_definition=source if kind is DrainNodeType.OUTFALL else None,
        )
        for index, kind in enumerate(DrainNodeType)
    ]
    edges = []
    for index, (start, end) in enumerate(pairwise(nodes)):
        kind = list(DrainEdgeType)[index % len(DrainEdgeType)]
        edges.append(
            DrainEdge(
                drain_edge_id=f"reference-edge-{index}",
                edge_type=kind,
                from_node_id=start.drain_node_id,
                to_node_id=end.drain_node_id,
                geometry={
                    "type": "LineString",
                    "coordinates": [start.geometry["coordinates"], end.geometry["coordinates"]],
                },
                source_reference=source.source_reference,
                direction_candidates=[
                    FlowDirectionCandidate(
                        from_node_id=start.drain_node_id,
                        to_node_id=end.drain_node_id,
                        method=FlowDirectionMethod.INVERT_ELEVATIONS,
                        source_reference=source.source_reference,
                        confidence=ConfidenceBand.HIGH,
                    )
                ],
                parameters=EdgeParameters(
                    cross_section=CrossSectionShape.CIRCULAR
                    if kind is DrainEdgeType.PIPE
                    else CrossSectionShape.RECTANGULAR,
                    length=parameter(10, ParameterUnit.METRE),
                    diameter=parameter(1, ParameterUnit.METRE),
                    width=parameter(1, ParameterUnit.METRE),
                    height=parameter(1, ParameterUnit.METRE),
                    slope=parameter(0.01, ParameterUnit.DIMENSIONLESS),
                    roughness=parameter(0.015, ParameterUnit.MANNING),
                    effective_capacity=parameter(0.5, ParameterUnit.DISCHARGE),
                    condition=source,
                ),
            )
        )
    exchanges = [
        ExchangeGeometry(
            exchange_id=f"reference-exchange-{index}",
            exchange_type=ExchangeType.POINT_INLET
            if index == 0
            else ExchangeType.MANHOLE_SURCHARGE,
            drain_node_id=node.drain_node_id,
            geometry=node.geometry,
            x=node.geometry["coordinates"][0],
            y=y,
            rim_elevation=parameter(6, ParameterUnit.METRE),
            opening_area=parameter(0.1, ParameterUnit.SQUARE_METRE),
            inlet_type="REFERENCE_OPENING",
            discharge_coefficient=parameter(0.6, ParameterUnit.DIMENSIONLESS),
            maximum_inlet_capacity=parameter(0.1, ParameterUnit.DISCHARGE),
            source_reference=source.source_reference,
            confidence=ConfidenceBand.HIGH,
        )
        for index, node in enumerate(nodes[:2])
    ]
    graph = DrainGraphPackage(
        city_id=city_id,
        pilot_area_id="kolkata-sequence8-reference",
        working_crs=working_crs,
        evidence_scope=DrainEvidenceScope.REFERENCE_FIXTURE,
        source_references=[source, ward_source],
        vertical_reference=VerticalReference(
            vertical_datum="SYNTHETIC_REFERENCE_DATUM",
            vertical_unit="m",
            datum_transform_status=DatumTransformStatus.COMPATIBLE,
        ),
        nodes=nodes,
        edges=edges,
        exchanges=exchanges,
        limitations=[
            "Controlled synthetic network and adjacent wards; not real Kolkata evidence.",
            "Static contracts only; no SWMM execution, hydraulic validation or forecast.",
        ],
    )
    definitions = HydraulicDefinitions(
        pumps=[
            PumpDefinition(
                drain_node_id="pump",
                evidence=evidence,
                initially_enabled=True,
                curve=[
                    PumpCurvePoint(head_m=0, discharge_m3_s=1),
                    PumpCurvePoint(head_m=5, discharge_m3_s=0),
                ],
            )
        ],
        storages=[
            StorageDefinition(
                drain_node_id="storage",
                evidence=evidence,
                curve=[
                    StorageCurvePoint(depth_m=0, area_m2=10),
                    StorageCurvePoint(depth_m=2, area_m2=10),
                ],
            )
        ],
        outfalls=[
            OutfallDefinition(
                drain_node_id="outfall",
                evidence=evidence,
                destination_id="reference-receiver",
                destination_kind="REFERENCE_RECEIVER",
                boundary_type="FREE",
                receiving_geometry=rectangle(x + 49, y - 5, x + 60, y + 5),
            )
        ],
    )
    return DrainModelInput(
        graph=graph,
        definitions=definitions,
        wards=WardBoundarySet(
            working_crs=working_crs,
            evidence_scope=DrainEvidenceScope.REFERENCE_FIXTURE,
            source=ward_source,
            boundaries=boundary_values,
        ),
    )
