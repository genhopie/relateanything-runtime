from relateanything_runtime.config import GovernedProcessingConfig
from relateanything_runtime.jobs import JobRecord, JobStatus
from relateanything_runtime.modal_state import record_from_durable_blob, record_to_durable_blob
from tests.test_config_fixture import VALID_SUBMIT_BODY


def _sample_record() -> JobRecord:
    from relateanything_runtime.config import parse_submit_body

    case_id, stored_file_id, mime_type, source_signed_url, config = parse_submit_body(VALID_SUBMIT_BODY)
    return JobRecord(
        execution_id="exec-1",
        idempotency_key="job-1",
        case_id=case_id,
        stored_file_id=stored_file_id,
        mime_type=mime_type,
        source_signed_url=source_signed_url,
        config=config,
        status=JobStatus.SUBMITTED,
    )


def test_durable_blob_excludes_signed_url() -> None:
    record = _sample_record()
    blob = record_to_durable_blob(record)
    assert "source_signed_url" not in blob
    assert "sourceSignedUrl" not in blob
    restored = record_from_durable_blob(blob)
    assert restored.source_signed_url == ""


def test_durable_blob_round_trip_config() -> None:
    record = _sample_record()
    blob = record_to_durable_blob(record)
    restored = record_from_durable_blob(blob, source_signed_url="https://example.test/v.mp4")
    assert isinstance(restored.config, GovernedProcessingConfig)
    assert restored.config.processing_config_version == record.config.processing_config_version
