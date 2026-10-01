"""Durable job metadata for Modal deployments (no signed URLs or raw video)."""

from __future__ import annotations

import os
from typing import Any

from relateanything_runtime.config import GovernedProcessingConfig
from relateanything_runtime.jobs import InMemoryJobStore, JobRecord, JobStatus, JobStore, _now

DEFAULT_REGISTRY_IMAGE = (
    "ghcr.io/genhopie/relateanything-runtime"
    "@sha256:37b3edec8612f22113478e47a98a65e4f6c5bd0d31e63cbd8d4d5e16049f0c9a"
)


def modal_jobs_enabled() -> bool:
    return os.environ.get("RELATEANYTHING_JOB_BACKEND", "local").strip().lower() == "modal"


def _dict_name() -> str:
    return os.environ.get("RELATEANYTHING_MODAL_STATE_DICT", "relateanything-runtime-job-state")


def _get_modal_dict():
    import modal  # type: ignore[import-untyped]

    return modal.Dict.from_name(_dict_name(), create_if_missing=True)


def _idempotency_key(key: str) -> str:
    return f"idempotency:{key}"


def _execution_key(execution_id: str) -> str:
    return f"execution:{execution_id}"


def record_to_durable_blob(record: JobRecord) -> dict[str, Any]:
    return {
        "execution_id": record.execution_id,
        "idempotency_key": record.idempotency_key,
        "case_id": record.case_id,
        "stored_file_id": record.stored_file_id,
        "mime_type": record.mime_type,
        "config_raw": dict(record.config.raw),
        "processing_config_version": record.config.processing_config_version,
        "runtime_revision": record.config.runtime_revision,
        "status": record.status.value,
        "cancel_requested": record.cancel_requested,
        "observations": record.observations,
        "provenance": record.provenance,
        "usage": record.usage,
        "error_code": record.error_code,
        "error_message": record.error_message,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "function_call_id": record.function_call_id,
    }


def record_from_durable_blob(blob: dict[str, Any], *, source_signed_url: str = "") -> JobRecord:
    config = GovernedProcessingConfig(
        raw={str(k): str(v) for k, v in blob.get("config_raw", {}).items()},
        processing_config_version=str(blob.get("processing_config_version", "")),
        runtime_revision=str(blob.get("runtime_revision", "")),
    )
    return JobRecord(
        execution_id=str(blob["execution_id"]),
        idempotency_key=str(blob["idempotency_key"]),
        case_id=str(blob.get("case_id", "")),
        stored_file_id=str(blob.get("stored_file_id", "")),
        mime_type=str(blob.get("mime_type", "")),
        source_signed_url=source_signed_url,
        config=config,
        status=JobStatus(str(blob.get("status", JobStatus.SUBMITTED.value))),
        cancel_requested=bool(blob.get("cancel_requested")),
        observations=list(blob.get("observations") or []),
        provenance=dict(blob.get("provenance") or {}),
        usage=dict(blob.get("usage") or {}),
        error_code=blob.get("error_code"),
        error_message=blob.get("error_message"),
        created_at=str(blob.get("created_at") or _now()),
        updated_at=str(blob.get("updated_at") or _now()),
        started_at=blob.get("started_at"),
        completed_at=blob.get("completed_at"),
        function_call_id=blob.get("function_call_id"),
    )


class ModalJobStore:
    """Modal Dict-backed metadata; signed URLs are not written to the dict."""

    def __init__(self) -> None:
        self._dict = _get_modal_dict()
        self._active_workers = 0

    def get_by_idempotency(self, key: str) -> JobRecord | None:
        blob = self._dict.get(_idempotency_key(key))
        if not isinstance(blob, dict):
            return None
        return record_from_durable_blob(blob)

    def get_by_execution(self, execution_id: str) -> JobRecord | None:
        blob = self._dict.get(_execution_key(execution_id))
        if not isinstance(blob, dict):
            return None
        return record_from_durable_blob(blob)

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
        existing = self.get_by_idempotency(idempotency_key)
        if existing:
            if source_signed_url and not existing.source_signed_url:
                existing.source_signed_url = source_signed_url
            return existing, True
        import uuid

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
        blob = record_to_durable_blob(record)
        self._dict[_idempotency_key(idempotency_key)] = blob
        self._dict[_execution_key(execution_id)] = blob
        return record, False

    def update(self, record: JobRecord) -> None:
        record.updated_at = _now()
        blob = record_to_durable_blob(record)
        self._dict[_idempotency_key(record.idempotency_key)] = blob
        self._dict[_execution_key(record.execution_id)] = blob

    def try_acquire_worker_slot(self, limit: int) -> bool:
        if self._active_workers >= limit:
            return False
        self._active_workers += 1
        return True

    def release_worker_slot(self) -> None:
        self._active_workers = max(0, self._active_workers - 1)


def spawn_modal_gpu_job(record: JobRecord) -> str:
    """Spawn GPU worker; returns Modal FunctionCall id. Source URL is passed only to the call."""
    import modal  # type: ignore[import-untyped]

    fn = modal.Function.from_name(
        os.environ.get("RELATEANYTHING_MODAL_APP", "relateanything-runtime"),
        os.environ.get("RELATEANYTHING_MODAL_GPU_FUNCTION", "run_visual_job_gpu"),
    )
    payload = {
        "execution_id": record.execution_id,
        "idempotency_key": record.idempotency_key,
        "source_signed_url": record.source_signed_url,
        "durable": record_to_durable_blob(record),
    }
    call = fn.spawn(payload)
    return str(call.object_id)


def refresh_record_from_modal_dict(record: JobRecord) -> None:
    blob = _get_modal_dict().get(_execution_key(record.execution_id))
    if not isinstance(blob, dict):
        return
    refreshed = record_from_durable_blob(blob)
    record.status = refreshed.status
    record.observations = refreshed.observations
    record.provenance = refreshed.provenance
    record.usage = refreshed.usage
    record.error_code = refreshed.error_code
    record.error_message = refreshed.error_message
    record.started_at = refreshed.started_at
    record.completed_at = refreshed.completed_at
    record.cancel_requested = refreshed.cancel_requested
    record.function_call_id = refreshed.function_call_id or record.function_call_id


def cancel_modal_function_call(function_call_id: str) -> None:
    import modal  # type: ignore[import-untyped]

    try:
        call = modal.functions.FunctionCall.from_id(function_call_id)
        call.cancel()
    except Exception:
        return


def create_job_store() -> JobStore:
    if modal_jobs_enabled():
        return ModalJobStore()
    return InMemoryJobStore()
