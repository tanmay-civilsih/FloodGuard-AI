import pytest
from pydantic import ValidationError

from floodguard.drainage.contracts import DrainGraphPackage, DrainNodeType
from floodguard.drainage.topology import inspect_topology
from tests.drainage_fixtures import edge, graph, node


def test_connected_graph_reports_paths_and_honest_ward_scope() -> None:
    report = inspect_topology(graph())
    paths = {path.from_node_id: path for path in report.outfall_paths}
    assert paths["inlet"].node_ids == ["inlet", "manhole", "outfall"]
    assert paths["inlet"].edge_ids == ["pipe-a", "pipe-b"]
    assert report.unreachable_node_ids == []
    assert report.missing_exchange_node_ids == []
    assert report.ward_transitions[0].drain_edge_id == "pipe-b"
    assert report.cross_ward_connectivity_scope == "DECLARED_WARD_IDS_ONLY"
    assert report.genuine_cross_ward_continuation_verified is False
    assert report.hydraulic_validation_claimed is False
    assert any(gap.parameter == "outfall_definition" for gap in report.parameter_gaps)
    assert any(gap.parameter == "maximum_inlet_capacity" for gap in report.parameter_gaps)


def test_dead_end_and_isolated_nodes_are_visible() -> None:
    package = graph()
    dead_end = node("dead-end", DrainNodeType.JUNCTION, 300_015.0)
    isolated = node("isolated", DrainNodeType.STORAGE, 300_030.0)
    package.nodes.extend([dead_end, isolated])
    package.edges.append(edge("dead-branch", package.nodes[1], dead_end))
    report = inspect_topology(package)
    assert report.unreachable_node_ids == ["dead-end", "isolated"]
    assert report.unconnected_node_ids == ["isolated"]
    assert any(
        gap.entity_id == "isolated" and gap.parameter == "storage_volume"
        for gap in report.parameter_gaps
    )


def test_cycle_can_reach_outfall_without_infinite_traversal() -> None:
    package = graph()
    package.edges.append(edge("return-pipe", package.nodes[1], package.nodes[0]))
    report = inspect_topology(package)
    assert report.unreachable_node_ids == []
    assert next(path for path in report.outfall_paths if path.from_node_id == "inlet").edge_ids == (
        ["pipe-a", "pipe-b"]
    )


def test_no_outfall_means_no_downstream_path_claim() -> None:
    data = graph().model_dump(mode="json")
    data["nodes"][2]["node_type"] = "JUNCTION"
    report = inspect_topology(DrainGraphPackage.model_validate(data))
    assert report.outfall_paths == []
    assert report.unreachable_node_ids == ["inlet", "manhole", "outfall"]


def test_missing_exchange_coverage_is_reported() -> None:
    package = graph()
    package.exchanges.clear()
    assert inspect_topology(package).missing_exchange_node_ids == ["inlet", "manhole"]


def test_input_order_does_not_change_diagnostics() -> None:
    package = graph()
    expected = inspect_topology(package)
    package.nodes.reverse()
    package.edges.reverse()
    package.exchanges.reverse()
    assert inspect_topology(package) == expected


def test_mutated_input_is_revalidated_before_reporting_paths() -> None:
    package = graph()
    package.edges[0].to_node_id = "absent"
    with pytest.raises(ValidationError):
        inspect_topology(package)


def test_minimum_hop_path_is_selected_without_claiming_hydraulic_optimality() -> None:
    package = graph()
    other_outfall = node("other-outfall", DrainNodeType.OUTFALL, 300_100.0)
    package.nodes.append(other_outfall)
    package.edges.append(edge("direct", package.nodes[0], other_outfall))
    report = inspect_topology(package)
    path = next(item for item in report.outfall_paths if item.from_node_id == "inlet")
    assert path.outfall_node_id == "other-outfall"
    assert path.edge_ids == ["direct"]
    assert report.hydraulic_validation_claimed is False
