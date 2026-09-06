import json
from uuid import uuid4

import pytest

from floodguard.drainage.importer import bind_graph, import_sources
from floodguard.drainage.serialization import canonical_bytes, decode_object, sha256
from tests.drain_model_fixtures import binding, sources


def test_import_preserves_uncertainty_and_raw_feature_lineage() -> None:
    info, raw, wards, model = sources()
    draft, ward_set = import_sources(info, raw, wards, max_bytes=100000)
    assert draft.readiness_status == "VISUAL_ONLY"
    assert not draft.direction_assigned and not draft.connections_inferred
    assert len(draft.features) == 12
    assert (
        next(f for f in draft.features if f.feature_kind == "DRAIN").source_properties[
            "dimension_m"
        ]
        is None
    )
    assert len(draft.unresolved_items) >= 4
    plan = binding(model, uuid4(), "a" * 64)
    assert bind_graph(draft, ward_set, plan).graph == model.graph


@pytest.mark.parametrize(
    "case",
    [
        "hash",
        "size",
        "crs",
        "lineage",
        "duplicate",
        "kind",
        "ward_id",
        "duplicate_ward",
        "empty",
        "missing_geometry",
    ],
)
def test_import_fails_closed(case: str) -> None:
    info, raw, wards, _ = sources()
    data = json.loads(raw)
    ward_doc = json.loads(wards)
    limit = 100000
    if case == "hash":
        raw += b" "
    elif case == "size":
        limit = 1
    elif case == "crs":
        data["crs"]["properties"]["name"] = "EPSG:4326"
    elif case == "lineage":
        data["features"][0]["properties"]["reconstruction_id"] = str(uuid4())
    elif case == "duplicate":
        data["features"].append(data["features"][0])
    elif case == "kind":
        data["features"][0]["properties"]["feature_kind"] = "LABEL"
    elif case == "ward_id":
        ward_doc["features"][0]["properties"]["WARD"] = None
    elif case == "duplicate_ward":
        ward_doc["features"].append(ward_doc["features"][0])
    elif case == "empty":
        data["features"] = []
    elif case == "missing_geometry":
        data["features"][0]["geometry"] = None
    if case not in {"hash", "size"}:
        raw, wards = canonical_bytes(data), canonical_bytes(ward_doc)
        info.reconstruction_source.sha256 = sha256(raw)
        info.ward_source.sha256 = sha256(wards)
    with pytest.raises((ValueError, TypeError)):
        import_sources(info, raw, wards, max_bytes=limit)


@pytest.mark.parametrize(
    "case",
    [
        "node_missing",
        "edge_missing",
        "label_node",
        "city",
        "source",
        "moved_node",
        "line_gap",
        "unknown_edge_source",
    ],
)
def test_binding_cannot_invent_source_geometry(case: str) -> None:
    info, raw, wards, model = sources()
    draft, ward_set = import_sources(info, raw, wards, max_bytes=100000)
    plan = binding(model, uuid4(), "a" * 64)
    if case == "node_missing":
        plan.node_bindings.pop()
    elif case == "edge_missing":
        plan.edge_bindings.pop()
    elif case == "label_node":
        plan.node_bindings[0].source_feature_id = "label"
    elif case == "city":
        plan.graph.city_id = "other"
    elif case == "source":
        plan.graph.source_references.remove(info.reconstruction_source)
    elif case == "moved_node":
        # Change the retained draft fixture so the graph's otherwise valid endpoint is unbound.
        draft.features[5].geometry = {"type": "Point", "coordinates": [300001, 2500000]}
    elif case == "line_gap":
        draft.features[0].geometry = {
            "type": "LineString",
            "coordinates": [[300000, 2500000], [300001, 2500000]],
        }
    else:
        plan.edge_bindings[0].source_feature_ids = ["unknown"]
    with pytest.raises(ValueError):
        bind_graph(draft, ward_set, plan)


@pytest.mark.parametrize("payload", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b"[]"])
def test_ambiguous_json_cannot_change_content_identity(payload: bytes) -> None:
    with pytest.raises(ValueError):
        decode_object(payload, 1000)
