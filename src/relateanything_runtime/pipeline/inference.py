from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from relateanything_runtime.config import GovernedProcessingConfig
from relateanything_runtime.config_keys import LOCKED_ARTIFACT_PINS


class InferenceUnavailableError(RuntimeError):
    pass


def _artifact_root() -> Path:
    root = os.environ.get("RELATEANYTHING_ARTIFACT_ROOT", "").strip()
    if not root:
        raise InferenceUnavailableError("artifact_root_missing")
    path = Path(root)
    if not path.is_dir():
        raise InferenceUnavailableError("artifact_root_invalid")
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundled_artifacts(config: GovernedProcessingConfig) -> None:
    root = _artifact_root()
    relation_weights = root / "relation" / "model.pth"
    detector_weights = root / "detector" / "model.safetensors"
    if not relation_weights.is_file():
        raise InferenceUnavailableError("relation_weights_missing")
    if not detector_weights.is_file():
        raise InferenceUnavailableError("detector_weights_missing")
    if _sha256_file(relation_weights).lower() != LOCKED_ARTIFACT_PINS["relation_model_weight_sha256"]:
        raise InferenceUnavailableError("relation_weights_checksum_mismatch")
    if _sha256_file(detector_weights).lower() != LOCKED_ARTIFACT_PINS["detector_weight_sha256"]:
        raise InferenceUnavailableError("detector_weights_checksum_mismatch")
    _ = config


def build_provenance(config: GovernedProcessingConfig) -> dict[str, Any]:
    return {
        "relation_model": config.require_str("content_visual_inference_relation_model"),
        "relation_model_revision": config.require_str("content_visual_inference_relation_model_revision"),
        "relation_model_weight_checksum": config.require_str("content_visual_inference_relation_model_weight_checksum"),
        "detector_model": config.require_str("content_visual_inference_detector_model"),
        "detector_revision": config.require_str("content_visual_inference_detector_revision"),
        "detector_weight_checksum": config.require_str("content_visual_inference_detector_weight_checksum"),
        "tracker_model": config.require_str("content_visual_inference_tracker_model"),
        "tracker_revision": config.require_str("content_visual_inference_tracker_revision"),
        "processing_config_version": config.processing_config_version,
        "runtime_revision": config.runtime_revision,
        "preprocessing_version": "bounded_sampling_v1",
        "relation_vocabulary": config.require_str("content_visual_inference_relation_vocabulary"),
    }


def run_relation_pipeline(
    frames: list[tuple[int, np.ndarray]],
    config: GovernedProcessingConfig,
    fps: float,
) -> list[dict[str, Any]]:
    from relateanything_runtime.pipeline.relsgg_bridge import process_sampled_frames

    observations = process_sampled_frames(frames, config, fps)
    return _consolidate_observations(
        observations,
        window_ms=config.require_int("content_visual_inference_temporal_consolidation_window_ms"),
        suppression_raw=config.require_str("content_visual_inference_duplicate_suppression_config"),
    )


def _consolidate_observations(
    observations: list[dict[str, Any]],
    *,
    window_ms: int,
    suppression_raw: str,
) -> list[dict[str, Any]]:
    if not observations:
        return []
    _ = (window_ms, suppression_raw)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in observations:
        key = f"{row['subject_track_key']}:{row['predicate']}:{row['object_track_key']}:{row['start_time_ms']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped
