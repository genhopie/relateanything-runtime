from __future__ import annotations

import logging
import os
import threading
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from relateanything_runtime.config import ConfigurationError, parse_submit_body
from relateanything_runtime.jobs import (
    TERMINAL,
    JobStatus,
    InMemoryJobStore,
    job_to_control_plane_response,
    job_to_response,
)
from relateanything_runtime.logging_policy import assert_safe_log_message
from relateanything_runtime.modal_state import (
    cancel_modal_function_call,
    create_job_store,
    modal_jobs_enabled,
    refresh_record_from_modal_dict,
    spawn_modal_gpu_job,
)
from relateanything_runtime.pipeline.processor import run_visual_job

logger = logging.getLogger("relateanything_runtime")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RelateAnything Runtime", version="0.1.0")
store = create_job_store()


def _verify_runtime_api_key(authorization: str | None) -> None:
    expected = os.environ.get("RELATEANYTHING_RUNTIME_API_KEY", "").strip()
    if not expected:
        return
    if not authorization or not authorization.strip().lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    token = authorization.strip().split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _schedule_local(record, limit: int) -> None:
    def worker() -> None:
        if not store.try_acquire_worker_slot(limit):
            record.status = JobStatus.QUEUED
            store.update(record)
            return
        try:
            run_visual_job(record)
        finally:
            store.release_worker_slot()
            store.update(record)

    threading.Thread(target=worker, daemon=True).start()


def _dispatch(record, limit: int) -> None:
    if modal_jobs_enabled():
        record.status = JobStatus.SUBMITTED
        store.update(record)
        record.function_call_id = spawn_modal_gpu_job(record)
        record.status = JobStatus.RUNNING
        store.update(record)
        return
    record.status = JobStatus.SUBMITTED
    store.update(record)
    _schedule_local(record, limit)


def _refresh_modal_status(record) -> None:
    if not modal_jobs_enabled():
        return
    if record.status in TERMINAL:
        return
    refresh_record_from_modal_dict(record)
    store.update(record)


def _submit_from_body(body: dict[str, Any], idempotency_key: str) -> tuple[Any, bool]:
    case_id, stored_file_id, mime_type, source_signed_url, config = parse_submit_body(body)
    record, reused = store.create_or_get_idempotent(
        idempotency_key,
        case_id=case_id,
        stored_file_id=stored_file_id,
        mime_type=mime_type,
        source_signed_url=source_signed_url,
        config=config,
    )
    if reused:
        return record, True
    limit = config.require_int("content_visual_inference_concurrency_limit")
    _dispatch(record, limit)
    return record, False


def _build_submit_body_from_control_plane(body: dict[str, Any]) -> dict[str, Any]:
    submit = body.get("submit")
    if not isinstance(submit, dict):
        raise ConfigurationError("missing_submit_payload")
    client_job_id = submit.get("clientJobId")
    if not isinstance(client_job_id, str) or not client_job_id.strip():
        raise ConfigurationError("missing_client_job_id")
    merged: dict[str, Any] = dict(submit)
    merged.pop("clientJobId", None)
    merged.setdefault("caseId", body.get("caseId"))
    for key in (
        "storedFileId",
        "mimeType",
        "sourceSignedUrl",
        "processingConfiguration",
        "processingConfigVersion",
        "runtimeRevision",
    ):
        if key not in merged and key in body:
            merged[key] = body[key]
    return merged


@app.post("/control-plane")
async def control_plane(
    request: Request,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    _verify_runtime_api_key(authorization)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid_json_body")
    operation = body.get("operation")
    if operation not in {"submit", "status", "cancel"}:
        raise HTTPException(status_code=400, detail="invalid_operation")

    if operation == "submit":
        try:
            submit_body = _build_submit_body_from_control_plane(body)
            idempotency_key = str(submit_body.get("clientJobId", "")).strip()
            record, reused = _submit_from_body(submit_body, idempotency_key)
        except ConfigurationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        payload = job_to_control_plane_response(record)
        return JSONResponse(payload, status_code=200 if reused else 202)

    runtime_job_id = body.get("runtimeJobId")
    if not isinstance(runtime_job_id, str) or not runtime_job_id.strip():
        submit = body.get("submit")
        if isinstance(submit, dict) and isinstance(submit.get("runtimeJobId"), str):
            runtime_job_id = submit["runtimeJobId"]
    if not isinstance(runtime_job_id, str) or not runtime_job_id.strip():
        raise HTTPException(status_code=400, detail="missing_runtime_job_id")

    record = store.get_by_execution(runtime_job_id.strip())
    if not record:
        raise HTTPException(status_code=404, detail="execution_not_found")

    if operation == "status":
        _refresh_modal_status(record)
        return JSONResponse(job_to_control_plane_response(record))

    if record.status in TERMINAL:
        return JSONResponse(job_to_control_plane_response(record))
    record.cancel_requested = True
    if record.function_call_id:
        cancel_modal_function_call(record.function_call_id)
    if record.status in {JobStatus.QUEUED, JobStatus.SUBMITTED, JobStatus.RUNNING}:
        record.status = JobStatus.CANCELLED
        record.completed_at = record.completed_at or record.updated_at
    store.update(record)
    return JSONResponse(job_to_control_plane_response(record))


@app.post("/v1/jobs")
async def submit_job(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    _verify_runtime_api_key(authorization)
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid_json_body")
    try:
        record, reused = _submit_from_body(body, idempotency_key.strip())
    except ConfigurationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if reused:
        return JSONResponse(job_to_response(record))
    return JSONResponse(job_to_response(record), status_code=202)


@app.get("/v1/jobs/{execution_id}")
async def get_job(execution_id: str, authorization: str | None = Header(default=None)) -> JSONResponse:
    _verify_runtime_api_key(authorization)
    record = store.get_by_execution(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail="execution_not_found")
    _refresh_modal_status(record)
    return JSONResponse(job_to_response(record))


@app.delete("/v1/jobs/{execution_id}")
async def cancel_job(execution_id: str, authorization: str | None = Header(default=None)) -> JSONResponse:
    _verify_runtime_api_key(authorization)
    record = store.get_by_execution(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail="execution_not_found")
    if record.status in TERMINAL:
        return JSONResponse(job_to_response(record))
    record.cancel_requested = True
    if record.function_call_id:
        cancel_modal_function_call(record.function_call_id)
    if record.status in {JobStatus.QUEUED, JobStatus.SUBMITTED, JobStatus.RUNNING}:
        record.status = JobStatus.CANCELLED
        record.completed_at = record.completed_at or record.updated_at
    store.update(record)
    return JSONResponse(job_to_response(record))


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.middleware("http")
async def safe_logging_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    path = request.url.path
    assert_safe_log_message(path)
    response = await call_next(request)
    return response


def reset_store_for_tests() -> None:
    global store
    store = InMemoryJobStore()
