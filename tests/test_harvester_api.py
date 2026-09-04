from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from floodguard.registry.database import get_db_session
from floodguard.registry.models import Base
from floodguard.registry.repository import RegistryRepository
from floodguard.registry.seed import kolkata_seed_sources


def test_harvester_readiness_api() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    RegistryRepository(session).seed_if_missing(kolkata_seed_sources())

    def override_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        client = TestClient(app)
        response = client.get("/harvester/readiness", params={"city_id": "kolkata"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["automation_permitted_sources"] >= 1
        assert payload["harvested_sources"] == 0
        assert payload["complete_versions"] == 0
        assert payload["raw_bucket"] == "floodguard-raw"
    finally:
        app.dependency_overrides.clear()
        session.close()
