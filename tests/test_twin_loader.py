"""Failure injection at the actual source-selection boundary using explicit source doubles."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.twin.bootstrap import pilot_request
from floodguard.twin.contracts import ComponentRole as R
from floodguard.twin.loader import TwinSourceLoader
from floodguard.twin.reference import reference_snapshot


class Record(SimpleNamespace):
    def model_dump(self, **kwargs):
        return {key: str(value) for key, value in vars(self).items()}


def loader_fixture():
    request = pilot_request()
    request.terrain_id = None
    request.drain_product_id = None
    request.missing_reasons.update(terrain="No selected terrain", drainage="No selected drainage")
    reference = reference_snapshot()
    request.pilot_area = reference.pilot_area
    records = {}
    store = MemorySpatialObjectStore()
    for identity, role, category in [
        (request.ward_id, R.WARD, "WARD_BOUNDARY"),
        (request.catchment_id, R.CATCHMENT, "CATCHMENT"),
        (request.waterbody_id, R.WATERBODY, "WATER_BODY"),
    ]:
        raw = reference.components[role]
        key = str(identity)
        store.spatial_objects[key] = raw
        records[identity] = Record(
            city_id="kolkata",
            working_crs="EPSG:32645",
            source_category=category,
            normalized_object_key=key,
            normalized_sha256=sha256(raw),
            normalization_id=identity,
        )
    spatial = SimpleNamespace(
        get_layer=records.__getitem__, object_store=store, qa_geojson=lambda identity: b"{}"
    )
    loader = TwinSourceLoader(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        spatial,
        max_bytes=128 * 1024 * 1024,
    )
    return request, loader, records, store


def test_explicit_missing_real_components_do_not_use_reference_products() -> None:
    request, loader, _, _ = loader_fixture()
    snapshot = loader.load(request)
    assert set(snapshot.components) == {R.WARD, R.CATCHMENT, R.WATERBODY}
    assert len(snapshot.missing) == 9
    assert snapshot.evidence_scope.value == "REAL_PILOT_PROVISIONAL"


@pytest.mark.parametrize("case", ["city", "crs", "category", "hash", "historical", "unknown"])
def test_explicit_spatial_version_checks_fail_closed(case) -> None:
    request, loader, records, store = loader_fixture()
    record = records[request.ward_id]
    if case == "city":
        record.city_id = "other"
    elif case == "crs":
        record.working_crs = "EPSG:4326"
    elif case == "category":
        record.source_category = "CATCHMENT"
    elif case == "hash":
        store.spatial_objects[record.normalized_object_key] += b"changed"
    elif case == "historical":

        def reject(identity):
            raise ValueError("old pipeline cannot be reused")

        loader.spatial.qa_geojson = reject
    else:
        request.ward_id = uuid4()
    with pytest.raises((ValueError, LookupError)):
        loader.load(request)


def test_drain_draft_is_retained_as_evidence_without_becoming_graph() -> None:
    request, loader, _, _ = loader_fixture()
    request.drain_product_id = uuid4()
    del request.missing_reasons["drainage"]
    record = Record(
        city_id=request.city_id,
        pilot_area_id=request.pilot_area.pilot_area_id,
        working_crs=request.horizontal_crs,
        product_id=request.drain_product_id,
        pipeline_version="sequence-8-drain-model-v1",
        product_kind="IMPORT_DRAFT",
        artifacts={"draft": {}},
    )
    loader.drains = SimpleNamespace(
        get=lambda identity: record,
        verify=lambda record: None,
        read_artifact=lambda identity, name: canonical_bytes(
            {"features": [], "readiness_status": "VISUAL_ONLY"}
        ),
    )
    snapshot = loader.load(request)
    assert R.DRAIN_GRAPH not in snapshot.components
    assert "drain-draft" in snapshot.evidence


@pytest.mark.parametrize("case", ["reference", "pilot", "pipeline"])
def test_selected_urban_source_must_match_real_pilot_and_pipeline(case) -> None:
    request, loader, _, _ = loader_fixture()
    request.urban_gis_id = uuid4()
    del request.missing_reasons["urban_gis"]
    record = Record(
        city_id=request.city_id,
        pilot_area_id=request.pilot_area.pilot_area_id,
        working_crs=request.horizontal_crs,
        pipeline_version="sequence-7-urban-gis-v1",
    )
    if case == "reference":
        record.evidence_scope = SimpleNamespace(value="REFERENCE_FIXTURE")
    elif case == "pilot":
        record.pilot_area_id = "other"
    else:
        record.pipeline_version = "old"
    loader.urban = SimpleNamespace(get=lambda identity: record)
    with pytest.raises(ValueError):
        loader.load(request)
