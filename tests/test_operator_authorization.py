"""Real ASGI request tests for the fail-closed global write guard."""

import hashlib
import json

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from floodguard.common.auth import require_write_access
from floodguard.common.auth_viewer import with_operator_credentials

TOKEN = "test-only-token-not-a-deployment-secret-0123456789"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("FLOODGUARD_OPERATORS_JSON", json.dumps({
        "reviewer-one": {"token_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
                         "roles": ["reviewer"]},
        "operator-two": {"token_sha256": hashlib.sha256((TOKEN + "-2").encode()).hexdigest(),
                         "roles": ["operator"]},
    }))
    app = FastAPI(dependencies=[Depends(require_write_access)])

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/reconstruction/maps/example/reviews")
    @app.post("/terrain/acquisitions")
    def mutation(request: Request) -> dict[str, str]:
        return {"subject": request.state.operator.subject}

    return TestClient(app)


def test_read_only_qa_remains_available_without_credentials(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Use an explicit empty environment value so a developer's real .env cannot leak
    # into this negative test through pydantic-settings' env_file fallback.
    monkeypatch.setenv("FLOODGUARD_OPERATORS_JSON", "")
    assert client.get("/health").status_code == 200
    assert client.post("/terrain/acquisitions").status_code == 503


@pytest.mark.parametrize("header", ["", "Bearer wrong", "Basic ignored", "Bearer " + "x" * 40])
def test_unauthorized_writes_are_rejected(client: TestClient, header: str) -> None:
    response = client.post("/terrain/acquisitions", headers={"Authorization": header})
    assert response.status_code == 401


def test_review_identity_cannot_be_spoofed(client: TestClient) -> None:
    headers = {"Authorization": "Bearer " + TOKEN}
    url = "/reconstruction/maps/example/reviews"
    assert client.post(url, headers=headers, json={"reviewer": "someone-else"}).status_code == 403
    response = client.post(url, headers=headers, json={"reviewer": "reviewer-one"})
    assert response.status_code == 200
    assert response.json()["subject"] == "reviewer-one"


def test_roles_are_not_interchangeable(client: TestClient) -> None:
    assert client.post("/terrain/acquisitions", headers={
        "Authorization": "Bearer " + TOKEN,
    }).status_code == 403
    assert client.post("/terrain/acquisitions", headers={
        "Authorization": "Bearer " + TOKEN + "-2",
    }).status_code == 200
    assert client.post("/reconstruction/maps/example/reviews", headers={
        "Authorization": "Bearer " + TOKEN + "-2",
    }, json={"reviewer": "operator-two"}).status_code == 403


@pytest.mark.parametrize("config", ["{}", "invalid", '{"person":{}}',
    '{"person":{"token_sha256":"invalid","roles":["reviewer"]}}',
    '{"person":{},"person":{}}',
])
def test_invalid_configuration_fails_closed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, config: str,
) -> None:
    monkeypatch.setenv("FLOODGUARD_OPERATORS_JSON", config)
    response = client.post("/terrain/acquisitions", headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 503
    assert TOKEN not in response.text


def test_qa_credentials_are_page_local_and_same_origin_only() -> None:
    html = with_operator_credentials("<html><body>QA</body></html>")
    assert 'type="password"' in html
    assert "url.origin === location.origin" in html
    assert "localStorage" not in html and "sessionStorage" not in html
