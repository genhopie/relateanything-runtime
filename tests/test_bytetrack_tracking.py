import json

import numpy as np
import pytest

from relateanything_runtime.config import GovernedProcessingConfig
from relateanything_runtime.pipeline.bytetrack_tracking import (
    create_bytetrack_tracker,
    stable_track_key,
    update_tracks,
)
from relateanything_runtime.config_keys import LOCKED_ARTIFACT_PINS


def _tracking_config() -> GovernedProcessingConfig:
    raw = {
        key: "x"
        for key in (
            "content_visual_inference_relation_model",
            "content_visual_inference_relation_model_revision",
            "content_visual_inference_relation_model_weight_checksum",
            "content_visual_inference_detector_model",
            "content_visual_inference_detector_revision",
            "content_visual_inference_detector_weight_checksum",
            "content_visual_inference_tracker_model",
            "content_visual_inference_tracker_revision",
            "content_visual_inference_runtime_container_revision",
            "content_visual_inference_processing_config_version",
            "content_visual_inference_relation_vocabulary",
            "content_visual_inference_sampling_interval_ms",
            "content_visual_inference_max_frames",
            "content_visual_inference_scene_change_threshold",
            "content_visual_inference_motion_threshold",
            "content_visual_inference_object_change_threshold",
            "content_visual_inference_max_segments",
            "content_visual_inference_max_objects_per_frame",
            "content_visual_inference_min_detector_confidence",
            "content_visual_inference_min_relation_confidence",
            "content_visual_inference_temporal_consolidation_window_ms",
            "content_visual_inference_duplicate_suppression_config",
            "content_visual_inference_job_timeout_seconds",
            "content_visual_inference_runtime_timeout_seconds",
            "content_visual_inference_poll_interval_seconds",
            "content_visual_inference_retry_count",
            "content_visual_inference_retry_delay_seconds",
            "content_visual_inference_concurrency_limit",
            "content_visual_inference_cancellation_timeout_seconds",
            "content_visual_inference_source_url_ttl_seconds",
        )
    }
    raw.update(
        {
            "content_visual_inference_relation_model_revision": LOCKED_ARTIFACT_PINS["relation_model_upstream_git"],
            "content_visual_inference_relation_model_weight_checksum": LOCKED_ARTIFACT_PINS["relation_model_weight_sha256"],
            "content_visual_inference_detector_revision": LOCKED_ARTIFACT_PINS["detector_revision"],
            "content_visual_inference_detector_weight_checksum": LOCKED_ARTIFACT_PINS["detector_weight_sha256"],
            "content_visual_inference_tracker_model": "ByteTrackTracker",
            "content_visual_inference_tracker_revision": LOCKED_ARTIFACT_PINS["tracker_publish_commit"],
            "content_visual_inference_tracking_config": json.dumps(
                {
                    "lost_track_buffer": 30,
                    "track_activation_threshold": 0.25,
                    "minimum_consecutive_frames": 1,
                    "minimum_iou_threshold": 0.1,
                    "high_conf_det_threshold": 0.25,
                }
            ),
        }
    )
    return GovernedProcessingConfig(
        raw=raw,
        processing_config_version="cfg-v1",
        runtime_revision="sha256:test",
    )


def test_bytetrack_assigns_stable_ids_across_frames() -> None:
    trackers = pytest.importorskip("trackers")
    _ = trackers
    config = _tracking_config()
    tracker = create_bytetrack_tracker(config, frame_rate=30.0)
    frame = np.zeros((120, 120, 3), dtype=np.uint8)
    boxes_a = np.array([[10, 10, 40, 40], [60, 60, 90, 90]], dtype=np.float32)
    scores_a = np.array([0.9, 0.85], dtype=np.float32)
    out_a = update_tracks(tracker, frame, boxes_a, scores_a, timestamp_seconds=0.0)
    out_b = update_tracks(
        tracker,
        frame,
        boxes_a + np.array([2, 2, 2, 2], dtype=np.float32),
        scores_a,
        timestamp_seconds=1 / 30,
    )
    assert out_b.tracker_id is not None
    active_ids = [int(tid) for tid in out_b.tracker_id if int(tid) >= 0]
    assert len(active_ids) >= 2
    assert len(set(active_ids)) == len(active_ids)
    assert stable_track_key(active_ids[0]).startswith("track-")


def test_tracking_config_missing_key_fails() -> None:
    config = _tracking_config()
    broken = dict(config.raw)
    broken["content_visual_inference_tracking_config"] = json.dumps({"lost_track_buffer": 1})
    broken_config = GovernedProcessingConfig(
        raw=broken,
        processing_config_version=config.processing_config_version,
        runtime_revision=config.runtime_revision,
    )
    from relateanything_runtime.pipeline.inference import InferenceUnavailableError

    with pytest.raises(InferenceUnavailableError, match="tracking_config_missing"):
        create_bytetrack_tracker(broken_config, frame_rate=30.0)
