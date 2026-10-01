from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from relateanything_runtime.config import GovernedProcessingConfig


class JobStatus(str, Enum):
    QUEUED = "queued"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}


@dataclass
class JobRecord:
    execution_id: str
    idempotency_key: str
    case_id: str
    stored_file_id: str
    mime_type: str
    source_signed_url: str
    config: GovernedProcessingConfig
    status: JobStatus = JobStatus.QUEUED
    cancel_requested: bool = False
    observations: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    created_at: str = field(default_factory=lambda: _now())
    updated_at: str = field(default_factory=lambda: _now())
    started_at: str | None = None
    completed_at: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_idempotency: dict[str, JobRecord] = {}
        self._by_execution: dict[str, JobRecord] = {}
        self._active_workers = 0

    def get_by_idempotency(self, key: str) -> JobRecord | None:
        with self._lock:
            return self._by_idempotency.get(key)

    def get_by_execution(self, execution_id: str) -> JobRecord | None:
        with self._lock:
            return self._by_execution.get(execution_id)

    def create_or_get_idempotent(
        self,
        idempotency_key: str,
        *,
        case_id: str,
        stored_file_id: str,
        mime_type: str,
        source_signed_url: str,
        config: GovernedProcessingConfig,
    ) -> tuple[JobRecord, bool]:
        with self._lock:
            existing = self._by_idempotency.get(idempotency_key)
            if existing:
                return existing, True
            execution_id = str(uuid.uuid4())
            record = JobRecord(
                execution_id=execution_id,
                idempotency_key=idempotency_key,
                case_id=case_id,
                stored_file_id=stored_file_id,
                mime_type=mime_type,
                source_signed_url=source_signed_url,
                config=config,
                status=JobStatus.SUBMITTED,
            )
            self._by_idempotency[idempotency_key] = record
            self._by_execution[execution_id] = record
            return record, False

    def update(self, record: JobRecord) -> None:
        with self._lock:
            record.updated_at = _now()
            self._by_execution[record.execution_id] = record
            self._by_idempotency[record.idempotency_key] = record

    def try_acquire_worker_slot(self, limit: int) -> bool:
        with self._lock:
            if self._active_workers >= limit:
                return False
            self._active_workers += 1
            return True

    def release_worker_slot(self) -> None:
        with self._lock:
            self._active_workers = max(0, self._active_workers - 1)


def job_to_response(record: JobRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "executionId": record.execution_id,
        "id": record.execution_id,
        "status": record.status.value,
        "provenance": record.provenance,
        "usage": record.usage,
    }
    if record.status == JobStatus.SUCCEEDED:
        payload["observations"] = record.observations
        payload["result"] = {"observations": record.observations}
    if record.status == JobStatus.FAILED:
        payload["error"] = {
            "code": record.error_code or "processing_failed",
            "message": record.error_message or "Processing failed.",
        }
    return payload
