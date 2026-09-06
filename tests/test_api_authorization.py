"""Application wiring: unauthorized mutations stop before touching domain services."""

import pytest
from fastapi.testclient import TestClient

from apps.api import main


def test_live_app_write_guard_and_public_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOODGUARD_OPERATORS_JSON", "")
    client = TestClient(main.app)
    assert client.get("/health").status_code == 200
    assert client.post("/terrain/acquisitions", json={}).status_code == 503


def test_live_readiness_returns_503_on_dependency_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "platform_readiness", lambda: {"database_and_schema": False})
    response = TestClient(main.app).get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_live_readiness_requires_all_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "platform_readiness", lambda: {
        "database_and_schema": True, "object_store": True,
    })
    response = TestClient(main.app).get("/ready")
    assert response.status_code == 200
    assert all(response.json()["dependencies"].values())
