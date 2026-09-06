import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from apps.api.routers.urban_gis import get_urban_gis_service
from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.urban_gis.reference import reference_package
from floodguard.urban_gis.repository import UrbanGisRepository
from floodguard.urban_gis.service import UrbanGisService


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    service = UrbanGisService(
        UrbanGisRepository(session),
        MemorySpatialObjectStore(),
        working_crs="EPSG:32645",
    )
    service.build(reference_package())
    app.dependency_overrides[get_urban_gis_service] = lambda: service
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_readiness_exposes_deferred_final_acceptance(client: TestClient) -> None:
    response = client.get("/urban-gis/readiness?city_id=kolkata")
    assert response.status_code == 200
    body = response.json()
    assert body["technical_development_gate_passed"] is True
    assert body["final_human_acceptance_pending"] is True
    assert body["final_completion_gate_passed"] is False


def test_visual_and_hydraulic_products_are_distinct(client: TestClient) -> None:
    products = client.get("/urban-gis/products?city_id=kolkata").json()
    urban_gis_id = products[0]["urban_gis_id"]
    visual = client.get(f"/urban-gis/products/{urban_gis_id}/visual")
    hydraulic = client.get(f"/urban-gis/products/{urban_gis_id}/hydraulic")
    assert visual.status_code == hydraulic.status_code == 200
    assert visual.json() != hydraulic.json()


def test_qa_viewer_and_roof_policy_are_reachable(client: TestClient) -> None:
    assert "Urban GIS QA" in client.get("/urban-gis/qa").text
    products = client.get("/urban-gis/products?city_id=kolkata").json()
    urban_gis_id = products[0]["urban_gis_id"]
    roof = client.get(f"/urban-gis/products/{urban_gis_id}/roof-runoff")
    assert roof.status_code == 200
    assert roof.json()["surface_cell_binding"] == "DEFERRED_TO_LATER_SEQUENCE"
