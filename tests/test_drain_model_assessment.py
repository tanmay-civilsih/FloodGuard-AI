import pytest

from floodguard.drainage.assessment import assess
from floodguard.drainage.contracts import (
    DrainEdgeType,
    DrainNodeType,
    EngineeringParameter,
    FlowDirectionMethod,
)
from floodguard.drainage.model_contracts import (
    DrainModelInput,
    HydraulicReadiness,
    PumpDefinition,
    StorageDefinition,
)
from floodguard.drainage.reference import reference_model
from floodguard.spatial.contracts import DatumTransformStatus


def test_connected_cross_ward_static_benchmark() -> None:
    model = reference_model()
    result = assess(model)
    assert {n.node_type for n in model.graph.nodes} == set(DrainNodeType)
    assert {e.edge_type for e in model.graph.edges} == set(DrainEdgeType)
    assert result.readiness_status is HydraulicReadiness.HYDRAULIC_SCENARIO_READY
    assert result.geometric_cross_ward_path
    assert not result.real_cross_ward_path_available
    assert not result.hydraulic_validation_claimed
    assert not result.scenario_blockers
    assert not result.topology.parameter_gaps
    inlet = next(p for p in result.topology.outfall_paths if p.from_node_id == "inlet")
    assert len(inlet.edge_ids) == 5 and inlet.outfall_node_id == "outfall"


@pytest.mark.parametrize("gap", ["roughness", "effective_capacity", "length", "slope", "diameter"])
def test_missing_parameters_allow_only_hydrologic_readiness(gap: str) -> None:
    model = reference_model()
    old = getattr(model.graph.edges[0].parameters, gap)
    setattr(
        model.graph.edges[0].parameters,
        gap,
        EngineeringParameter(
            unit=old.unit, status="MISSING", version="v1", missing_reason="No survey evidence"
        ),
    )
    result = assess(model)
    assert result.readiness_status is HydraulicReadiness.HYDROLOGIC_READY
    assert any(p.parameter == gap for p in result.topology.parameter_gaps)


@pytest.mark.parametrize("missing", ["pumps", "storages", "outfalls"])
def test_reference_to_definition_is_not_executable_definition(missing: str) -> None:
    model = reference_model()
    setattr(model.definitions, missing, [])
    result = assess(model)
    assert result.readiness_status is HydraulicReadiness.VISUAL_ONLY
    assert result.definition_errors


@pytest.mark.parametrize(
    "case",
    [
        "wrong_ward",
        "overlap",
        "gap",
        "false_receiver",
        "missing_exchange",
        "storage_volume",
        "disconnected",
    ],
)
def test_false_geometry_or_connectivity_cannot_be_ready(case: str) -> None:
    model = reference_model()
    if case == "wrong_ward":
        model.graph.nodes[0].ward_id = "reference-B"
    elif case in {"overlap", "gap"}:
        coords = model.wards.boundaries[1].geometry["coordinates"][0]
        for point in coords:
            if point[0] == 300025:
                point[0] += 1 if case == "gap" else -1
    elif case == "false_receiver":
        model.definitions.outfalls[0].receiving_geometry = model.wards.boundaries[0].geometry
    elif case == "missing_exchange":
        model.graph.exchanges = []
    elif case == "storage_volume":
        model.graph.nodes[3].storage_volume.value = 30
    elif case == "disconnected":
        model.graph.edges = model.graph.edges[1:]
    result = assess(model)
    assert result.readiness_status is HydraulicReadiness.VISUAL_ONLY
    assert result.scenario_blockers
    if case in {"wrong_ward", "overlap", "gap", "false_receiver"}:
        assert not result.geometric_cross_ward_path


def test_unknown_datum_and_low_rim_block_scenario_promotion() -> None:
    model = reference_model()
    model.graph.vertical_reference.datum_transform_status = DatumTransformStatus.UNRESOLVED
    for edge in model.graph.edges:
        for candidate in edge.direction_candidates:
            candidate.method = FlowDirectionMethod.HYDRAULIC_TOPOLOGICAL_INFERENCE
    assert assess(model).readiness_status is HydraulicReadiness.HYDROLOGIC_READY
    model = reference_model()
    model.graph.exchanges[0].rim_elevation.value = 1
    assert any("rim" in b for b in assess(model).scenario_blockers)


@pytest.mark.parametrize(
    "kind,change",
    [
        ("pump", "head"),
        ("pump", "capacity"),
        ("pump", "negative"),
        ("storage", "start"),
        ("storage", "area"),
        ("storage", "depth"),
    ],
)
def test_invalid_engineering_curves_rejected(kind: str, change: str) -> None:
    model = reference_model()
    if kind == "pump":
        data = model.definitions.pumps[0].model_dump()
        if change == "head":
            data["curve"][1]["head_m"] = 0
        elif change == "capacity":
            data["curve"][1]["discharge_m3_s"] = 2
        else:
            data["curve"][0]["head_m"] = -1
        with pytest.raises(ValueError):
            PumpDefinition.model_validate(data)
    else:
        data = model.definitions.storages[0].model_dump()
        if change == "start":
            data["curve"][0]["depth_m"] = 1
        elif change == "area":
            data["curve"][0]["area_m2"] = 0
        else:
            data["curve"][1]["depth_m"] = 0
        with pytest.raises(ValueError):
            StorageDefinition.model_validate(data)


def test_mixed_scope_or_wrong_crs_rejected() -> None:
    model = reference_model().model_dump(mode="json")
    model["wards"]["working_crs"] = "EPSG:32644"
    with pytest.raises(ValueError, match="CRS"):
        DrainModelInput.model_validate(model)
