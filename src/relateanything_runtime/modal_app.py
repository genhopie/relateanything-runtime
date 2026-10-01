"""Modal deployment entrypoint (scale-to-zero GPU + ASGI control plane)."""

from __future__ import annotations

import os

import modal

from relateanything_runtime.modal_state import DEFAULT_REGISTRY_IMAGE

APP_NAME = os.environ.get("RELATEANYTHING_MODAL_APP", "relateanything-runtime")
PRODUCTION_MODAL_ENVIRONMENT = "main"
PRODUCTION_MODAL_SECRET_NAME = "relateanything-runtime-api"
MODAL_ENV = os.environ.get("RELATEANYTHING_MODAL_ENVIRONMENT", PRODUCTION_MODAL_ENVIRONMENT)
REGISTRY_IMAGE = os.environ.get("RELATEANYTHING_REGISTRY_IMAGE", DEFAULT_REGISTRY_IMAGE)
RUNTIME_API_KEY_ENV = "RELATEANYTHING_RUNTIME_API_KEY"

inference_image = modal.Image.from_registry(REGISTRY_IMAGE)
web_image = inference_image

app = modal.App(APP_NAME)


def modal_secret_name() -> str:
    return os.environ.get("RELATEANYTHING_MODAL_SECRET", PRODUCTION_MODAL_SECRET_NAME).strip()


def modal_allows_no_secret() -> bool:
    return os.environ.get("RELATEANYTHING_MODAL_ALLOW_NO_SECRET", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _modal_secrets() -> list[modal.Secret]:
    if modal_allows_no_secret():
        return []
    name = modal_secret_name()
    if not name:
        raise RuntimeError("RELATEANYTHING_MODAL_SECRET is required for Modal deployment")
    return [modal.Secret.from_name(name)]


def assert_modal_runtime_api_key_configured() -> None:
    """Fail closed when a Modal Secret is required but did not inject the runtime API key."""
    if modal_allows_no_secret():
        return
    if not os.environ.get(RUNTIME_API_KEY_ENV, "").strip():
        raise RuntimeError(
            f"Modal secret {modal_secret_name()!r} must provide {RUNTIME_API_KEY_ENV}"
        )


@app.function(
    image=inference_image,
    gpu="T4",
    timeout=int(os.environ.get("RELATEANYTHING_MODAL_GPU_TIMEOUT_SECONDS", "3600")),
    scaledown_window=int(os.environ.get("RELATEANYTHING_MODAL_SCALEDOWN_WINDOW_SECONDS", "60")),
    max_containers=int(os.environ.get("RELATEANYTHING_MODAL_MAX_CONTAINERS", "4")),
    secrets=_modal_secrets(),
)
def run_visual_job_gpu(payload: dict) -> dict:
    """Execute one visual job on GPU; updates durable metadata without retaining signed URLs."""
    assert_modal_runtime_api_key_configured()
    os.environ["RELATEANYTHING_JOB_BACKEND"] = "modal"
    os.environ.setdefault("RELATEANYTHING_DEVICE", "cuda")
    from relateanything_runtime.jobs import JobStatus
    from relateanything_runtime.modal_state import (
        _execution_key,
        _get_modal_dict,
        record_from_durable_blob,
        record_to_durable_blob,
    )
    from relateanything_runtime.pipeline.processor import run_visual_job

    durable = payload.get("durable")
    if not isinstance(durable, dict):
        raise ValueError("missing_durable_payload")
    source_url = str(payload.get("source_signed_url", ""))
    record = record_from_durable_blob(durable, source_signed_url=source_url)
    state = _get_modal_dict()
    record.status = JobStatus.RUNNING
    state[_execution_key(record.execution_id)] = record_to_durable_blob(record)
    run_visual_job(record)
    state[_execution_key(record.execution_id)] = record_to_durable_blob(record)
    record.source_signed_url = ""
    return record_to_durable_blob(record)


@app.function(
    image=web_image,
    scaledown_window=int(os.environ.get("RELATEANYTHING_MODAL_WEB_SCALEDOWN_WINDOW_SECONDS", "60")),
    max_containers=int(os.environ.get("RELATEANYTHING_MODAL_WEB_MAX_CONTAINERS", "10")),
    secrets=_modal_secrets(),
)
@modal.asgi_app()
def serve_fastapi():
    assert_modal_runtime_api_key_configured()
    os.environ["RELATEANYTHING_JOB_BACKEND"] = "modal"
    from relateanything_runtime.api import app as fastapi_app

    return fastapi_app
