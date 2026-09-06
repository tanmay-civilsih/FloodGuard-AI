"""Conservative static-model readiness; no solver validation or human approval."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Literal

from floodguard.drainage.contracts import DrainEvidenceScope, DrainInput, DrainNode, DrainNodeType
from floodguard.drainage.model_contracts import DrainModelInput, HydraulicReadiness
from floodguard.drainage.topology import TopologyReport, inspect_topology
from floodguard.spatial.contracts import DatumTransformStatus


def shape(geometry: dict[str, Any]) -> Any:
    return import_module("shapely.geometry").shape(geometry)


class DrainAssessment(DrainInput):
    policy_version: Literal["sequence-8-readiness-v1"] = "sequence-8-readiness-v1"
    readiness_status: HydraulicReadiness
    topology: TopologyReport
    geometry_errors: list[str]
    definition_errors: list[str]
    scenario_blockers: list[str]
    geometric_cross_ward_path: bool
    cross_ward_evidence_scope: Literal["REFERENCE_GEOMETRY", "SOURCE_BOUND_GEOMETRY"]
    real_cross_ward_path_available: bool
    final_human_acceptance_pending: Literal[True] = True
    hydraulic_validation_claimed: Literal[False] = False


def assess(model: DrainModelInput) -> DrainAssessment:
    model = DrainModelInput.model_validate(model.model_dump(mode="json"))
    graph = model.graph
    topology = inspect_topology(graph)
    nodes = {item.drain_node_id: item for item in graph.nodes}
    edges = {item.drain_edge_id: item for item in graph.edges}
    wards = {item.ward_id: shape(item.geometry) for item in model.wards.boundaries}
    geometry_errors: list[str] = []
    definitions: list[str] = []
    tolerance = graph.endpoint_tolerance_m
    for node in graph.nodes:
        ward = wards.get(node.ward_id)
        if ward is None or not ward.covers(shape(node.geometry)):
            geometry_errors.append(f"Node {node.drain_node_id} is outside its declared ward.")

    for edge in graph.edges:
        source_ward = nodes[edge.from_node_id].ward_id
        target_ward = nodes[edge.to_node_id].ward_id
        if (source_ward == target_ward and source_ward in wards
            and not wards[source_ward].buffer(tolerance).covers(shape(edge.geometry))):
            geometry_errors.append(f"Edge {edge.drain_edge_id} leaves its declared ward.")

    valid_transitions: set[str] = set()
    for transition in topology.ward_transitions:
        first, second = wards.get(transition.from_ward_id), wards.get(transition.to_ward_id)
        edge = edges[transition.drain_edge_id]
        line = shape(edge.geometry)
        if first is None or second is None:
            continue
        shared = first.boundary.intersection(second.boundary)
        if (
            shared.length <= tolerance
            or first.intersection(second).area > tolerance**2
            or not line.intersects(shared)
            or not first.union(second).buffer(tolerance).covers(line)
            or line.intersection(first).length <= tolerance
            or line.intersection(second).length <= tolerance
        ):
            geometry_errors.append(f"Edge {edge.drain_edge_id} lacks an adjacent-ward crossing.")
        else:
            valid_transitions.add(edge.drain_edge_id)

    supplied: dict[str, set[str]] = {}
    definition_node: DrainNode | None
    for items, kind, label in (
        (model.definitions.pumps, DrainNodeType.PUMP, "pump"),
        (model.definitions.storages, DrainNodeType.STORAGE, "storage"),
        (model.definitions.outfalls, DrainNodeType.OUTFALL, "outfall"),
    ):
        supplied[label] = {item.drain_node_id for item in items}
        for item in items:
            definition_node = nodes.get(item.drain_node_id)
            if definition_node is None or definition_node.node_type is not kind:
                definitions.append(f"{label} definition refers to an incompatible node.")
            if item.evidence.source not in graph.source_references:
                definitions.append(f"{label} definition source is absent from graph lineage.")
        for node in graph.nodes:
            if node.node_type is kind and node.drain_node_id not in supplied[label]:
                definitions.append(f"Node {node.drain_node_id} lacks its {label} definition.")

    for pump in model.definitions.pumps:
        definition_node = nodes.get(pump.drain_node_id)
        if definition_node is not None and definition_node.pump_definition != pump.evidence.source:
            definitions.append(f"Pump {pump.drain_node_id} definition identity does not match.")
    for storage in model.definitions.storages:
        definition_node = nodes.get(storage.drain_node_id)
        volume = sum(
            (a.area_m2 + b.area_m2) * 0.5 * (b.depth_m - a.depth_m)
            for a, b in zip(storage.curve, storage.curve[1:], strict=False)
        )
        if (
            definition_node is not None
            and definition_node.storage_volume.value is not None
            and abs(volume - definition_node.storage_volume.value) > 1e-9 * max(volume, 1.0)
        ):
            definitions.append(f"Storage {storage.drain_node_id} volume differs from its curve.")

    valid_outfalls: set[str] = set()
    for outfall in model.definitions.outfalls:
        definition_node = nodes.get(outfall.drain_node_id)
        valid = definition_node is not None and definition_node.node_type is DrainNodeType.OUTFALL
        if valid and definition_node is not None:
            valid = (
                definition_node.outfall_definition == outfall.evidence.source
                and outfall.evidence.source in graph.source_references
                and shape(outfall.receiving_geometry).distance(shape(definition_node.geometry))
                <= tolerance
                and not (
                    graph.evidence_scope is DrainEvidenceScope.REAL_PILOT_PROVISIONAL
                    and outfall.destination_kind == "REFERENCE_RECEIVER"
                )
            )
        if not valid:
            definitions.append(
                f"Outfall {outfall.drain_node_id} lacks matching destination evidence."
            )
        else:
            valid_outfalls.add(outfall.drain_node_id)

    cross_ward = not geometry_errors and any(
        path.outfall_node_id in valid_outfalls and bool(set(path.edge_ids) & valid_transitions)
        for path in topology.outfall_paths
    )
    connectivity_errors = []
    if topology.unreachable_node_ids:
        connectivity_errors.append("Some nodes cannot reach a declared outfall.")
    if topology.missing_exchange_node_ids:
        connectivity_errors.append("Some inlet/manhole nodes lack physical exchange geometry.")
    if not valid_outfalls:
        connectivity_errors.append("No outfall has a source-bound receiving destination.")
    hydrologic_ready = not (geometry_errors or definitions or connectivity_errors)
    blockers = [*geometry_errors, *definitions, *connectivity_errors]
    if topology.parameter_gaps:
        blockers.append(
            f"{len(topology.parameter_gaps)} required hydraulic parameters are missing."
        )
    reference = graph.vertical_reference
    comparable = (
        reference.datum_transform_status
        in {
            DatumTransformStatus.COMPATIBLE,
            DatumTransformStatus.TRANSFORMED,
        }
        and reference.vertical_unit == "m"
    )
    if not comparable:
        blockers.append(
            "A compatible or explicitly transformed metric vertical reference is required."
        )
    else:
        for exchange in graph.exchanges:
            invert = nodes[exchange.drain_node_id].invert_elevation.value
            rim = exchange.rim_elevation.value
            if invert is not None and rim is not None and rim < invert:
                blockers.append(f"Exchange {exchange.exchange_id} rim is below its node invert.")
    for outfall in model.definitions.outfalls:
        if outfall.stage_elevation is not None and outfall.stage_elevation.value is None:
            blockers.append(f"Outfall {outfall.drain_node_id} fixed stage is missing.")
    status = HydraulicReadiness.VISUAL_ONLY
    if hydrologic_ready:
        status = HydraulicReadiness.HYDROLOGIC_READY
    if not blockers:
        status = HydraulicReadiness.HYDRAULIC_SCENARIO_READY
    real = graph.evidence_scope is DrainEvidenceScope.REAL_PILOT_PROVISIONAL
    return DrainAssessment(
        readiness_status=status,
        topology=topology,
        geometry_errors=geometry_errors,
        definition_errors=definitions,
        scenario_blockers=list(dict.fromkeys(blockers)),
        geometric_cross_ward_path=cross_ward,
        cross_ward_evidence_scope="SOURCE_BOUND_GEOMETRY" if real else "REFERENCE_GEOMETRY",
        real_cross_ward_path_available=bool(real and cross_ward),
    )
