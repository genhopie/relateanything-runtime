import os

import pytest
from fastapi.testclient import TestClient

from relateanything_runtime.api import app, reset_store_for_tests


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_store_for_tests()


def test_bearer_required_when_api_key_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELATEANYTHING_RUNTIME_API_KEY", "secret-token")
    client = TestClient(app)
    response = client.post("/control-plane", json={"operation": "status", "runtimeJobId": "missing"})
    assert response.status_code == 401
    authed = client.post(
        "/control-plane",
        json={"operation": "status", "runtimeJobId": "missing"},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert authed.status_code == 404


def test_healthz_unauthenticated_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELATEANYTHING_RUNTIME_API_KEY", "secret-token")
    client = TestClient(app)
    assert client.get("/healthz").status_code == 200
