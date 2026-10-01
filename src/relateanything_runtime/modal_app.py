"""Modal deployment entrypoint (scale-to-zero GPU + ASGI control plane)."""

from __future__ import annotations

import os

import modal

from relateanything_runtime.modal_state import DEFAULT_REGISTRY_IMAGE

APP_NAME = os.environ.get("RELATEANYTHING_MODAL_APP", "relateanything-runtime")
MODAL_ENV = os.environ.get("RELATEANYTHING_MODAL_ENVIRONMENT", "main")
REGISTRY_IMAGE = os.environ.get("RELATEANYTHING_REGISTRY_IMAGE", DEFAULT_REGISTRY_IMAGE)

inference_image = modal.Image.from_registry(REGISTRY_IMAGE)
web_image = inference_image

app = modal.App(APP_NAME)


def _modal_secrets() -> list[modal.Secret]:
    name = os.environ.get("RELATEANYTHING_MODAL_SECRET", "").strip()
    if not name:
        return []
    return [modal.Secret.from_name(name)]


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
    os.environ["RELATEANYTHING_JOB_BACKEND"] = "modal"
    from relateanything_runtime.api import app as fastapi_app

    return fastapi_app
