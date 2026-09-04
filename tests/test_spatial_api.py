from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from apps.api.routers.spatial import get_spatial_service
from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.spatial.repository import SpatialRepository
from floodguard.spatial.service import SpatialService


def test_spatial_readiness_and_qa_viewer() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    service = SpatialService(
        SpatialRepository(session),
        MemorySpatialObjectStore(),
        working_crs="EPSG:32645",
        alignment_tolerance_m=0.05,
        rainfall_conservation_tolerance=1e-9,
        max_object_bytes=1024 * 1024,
    )
    app.dependency_overrides[get_spatial_service] = lambda: service
    try:
        client = TestClient(app)
        readiness = client.get("/spatial/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["working_crs"] == "EPSG:32645"
        assert readiness.json()["rainfall_conservation"]["passed"] is True

        viewer = client.get("/spatial/qa")
        assert viewer.status_code == 200
        assert "MapLibre" in viewer.text
        assert "/spatial/layers" in viewer.text
    finally:
        app.dependency_overrides.clear()
        session.close()
