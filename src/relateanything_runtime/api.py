from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from relateanything_runtime.config import ConfigurationError, parse_submit_body
from relateanything_runtime.jobs import JobStatus, JobStore, TERMINAL, job_to_response
from relateanything_runtime.logging_policy import assert_safe_log_message
from relateanything_runtime.pipeline.processor import run_visual_job

logger = logging.getLogger("relateanything_runtime")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RelateAnything Runtime", version="0.1.0")
store = JobStore()


def _schedule(record, limit: int) -> None:
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


@app.post("/v1/jobs")
async def submit_job(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid_json_body")
    try:
        case_id, stored_file_id, mime_type, source_signed_url, config = parse_submit_body(body)
    except ConfigurationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    record, reused = store.create_or_get_idempotent(
        idempotency_key.strip(),
        case_id=case_id,
        stored_file_id=stored_file_id,
        mime_type=mime_type,
        source_signed_url=source_signed_url,
        config=config,
    )
    if reused:
        return JSONResponse(job_to_response(record))

    limit = config.require_int("content_visual_inference_concurrency_limit")
    record.status = JobStatus.SUBMITTED
    store.update(record)
    _schedule(record, limit)
    return JSONResponse(job_to_response(record), status_code=202)


@app.get("/v1/jobs/{execution_id}")
async def get_job(execution_id: str) -> JSONResponse:
    record = store.get_by_execution(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail="execution_not_found")
    return JSONResponse(job_to_response(record))


@app.delete("/v1/jobs/{execution_id}")
async def cancel_job(execution_id: str) -> JSONResponse:
    record = store.get_by_execution(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail="execution_not_found")
    if record.status in TERMINAL:
        return JSONResponse(job_to_response(record))
    record.cancel_requested = True
    if record.status in {JobStatus.QUEUED, JobStatus.SUBMITTED}:
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
