from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from apps.api.routers.terrain import get_terrain_service
from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.terrain.repository import TerrainRepository
from floodguard.terrain.service import TerrainService
from tests.terrain_fixtures import source_and_version


def test_terrain_readiness_products_and_qa_api() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    source, version, raw_object, payload = source_and_version()
    service = TerrainService(
        TerrainRepository(session),
        MemorySpatialObjectStore(raw_objects={raw_object.object_key: payload}),
        working_crs="EPSG:32645",
        max_object_bytes=1024 * 1024,
    )
    result = service.build_from_raw(source, version, raw_object)
    app.dependency_overrides[get_terrain_service] = lambda: service
    try:
        client = TestClient(app)
        readiness = client.get("/terrain/readiness?city_id=kolkata")
        assert readiness.status_code == 200
        assert readiness.json()["completion_gate_passed"] is True
        assert readiness.json()["best_readiness_status"] == "HYDRAULIC_SCENARIO_READY"

        products = client.get("/terrain/products?city_id=kolkata")
        assert products.status_code == 200
        assert products.json()[0]["terrain_id"] == str(result.terrain_id)
        assert products.json()[0]["validation_limitations"]

        detail = client.get(f"/terrain/products/{result.terrain_id}")
        assert detail.status_code == 200
        assert detail.json()["source_surface_type"] == "DSM"

        for path, content_type in (
            ("raw", "application/json"),
            ("visual", "application/json"),
            ("hydraulic", "application/json"),
            ("multi-level-structures", "application/json"),
            ("qa", "application/geo+json"),
            ("audit", "application/json"),
        ):
            response = client.get(f"/terrain/products/{result.terrain_id}/{path}")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith(content_type)

        viewer = client.get("/terrain/qa")
        assert viewer.status_code == 200
        assert "Terrain QA" in viewer.text

        audit = client.get(f"/terrain/products/{result.terrain_id}/audit").json()
        assert audit["vertical_validation"]["computed_evaluation"]["status"] == "NOT_ASSESSED"
        assert audit["vertical_validation"]["rmse_m"] is None
        audit_key = service.get(result.terrain_id).audit_object_key
        service.object_store.spatial_objects[audit_key] = b"bad"
        corrupted = client.get(f"/terrain/products/{result.terrain_id}/audit")
        assert corrupted.status_code == 409
        assert "integrity" in corrupted.json()["detail"]
        service.object_store.spatial_objects.pop(audit_key)
        assert client.get(f"/terrain/products/{result.terrain_id}/audit").status_code == 503
    finally:
        app.dependency_overrides.clear()
        session.close()
