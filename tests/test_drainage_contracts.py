import pytest
from pydantic import ValidationError

from floodguard.drainage.contracts import (
    DrainGraphPackage,
    EngineeringParameter,
    FlowDirectionCandidate,
    FlowDirectionMethod,
    ParameterUnit,
    select_flow_direction,
)
from tests.drainage_fixtures import assumed, graph


def test_missing_parameters_are_explicit_and_roundtrip() -> None:
    package = graph()
    assert DrainGraphPackage.model_validate_json(package.model_dump_json()) == package
    assert package.nodes[0].invert_elevation.value is None
    assert package.nodes[0].invert_elevation.status.value == "MISSING"
    assert package.nodes[0].invert_elevation.missing_reason
    assert package.edges[0].hydraulic_domain == "NETWORK_1D"


@pytest.mark.parametrize(
    "field,value",
    [
        ("value", True),
        ("value", float("nan")),
        ("value", float("inf")),
        ("method", None),
        ("source_reference", None),
        ("lower_bound", 2.0),
        ("upper_bound", 0.5),
        ("missing_reason", "Conflicting missing assertion"),
    ],
)
def test_invalid_parameter_evidence_is_rejected(field: str, value: object) -> None:
    data = assumed(1.0, ParameterUnit.METRE).model_dump(mode="json")
    data[field] = value
    with pytest.raises(ValidationError):
        EngineeringParameter.model_validate(data)


@pytest.mark.parametrize("value,reason", [(0.0, "Not supplied"), (None, None)])
def test_missing_status_cannot_hide_a_value_or_omit_reason(
    value: float | None,
    reason: str | None,
) -> None:
    data = graph().nodes[0].invert_elevation.model_dump(mode="json")
    data.update(value=value, missing_reason=reason)
    with pytest.raises(ValidationError, match="MISSING"):
        EngineeringParameter.model_validate(data)


@pytest.mark.parametrize("location", ["node", "edge", "exchange", "package"])
def test_premature_surface_cell_ids_are_forbidden(location: str) -> None:
    data = graph().model_dump(mode="json")
    target = data if location == "package" else data[location + "s"][0]
    target["surface_cell_ids"] = [1]
    with pytest.raises(ValidationError, match="Extra inputs"):
        DrainGraphPackage.model_validate(data)


@pytest.mark.parametrize(
    "collection,id_field",
    [
        ("nodes", "drain_node_id"),
        ("edges", "drain_edge_id"),
        ("exchanges", "exchange_id"),
    ],
)
def test_duplicate_ids_fail(collection: str, id_field: str) -> None:
    data = graph().model_dump(mode="json")
    data[collection][1][id_field] = data[collection][0][id_field]
    with pytest.raises(ValidationError):
        DrainGraphPackage.model_validate(data)


@pytest.mark.parametrize(
    "defect",
    [
        "unknown-node",
        "unknown-exchange-node",
        "edge-endpoint",
        "exchange-xy",
        "exchange-point",
        "exchange-node-type",
        "geographic-crs",
        "wrong-unit",
        "surface-owner",
        "negative-capacity",
        "zero-diameter",
        "z-coordinate",
    ],
)
def test_geometry_reference_unit_and_ownership_guards(defect: str) -> None:
    data = graph().model_dump(mode="json")
    if defect == "unknown-node":
        data["nodes"] = data["nodes"][1:]
    elif defect == "unknown-exchange-node":
        data["exchanges"][0]["drain_node_id"] = "absent"
    elif defect == "edge-endpoint":
        data["edges"][0]["geometry"]["coordinates"][0][0] += 2
    elif defect == "exchange-xy":
        data["exchanges"][0]["x"] += 1
    elif defect == "exchange-point":
        data["exchanges"][0]["x"] += 1
        data["exchanges"][0]["geometry"]["coordinates"][0] += 1
    elif defect == "exchange-node-type":
        data["exchanges"][0]["exchange_type"] = "MANHOLE_SURCHARGE"
    elif defect == "geographic-crs":
        data["working_crs"] = "EPSG:4326"
    elif defect == "wrong-unit":
        data["nodes"][0]["invert_elevation"]["unit"] = "m3"
    elif defect == "surface-owner":
        data["edges"][0]["hydraulic_domain"] = "SURFACE_2D"
    elif defect == "negative-capacity":
        data["edges"][0]["parameters"]["effective_capacity"] = assumed(
            -1,
            ParameterUnit.DISCHARGE,
        ).model_dump(mode="json")
    elif defect == "zero-diameter":
        data["edges"][0]["parameters"]["diameter"] = assumed(
            0,
            ParameterUnit.METRE,
        ).model_dump(mode="json")
    else:
        data["nodes"][0]["geometry"]["coordinates"].append(1.0)
    with pytest.raises(ValidationError):
        DrainGraphPackage.model_validate(data)


def test_strongest_direction_priority_wins_and_conflicts_fail() -> None:
    strongest = graph().edges[0].direction_candidates[0]
    data = strongest.model_dump(mode="json")
    data.update(from_node_id="manhole", to_node_id="inlet", confidence="LOW")
    for method in list(FlowDirectionMethod)[1:]:
        data["method"] = method
        weaker = FlowDirectionCandidate.model_validate(data)
        assert select_flow_direction([weaker, strongest]) == strongest
    data["method"] = FlowDirectionMethod.MUNICIPAL_ARROWS_LABELS
    with pytest.raises(ValueError, match="conflicts"):
        select_flow_direction([strongest, FlowDirectionCandidate.model_validate(data)])


def test_surface_terrain_direction_cannot_claim_high_confidence() -> None:
    data = graph().edges[0].direction_candidates[0].model_dump(mode="json")
    data["method"] = "SURFACE_TERRAIN_FALLBACK"
    with pytest.raises(ValidationError, match="LOW-confidence"):
        FlowDirectionCandidate.model_validate(data)


@pytest.mark.parametrize("defect", ["datum", "missing-invert", "reversed-invert", "none"])
def test_invert_direction_requires_comparable_descending_values(defect: str) -> None:
    data = graph().model_dump(mode="json")
    data["edges"][0]["direction_candidates"][0]["method"] = "INVERT_ELEVATIONS"
    if defect != "datum":
        data["vertical_reference"].update(
            datum_transform_status="COMPATIBLE",
            vertical_unit="m",
            vertical_datum="REFERENCE_DATUM_ONLY",
        )
    if defect != "missing-invert":
        for node, elevation in zip(data["nodes"], [2.0, 1.0, 0.0], strict=True):
            node["invert_elevation"] = assumed(elevation, ParameterUnit.METRE).model_dump(
                mode="json"
            )
    if defect == "reversed-invert":
        data["nodes"][0]["invert_elevation"]["value"] = 0
    if defect == "none":
        assert DrainGraphPackage.model_validate(data)
    else:
        with pytest.raises(ValidationError, match="invert"):
            DrainGraphPackage.model_validate(data)


@pytest.mark.parametrize("defect", ["offset", "vertical-unit", "source-collision", "limitations"])
def test_invalid_package_metadata_is_rejected(defect: str) -> None:
    data = graph().model_dump(mode="json")
    if defect == "offset":
        data["vertical_reference"]["vertical_offset_m"] = float("nan")
    elif defect == "vertical-unit":
        data["vertical_reference"]["vertical_unit"] = "ft"
    elif defect == "source-collision":
        duplicate = dict(data["source_references"][0])
        duplicate["sha256"] = "b" * 64
        data["source_references"].append(duplicate)
    else:
        data["limitations"] = [""]
    with pytest.raises(ValidationError):
        DrainGraphPackage.model_validate(data)
