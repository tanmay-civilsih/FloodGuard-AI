import json

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers.drainage import get_drain_service
from floodguard.drainage.contracts import DrainEvidenceScope
from floodguard.drainage.reference import reference_model
from floodguard.drainage.service import DrainIntegrityError
from tests.drain_model_fixtures import binding, service_fixture, sources


@pytest.fixture
def setup_service():
    service, session, store = service_fixture()
    try:
        yield service, store
    finally:
        session.close()


def test_immutable_products_reuse_with_full_artifact_readback(setup_service) -> None:
    service, _ = setup_service
    created = service.build_reference(reference_model())
    reused = service.build_reference(reference_model())
    assert created.created and not reused.created
    assert reused.product_id == created.product_id
    product = service.get(created.product_id)
    service.verify(product)
    assert len(product.artifacts) == 8
    assert product.created_at.utcoffset().total_seconds() == 0
    assert (
        json.loads(service.read_artifact(created.product_id, "exchanges"))["surface_cell_binding"]
        == "DEFERRED_TO_SEQUENCE_11"
    )
    assert service.readiness("kolkata").reference_ready == 1
    assert not service.readiness("kolkata").technical_development_gate_passed
    assert not service.readiness("kolkata").final_completion_gate_passed


@pytest.mark.parametrize(
    "artifact", ["graph", "parameters", "exchanges", "assessment", "wards", "qa", "input", "audit"]
)
@pytest.mark.parametrize("failure", ["corrupt", "missing"])
def test_every_bad_artifact_blocks_readiness_reuse_and_api(
    setup_service, artifact, failure
) -> None:
    service, store = setup_service
    built = service.build_reference(reference_model())
    record = service.get(built.product_id)
    key = record.artifacts[artifact].object_key
    if failure == "corrupt":
        store.spatial_objects[key] += b" "
    else:
        del store.spatial_objects[key]
    assert service.readiness("kolkata").eligible_products == 0
    with pytest.raises((DrainIntegrityError, FileNotFoundError)):
        service.build_reference(reference_model())
    app.dependency_overrides[get_drain_service] = lambda: service
    try:
        response = TestClient(app).get(f"/drainage/products/{built.product_id}/graph")
        assert response.status_code == (409 if failure == "corrupt" else 503)
    finally:
        app.dependency_overrides.pop(get_drain_service)


@pytest.mark.parametrize(
    "artifact", ["draft", "source-reconstruction", "source-wards", "wards", "qa", "input", "audit"]
)
def test_draft_source_corruption_blocks_binding(setup_service, artifact) -> None:
    service, store = setup_service
    info, raw, wards, model = sources()
    created = service.import_draft(info, raw, wards)
    record = service.get(created.product_id)
    store.spatial_objects[record.artifacts[artifact].object_key] += b" "
    with pytest.raises(DrainIntegrityError):
        service.build_bound(binding(model, record.product_id, record.fingerprint))
    assert service.readiness("kolkata").eligible_products == 0


def test_bound_build_preserves_exact_source_bytes_and_coverage(setup_service) -> None:
    service, _ = setup_service
    info, raw, wards, model = sources()
    draft = service.import_draft(info, raw, wards)
    assert not service.import_draft(info, raw, wards).created
    record = service.get(draft.product_id)
    plan = binding(model, record.product_id, record.fingerprint)
    built = service.build_bound(plan)
    assert not service.build_bound(plan).created
    assert service.read_artifact(built.product_id, "source-reconstruction") == raw
    assert service.read_artifact(built.product_id, "source-wards") == wards
    coverage = json.loads(service.read_artifact(built.product_id, "binding-coverage"))
    assert coverage["unbound_drain_ids"] == []
    plan.draft_fingerprint = "0" * 64
    with pytest.raises(ValueError, match="exact import"):
        service.build_bound(plan)


def test_provisional_scope_cannot_bypass_import_binding(setup_service) -> None:
    service, _ = setup_service
    model = reference_model()
    model.graph.evidence_scope = DrainEvidenceScope.REAL_PILOT_PROVISIONAL
    model.wards.evidence_scope = DrainEvidenceScope.REAL_PILOT_PROVISIONAL
    with pytest.raises(ValueError, match="binding"):
        service.build_reference(model)


def test_version_crs_and_manifest_cannot_be_relabelled(setup_service) -> None:
    service, _ = setup_service
    built = service.build_reference(reference_model())
    record = service.repository.get(built.product_id)
    record.city_id = "other"
    service.repository.session.commit()
    with pytest.raises(DrainIntegrityError):
        service.verify(service.get(built.product_id))
    assert service.readiness("other").eligible_products == 0


def test_new_parameter_creates_new_product_without_overwrite(setup_service) -> None:
    service, _ = setup_service
    original = service.build_reference(reference_model())
    model = reference_model()
    model.graph.edges[0].parameters.roughness.value = 0.02
    changed = service.build_reference(model)
    assert original.product_id != changed.product_id
    service.verify(service.get(original.product_id))
    service.verify(service.get(changed.product_id))


def test_read_api_supports_all_artifacts_and_has_no_write_routes(setup_service) -> None:
    service, _ = setup_service
    built = service.build_reference(reference_model())
    app.dependency_overrides[get_drain_service] = lambda: service
    try:
        client = TestClient(app)
        assert client.get("/drainage/qa").status_code == 200
        assert "Drain Model QA" in client.get("/drainage/qa").text
        assert client.get("/drainage/readiness").json()["reference_ready"] == 1
        assert len(client.get("/drainage/products").json()) == 1
        for name in service.get(built.product_id).artifacts:
            assert client.get(f"/drainage/products/{built.product_id}/{name}").status_code == 200
        assert client.get(f"/drainage/products/{built.product_id}/unknown").status_code == 404
        assert client.get("/drainage/products/invalid").status_code == 422
        routes = client.get("/openapi.json").json()["paths"]
        assert all(
            set(methods) == {"get"}
            for path, methods in routes.items()
            if path.startswith("/drainage/")
        )
    finally:
        app.dependency_overrides.pop(get_drain_service)
