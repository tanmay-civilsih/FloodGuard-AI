"""Deterministic graph diagnostics, not hydraulic flow or real-pilot acceptance."""

from __future__ import annotations

from collections import deque
from typing import Literal

from floodguard.drainage.contracts import (
    CrossSectionShape,
    DrainGraphPackage,
    DrainInput,
    DrainNodeType,
    EngineeringParameter,
    ParameterUnit,
)


class OutfallPath(DrainInput):
    from_node_id: str
    outfall_node_id: str
    node_ids: list[str]
    edge_ids: list[str]


class WardTransition(DrainInput):
    drain_edge_id: str
    from_ward_id: str
    to_ward_id: str


class ParameterGap(DrainInput):
    entity_type: Literal["NODE", "EDGE", "EXCHANGE"]
    entity_id: str
    parameter: str
    unit: ParameterUnit | None = None
    reason: str


class TopologyReport(DrainInput):
    node_count: int
    edge_count: int
    exchange_count: int
    outfall_paths: list[OutfallPath]
    unreachable_node_ids: list[str]
    unconnected_node_ids: list[str]
    missing_exchange_node_ids: list[str]
    ward_transitions: list[WardTransition]
    parameter_gaps: list[ParameterGap]
    cross_ward_connectivity_scope: Literal["DECLARED_WARD_IDS_ONLY"] = "DECLARED_WARD_IDS_ONLY"
    genuine_cross_ward_continuation_verified: Literal[False] = False
    hydraulic_validation_claimed: Literal[False] = False


def inspect_topology(package: DrainGraphPackage) -> TopologyReport:
    """Inspect nominal direction; cycles and later hydraulic reverse flow remain permissible."""
    # Revalidate nested collections so mutation after construction cannot bypass graph checks.
    package = DrainGraphPackage.model_validate(package.model_dump(mode="json"))
    nodes = {node.drain_node_id: node for node in package.nodes}
    adjacency: dict[str, list[tuple[str, str]]] = {node_id: [] for node_id in nodes}
    incident: set[str] = set()
    transitions: list[WardTransition] = []
    for edge in sorted(package.edges, key=lambda item: item.drain_edge_id):
        adjacency[edge.from_node_id].append((edge.to_node_id, edge.drain_edge_id))
        incident.update((edge.from_node_id, edge.to_node_id))
        source_ward = nodes[edge.from_node_id].ward_id
        target_ward = nodes[edge.to_node_id].ward_id
        if source_ward != target_ward:
            transitions.append(
                WardTransition(
                    drain_edge_id=edge.drain_edge_id,
                    from_ward_id=source_ward,
                    to_ward_id=target_ward,
                )
            )

    paths: list[OutfallPath] = []
    unreachable: list[str] = []
    for start in sorted(nodes):
        queue: deque[tuple[str, list[str], list[str]]] = deque([(start, [start], [])])
        visited = {start}
        while queue:
            node_id, node_path, edge_path = queue.popleft()
            if nodes[node_id].node_type is DrainNodeType.OUTFALL:
                paths.append(
                    OutfallPath(
                        from_node_id=start,
                        outfall_node_id=node_id,
                        node_ids=node_path,
                        edge_ids=edge_path,
                    )
                )
                break
            for target, edge_id in sorted(adjacency[node_id]):
                if target not in visited:
                    visited.add(target)
                    queue.append((target, [*node_path, target], [*edge_path, edge_id]))
        else:
            unreachable.append(start)

    gaps: list[ParameterGap] = []

    def scalar_gap(
        entity_type: Literal["NODE", "EDGE", "EXCHANGE"],
        entity_id: str,
        name: str,
        parameter: EngineeringParameter,
    ) -> None:
        if parameter.value is None:
            gaps.append(
                ParameterGap(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    parameter=name,
                    unit=parameter.unit,
                    reason=parameter.missing_reason or "Value unavailable.",
                )
            )

    def reference_gap(
        entity_type: Literal["NODE", "EDGE", "EXCHANGE"],
        entity_id: str,
        name: str,
    ) -> None:
        gaps.append(
            ParameterGap(
                entity_type=entity_type,
                entity_id=entity_id,
                parameter=name,
                reason="No versioned source definition supplied.",
            )
        )

    for node_id, node in sorted(nodes.items()):
        scalar_gap("NODE", node_id, "invert_elevation", node.invert_elevation)
        if node.node_type is DrainNodeType.STORAGE:
            scalar_gap("NODE", node_id, "storage_volume", node.storage_volume)
        if node.node_type is DrainNodeType.PUMP and node.pump_definition is None:
            reference_gap("NODE", node_id, "pump_definition")
        if node.node_type is DrainNodeType.OUTFALL and node.outfall_definition is None:
            reference_gap("NODE", node_id, "outfall_definition")
    for edge in sorted(package.edges, key=lambda item: item.drain_edge_id):
        parameters = edge.parameters
        for name in ("length", "slope", "roughness", "effective_capacity"):
            scalar_gap("EDGE", edge.drain_edge_id, name, getattr(parameters, name))
        if parameters.cross_section is CrossSectionShape.UNKNOWN:
            reference_gap("EDGE", edge.drain_edge_id, "cross_section")
        elif parameters.cross_section is CrossSectionShape.CIRCULAR:
            scalar_gap("EDGE", edge.drain_edge_id, "diameter", parameters.diameter)
        else:
            scalar_gap("EDGE", edge.drain_edge_id, "width", parameters.width)
            scalar_gap("EDGE", edge.drain_edge_id, "height", parameters.height)
            if parameters.cross_section is CrossSectionShape.TRAPEZOIDAL:
                scalar_gap("EDGE", edge.drain_edge_id, "side_slope", parameters.side_slope)
        if parameters.condition is None:
            reference_gap("EDGE", edge.drain_edge_id, "condition")
    for exchange in sorted(package.exchanges, key=lambda item: item.exchange_id):
        for name in (
            "rim_elevation",
            "opening_area",
            "discharge_coefficient",
            "maximum_inlet_capacity",
        ):
            scalar_gap("EXCHANGE", exchange.exchange_id, name, getattr(exchange, name))

    bound_nodes = {item.drain_node_id for item in package.exchanges}
    return TopologyReport(
        node_count=len(nodes),
        edge_count=len(package.edges),
        exchange_count=len(package.exchanges),
        outfall_paths=paths,
        unreachable_node_ids=unreachable,
        unconnected_node_ids=sorted(set(nodes) - incident),
        missing_exchange_node_ids=sorted(
            node_id
            for node_id, node in nodes.items()
            if node.node_type in {DrainNodeType.INLET, DrainNodeType.MANHOLE}
            and node_id not in bound_nodes
        ),
        ward_transitions=transitions,
        parameter_gaps=gaps,
    )
