from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from relateanything_runtime.config_keys import LOCKED_ARTIFACT_PINS, REQUIRED_PROCESSING_CONFIGURATION_KEYS


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class GovernedProcessingConfig:
    raw: dict[str, str]
    processing_config_version: str
    runtime_revision: str

    def require_int(self, key: str) -> int:
        value = self.raw.get(key)
        if value is None or not str(value).strip():
            raise ConfigurationError(f"missing_config:{key}")
        try:
            parsed = int(str(value).strip())
        except ValueError:
            raise ConfigurationError(f"invalid_config:{key}") from None
        return parsed

    def require_float(self, key: str) -> float:
        value = self.raw.get(key)
        if value is None or not str(value).strip():
            raise ConfigurationError(f"missing_config:{key}")
        try:
            parsed = float(str(value).strip())
        except ValueError:
            raise ConfigurationError(f"invalid_config:{key}") from None
        return parsed

    def require_str(self, key: str) -> str:
        value = self.raw.get(key)
        if value is None or not str(value).strip():
            raise ConfigurationError(f"missing_config:{key}")
        return str(value).strip()


def parse_submit_body(body: dict[str, Any]) -> tuple[str, str, str, str, GovernedProcessingConfig]:
    case_id = body.get("caseId")
    stored_file_id = body.get("storedFileId")
    mime_type = body.get("mimeType")
    source_signed_url = body.get("sourceSignedUrl")
    if not all(isinstance(v, str) and v.strip() for v in (case_id, stored_file_id, mime_type, source_signed_url)):
        raise ConfigurationError("invalid_submit_body")

    processing_configuration = body.get("processingConfiguration")
    if not isinstance(processing_configuration, dict):
        raise ConfigurationError("missing_processing_configuration")

    normalized: dict[str, str] = {}
    for key in REQUIRED_PROCESSING_CONFIGURATION_KEYS:
        entry = processing_configuration.get(key)
        if entry is None or not str(entry).strip():
            raise ConfigurationError(f"missing_config:{key}")
        normalized[key] = str(entry).strip()

    processing_config_version = body.get("processingConfigVersion")
    runtime_revision = body.get("runtimeRevision")
    if not isinstance(processing_config_version, str) or not processing_config_version.strip():
        raise ConfigurationError("missing_processing_config_version")
    if not isinstance(runtime_revision, str) or not runtime_revision.strip():
        raise ConfigurationError("missing_runtime_revision")

    if normalized["content_visual_inference_processing_config_version"] != processing_config_version.strip():
        raise ConfigurationError("processing_config_version_mismatch")
    if normalized["content_visual_inference_runtime_container_revision"] != runtime_revision.strip():
        raise ConfigurationError("runtime_revision_mismatch")

    _assert_locked_pins(normalized)

    return (
        case_id.strip(),
        stored_file_id.strip(),
        mime_type.strip(),
        source_signed_url.strip(),
        GovernedProcessingConfig(
            raw=normalized,
            processing_config_version=processing_config_version.strip(),
            runtime_revision=runtime_revision.strip(),
        ),
    )


def _assert_locked_pins(config: dict[str, str]) -> None:
    if config["content_visual_inference_relation_model_revision"] != LOCKED_ARTIFACT_PINS["relation_model_upstream_git"]:
        raise ConfigurationError("relation_model_revision_mismatch")
    if (
        config["content_visual_inference_relation_model_weight_checksum"].lower()
        != LOCKED_ARTIFACT_PINS["relation_model_weight_sha256"]
    ):
        raise ConfigurationError("relation_model_checksum_mismatch")
    if config["content_visual_inference_detector_revision"] != LOCKED_ARTIFACT_PINS["detector_revision"]:
        raise ConfigurationError("detector_revision_mismatch")
    if (
        config["content_visual_inference_detector_weight_checksum"].lower()
        != LOCKED_ARTIFACT_PINS["detector_weight_sha256"]
    ):
        raise ConfigurationError("detector_checksum_mismatch")
    tracker = config["content_visual_inference_tracker_model"]
    if tracker not in {"ByteTrackTracker", "ByteTrack", LOCKED_ARTIFACT_PINS["tracker_package"]}:
        raise ConfigurationError("tracker_model_mismatch")
