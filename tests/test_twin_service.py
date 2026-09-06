import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers.twin import get_twin_service
from floodguard.drainage.model_contracts import HydraulicReadiness
from floodguard.drainage.serialization import canonical_bytes
from floodguard.twin.contracts import ComponentRole as R
from floodguard.twin.reference import reference_snapshot
from floodguard.twin.service import TwinIntegrityError, manifest_identity
from floodguard.twin.snapshot import assemble_parameters
from tests.twin_fixtures import bound_fixture_snapshot, twin_service


@pytest.fixture
def service_setup():
    service, session, store = twin_service()
    try:
        yield service, store
    finally:
        session.close()


def test_twin_recreated_in_empty_database_without_live_sources(service_setup) -> None:
    service, store = service_setup
    created = service.build(reference_snapshot())
    manifest = service.read_artifact(created.twin_id, "manifest")
    assert created.hydraulic_readiness is HydraulicReadiness.HYDRAULIC_SCENARIO_READY
    assert not service.build(reference_snapshot()).created
    fresh, session, _ = twin_service(store)
    try:
        fresh.software_version = "future-reader"
        fresh.software_source_sha256 = "f" * 64
        restored = fresh.recreate(manifest)
        assert restored.created and restored.twin_id == created.twin_id
        assert fresh.read_artifact(restored.twin_id, "manifest") == manifest
        for role in R:
            assert fresh.read_artifact(restored.twin_id, role.value) == service.read_artifact(
                created.twin_id, role.value
            )
    finally:
        session.close()
    state = service.readiness("kolkata")
    assert state.reference_scenario_ready == 1
    assert state.real_cross_ward_twins == 0
    assert not state.technical_development_gate_passed
    assert not state.final_completion_gate_passed


@pytest.mark.parametrize("role", list(R))
@pytest.mark.parametrize("failure", ["corrupt", "missing"])
def test_bad_frozen_component_blocks_all_reads_and_recreation(service_setup, role, failure) -> None:
    service, store = service_setup
    result = service.build(reference_snapshot())
    manifest_bytes = service.read_artifact(result.twin_id, "manifest")
    manifest = json.loads(manifest_bytes)
    key = manifest[role.value]["artifact"]["object_key"]
    if failure == "corrupt":
        store.spatial_objects[key] += b" "
    else:
        del store.spatial_objects[key]
    assert service.readiness("kolkata").verified_twins == 0
    with pytest.raises((TwinIntegrityError, FileNotFoundError)):
        service.recreate(manifest_bytes)
    with pytest.raises((TwinIntegrityError, FileNotFoundError)):
        service.read_artifact(result.twin_id, "manifest")


@pytest.mark.parametrize(
    "part", ["manifest", "audit", "terrain-metadata", "drain-input", "drain-parameters"]
)
def test_metadata_evidence_corruption_cannot_be_reused(service_setup, part) -> None:
    service, store = service_setup
    result = service.build(reference_snapshot())
    record = service.get(result.twin_id)
    manifest = service.verify(record)
    reference = (
        getattr(record, part)
        if part in {"manifest", "audit"}
        else manifest.evidence_artifacts[part]
    )
    store.spatial_objects[reference.object_key] += b"bad"
    with pytest.raises(TwinIntegrityError):
        service.read_artifact(result.twin_id, "manifest")
    assert service.readiness("kolkata").verified_twins == 0


@pytest.mark.parametrize("change", ["software", "surface_parameters", "missing_reason", "pilot"])
def test_input_changes_create_new_versions_without_overwrite(service_setup, change) -> None:
    service, _ = service_setup
    first = service.build(reference_snapshot())
    snapshot = reference_snapshot()
    if change == "software":
        service.software_source_sha256 = "b" * 64
    elif change == "surface_parameters":
        surface = json.loads(snapshot.components[R.HYDRAULIC_SURFACE])
        surface["features"][0]["properties"]["hydrology"]["runoff_coefficient"] = 0.8
        snapshot.add(
            R.HYDRAULIC_SURFACE, canonical_bytes(surface), snapshot.sources[R.HYDRAULIC_SURFACE]
        )
        assemble_parameters(snapshot)
    elif change == "missing_reason":
        del snapshot.components[R.VISUAL_CITY], snapshot.sources[R.VISUAL_CITY]
        snapshot.missing[R.VISUAL_CITY] = "Explicitly absent reference display geometry."
    else:
        snapshot.pilot_area.geometry["coordinates"][0][1][0] -= 1
        snapshot.pilot_area.geometry["coordinates"][0][2][0] -= 1
    second = service.build(snapshot)
    assert second.twin_id != first.twin_id
    service.verify(service.get(first.twin_id))


@pytest.mark.parametrize(
    "field,value",
    [
        ("city_id", "other"),
        ("twin_id", str(UUID(int=0))),
        ("software_version", "fake"),
        ("real_cross_ward_path_available", True),
    ],
)
def test_manifest_edits_cannot_retain_old_identity(service_setup, field, value) -> None:
    service, _ = service_setup
    result = service.build(reference_snapshot())
    data = json.loads(service.read_artifact(result.twin_id, "manifest"))
    data[field] = value
    with pytest.raises(ValueError):
        service.recreate(canonical_bytes(data))


def test_readiness_is_recomputed_even_for_a_rehashed_manifest(service_setup) -> None:
    service, _ = service_setup
    result = service.build(reference_snapshot())
    data = json.loads(service.read_artifact(result.twin_id, "manifest"))
    data["hydraulic_readiness"] = "VISUAL_ONLY"
    data["twin_id"] = str(manifest_identity(data)[0])
    with pytest.raises(TwinIntegrityError, match="readiness"):
        service.recreate(canonical_bytes(data))


def test_bound_real_path_is_required_for_technical_freeze_but_never_final_acceptance(service_setup):
    # Isolated synthetic source doubles exercise the positive gate; no deployment of this fixture.
    service, _ = service_setup
    service.build(reference_snapshot())
    built = service.build(bound_fixture_snapshot())
    state = service.readiness("kolkata")
    assert state.real_cross_ward_twins == 1
    assert state.technical_development_gate_passed
    assert not state.final_completion_gate_passed
    assert service.verify(service.get(built.twin_id)).hydraulic_validation_claimed is False


def test_api_reads_and_failure_statuses(service_setup) -> None:
    service, store = service_setup
    result = service.build(reference_snapshot())
    app.dependency_overrides[get_twin_service] = lambda: service
    try:
        client = TestClient(app)
        assert "Twin Manifest QA" in client.get("/twins/qa").text
        assert client.get("/twins/readiness").json()["reference_scenario_ready"] == 1
        assert len(client.get("/twins/products").json()) == 1
        for role in R:
            assert client.get(f"/twins/products/{result.twin_id}/{role.value}").status_code == 200
        assert client.get(f"/twins/products/{result.twin_id}/unknown").status_code == 404
        assert client.get("/twins/products/invalid").status_code == 422
        record = service.get(result.twin_id)
        store.spatial_objects[record.audit.object_key] += b"corrupt"
        assert client.get(f"/twins/products/{result.twin_id}/manifest").status_code == 409
        del store.spatial_objects[record.audit.object_key]
        assert client.get(f"/twins/products/{result.twin_id}/manifest").status_code == 503
        paths = client.get("/openapi.json").json()["paths"]
        assert all(
            set(methods) == {"get"} for path, methods in paths.items() if path.startswith("/twins/")
        )
    finally:
        app.dependency_overrides.pop(get_twin_service)
