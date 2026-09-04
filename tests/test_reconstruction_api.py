from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from apps.api.routers.reconstruction import get_reconstruction_service
from floodguard.reconstruction.repository import ReconstructionRepository
from floodguard.reconstruction.service import ReconstructionService
from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from tests.reconstruction_fixtures import source_and_version, synthetic_pdf


def test_reconstruction_readiness_geojson_qa_and_review_api() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    payload = synthetic_pdf()
    source, version, raw_object, calibration = source_and_version(payload)
    store = MemorySpatialObjectStore(raw_objects={raw_object.object_key: payload})
    service = ReconstructionService(
        ReconstructionRepository(session),
        store,
        working_crs="EPSG:32645",
        max_object_bytes=1024 * 1024,
    )
    result = service.reconstruct(source, version, raw_object, calibration)
    app.dependency_overrides[get_reconstruction_service] = lambda: service
    try:
        client = TestClient(app)
        readiness = client.get("/reconstruction/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["completion_gate_passed"] is False

        maps = client.get("/reconstruction/maps?city_id=kolkata")
        assert maps.status_code == 200
        assert maps.json()[0]["reconstruction_id"] == str(result.reconstruction_id)

        geojson = client.get(
            f"/reconstruction/maps/{result.reconstruction_id}/geojson"
        )
        assert geojson.status_code == 200
        assert geojson.headers["content-type"].startswith("application/geo+json")

        qa = client.get("/reconstruction/qa")
        assert qa.status_code == 200
        assert "Drainage Reconstruction QA" in qa.text

        rejected = client.post(
            f"/reconstruction/maps/{result.reconstruction_id}/reviews",
            json={
                "decision": "APPROVE",
                "reviewer": "Automated API test",
                "reviewer_type": "AUTOMATED",
                "notes": "An automated actor must not approve.",
                "source_alignment_checked": True,
                "drain_symbology_checked": True,
                "feature_placement_checked": True,
                "missing_attributes_not_invented": True,
            },
        )
        assert rejected.status_code == 409
    finally:
        app.dependency_overrides.clear()
        session.close()
