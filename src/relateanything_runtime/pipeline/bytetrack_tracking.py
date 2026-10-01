from __future__ import annotations

import json
from typing import Any

import numpy as np

from relateanything_runtime.config import GovernedProcessingConfig
from relateanything_runtime.pipeline.inference import InferenceUnavailableError

REQUIRED_TRACKING_CONFIG_KEYS = (
    "lost_track_buffer",
    "track_activation_threshold",
    "minimum_consecutive_frames",
    "minimum_iou_threshold",
    "high_conf_det_threshold",
)


def parse_tracking_config(config: GovernedProcessingConfig) -> dict[str, Any]:
    raw = config.require_str("content_visual_inference_tracking_config")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise InferenceUnavailableError("tracking_config_invalid") from error
    if not isinstance(parsed, dict):
        raise InferenceUnavailableError("tracking_config_invalid")
    missing = [key for key in REQUIRED_TRACKING_CONFIG_KEYS if key not in parsed]
    if missing:
        raise InferenceUnavailableError(f"tracking_config_missing:{','.join(missing)}")
    return parsed


def create_bytetrack_tracker(config: GovernedProcessingConfig, frame_rate: float):
    try:
        from trackers import ByteTrackTracker
    except ImportError:
        raise InferenceUnavailableError("tracker_stack_missing") from None

    model_name = config.require_str("content_visual_inference_tracker_model")
    if model_name not in {"ByteTrackTracker", "ByteTrack"}:
        raise InferenceUnavailableError("tracker_model_mismatch")

    revision = config.require_str("content_visual_inference_tracker_revision")
    from relateanything_runtime.config_keys import LOCKED_ARTIFACT_PINS

    if revision != LOCKED_ARTIFACT_PINS["tracker_publish_commit"]:
        raise InferenceUnavailableError("tracker_revision_mismatch")

    params = parse_tracking_config(config)
    return ByteTrackTracker(
        lost_track_buffer=int(params["lost_track_buffer"]),
        frame_rate=float(frame_rate),
        track_activation_threshold=float(params["track_activation_threshold"]),
        minimum_consecutive_frames=int(params["minimum_consecutive_frames"]),
        minimum_iou_threshold=float(params["minimum_iou_threshold"]),
        high_conf_det_threshold=float(params["high_conf_det_threshold"]),
    )


def update_tracks(
    tracker,
    frame: np.ndarray,
    boxes_xyxy: np.ndarray,
    confidences: np.ndarray,
    *,
    timestamp_seconds: float | None = None,
):
    try:
        import supervision as sv
    except ImportError:
        raise InferenceUnavailableError("supervision_missing") from None

    if boxes_xyxy.size == 0:
        empty = np.zeros((0, 4), dtype=np.float32)
        return sv.Detections(xyxy=empty, confidence=np.zeros((0,), dtype=np.float32))

    detections = sv.Detections(
        xyxy=boxes_xyxy.astype(np.float32),
        confidence=confidences.astype(np.float32),
    )
    return tracker.update(detections, frame=frame, timestamp=timestamp_seconds)


def stable_track_key(tracker_id: int) -> str:
    return f"track-{int(tracker_id)}"
