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


def test_registry_http_api() -> None:
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
        readiness = client.get("/registry/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["catalogue_complete"] is True

        sources = client.get("/registry/sources", params={"city_id": "kolkata"})
        assert sources.status_code == 200
        assert len(sources.json()) >= 17

        source_id = sources.json()[0]["source_id"]
        detail = client.get(f"/registry/sources/{source_id}")
        assert detail.status_code == 200
        assert detail.json()["source_id"] == source_id
    finally:
        app.dependency_overrides.clear()
        session.close()
