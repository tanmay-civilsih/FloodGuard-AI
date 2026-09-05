from uuid import UUID

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    UUID(response.headers["X-Correlation-ID"])


def test_correlation_id_is_preserved() -> None:
    correlation_id = "8d30c6c7-0d83-4d2e-8b27-8f4f6951ce20"
    response = client.get("/version", headers={"X-Correlation-ID": correlation_id})
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == correlation_id


def test_invalid_correlation_id_is_rejected() -> None:
    response = client.get("/health", headers={"X-Correlation-ID": "not-a-uuid"})
    assert response.status_code == 400


def test_version_endpoint() -> None:
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["sequence"] == 5
    assert response.json()["version"] == "0.5.0"
