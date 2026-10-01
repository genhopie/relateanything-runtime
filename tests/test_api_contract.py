from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from relateanything_runtime.api import app, reset_store_for_tests
from relateanything_runtime.jobs import JobStatus
from tests.test_config_fixture import VALID_SUBMIT_BODY


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_store_for_tests()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_submit_requires_idempotency_key(client: TestClient) -> None:
    response = client.post("/v1/jobs", json=VALID_SUBMIT_BODY)
    assert response.status_code == 400


def test_submit_idempotent_replay(client: TestClient) -> None:
    with patch("relateanything_runtime.api._dispatch"):
        first = client.post(
            "/v1/jobs",
            json=VALID_SUBMIT_BODY,
            headers={"Idempotency-Key": "job-abc"},
        )
        assert first.status_code in {200, 202}
        execution_id = first.json()["executionId"]
        second = client.post(
            "/v1/jobs",
            json=VALID_SUBMIT_BODY,
            headers={"Idempotency-Key": "job-abc"},
        )
        assert second.status_code == 200
        assert second.json()["executionId"] == execution_id


def test_cancel_is_idempotent_for_terminal_state(client: TestClient) -> None:
    with patch("relateanything_runtime.api._dispatch"):
        submit = client.post(
            "/v1/jobs",
            json=VALID_SUBMIT_BODY,
            headers={"Idempotency-Key": "job-cancel"},
        )
        execution_id = submit.json()["executionId"]
    from relateanything_runtime.api import store

    record = store.get_by_execution(execution_id)
    assert record is not None
    record.status = JobStatus.CANCELLED
    store.update(record)
    first = client.delete(f"/v1/jobs/{execution_id}")
    second = client.delete(f"/v1/jobs/{execution_id}")
    assert first.json()["status"] == "cancelled"
    assert second.json()["status"] == "cancelled"


def test_missing_config_key_rejected(client: TestClient) -> None:
    body = dict(VALID_SUBMIT_BODY)
    body["processingConfiguration"] = dict(body["processingConfiguration"])
    del body["processingConfiguration"]["content_visual_inference_max_frames"]
    response = client.post(
        "/v1/jobs",
        json=body,
        headers={"Idempotency-Key": "job-missing-config"},
    )
    assert response.status_code == 400


def test_logging_policy_blocks_secrets() -> None:
    from relateanything_runtime.logging_policy import assert_safe_log_message

    with pytest.raises(ValueError):
        assert_safe_log_message("logged sourceSignedUrl value")
