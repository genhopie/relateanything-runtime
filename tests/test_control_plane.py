from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from relateanything_runtime.api import app, reset_store_for_tests
from tests.test_config_fixture import VALID_SUBMIT_BODY


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_store_for_tests()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_control_plane_submit_maps_to_job_authority(client: TestClient) -> None:
    with patch("relateanything_runtime.api._dispatch"):
        response = client.post(
            "/control-plane",
            json={
                "operation": "submit",
                "useCaseKey": "content_video_visual_analysis",
                "moduleKey": "content_intelligence",
                "caseId": "case-1",
                "submit": {
                    "clientJobId": "job-cp-1",
                    **VALID_SUBMIT_BODY,
                },
            },
        )
    assert response.status_code == 202
    body = response.json()
    assert body["runtimeJobId"] == body["executionId"]
    assert body["status"] in {"submitted", "queued", "running"}


def test_control_plane_submit_idempotent(client: TestClient) -> None:
    with patch("relateanything_runtime.api._dispatch"):
        first = client.post(
            "/control-plane",
            json={
                "operation": "submit",
                "submit": {"clientJobId": "job-cp-2", **VALID_SUBMIT_BODY},
            },
        )
        second = client.post(
            "/control-plane",
            json={
                "operation": "submit",
                "submit": {"clientJobId": "job-cp-2", **VALID_SUBMIT_BODY},
            },
        )
    assert first.json()["runtimeJobId"] == second.json()["runtimeJobId"]


def test_control_plane_status_and_cancel(client: TestClient) -> None:
    with patch("relateanything_runtime.api._dispatch"):
        submit = client.post(
            "/control-plane",
            json={
                "operation": "submit",
                "submit": {"clientJobId": "job-cp-3", **VALID_SUBMIT_BODY},
            },
        )
        runtime_job_id = submit.json()["runtimeJobId"]
    status = client.post(
        "/control-plane",
        json={"operation": "status", "runtimeJobId": runtime_job_id},
    )
    assert status.status_code == 200
    assert status.json()["runtimeJobId"] == runtime_job_id
    cancel = client.post(
        "/control-plane",
        json={"operation": "cancel", "runtimeJobId": runtime_job_id},
    )
    assert cancel.json()["status"] == "cancelled"
    again = client.post(
        "/control-plane",
        json={"operation": "cancel", "runtimeJobId": runtime_job_id},
    )
    assert again.json()["status"] == "cancelled"
