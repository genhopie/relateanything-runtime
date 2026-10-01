from __future__ import annotations

import os
import tempfile
import time
from typing import Any

import httpx

from relateanything_runtime.config import GovernedProcessingConfig
from relateanything_runtime.jobs import JobRecord, JobStatus
from relateanything_runtime.pipeline.inference import (
    InferenceUnavailableError,
    build_provenance,
    run_relation_pipeline,
)
from relateanything_runtime.pipeline.sampling import load_frames, read_video_metadata, select_frame_indices


def run_visual_job(record: JobRecord) -> None:
    if record.cancel_requested:
        record.status = JobStatus.CANCELLED
        record.completed_at = record.completed_at or _iso_now()
        return

    config = record.config
    timeout = config.require_int("content_visual_inference_job_timeout_seconds")
    record.status = JobStatus.RUNNING
    record.started_at = record.started_at or _iso_now()

    started = time.perf_counter()
    frames_processed = 0
    bytes_downloaded = 0

    try:
        with tempfile.TemporaryDirectory(prefix="ra-runtime-") as tmp:
            video_path = os.path.join(tmp, "source.bin")
            bytes_downloaded = _download_source(record.source_signed_url, video_path, timeout_seconds=timeout)
            frame_count, fps = read_video_metadata(video_path)
            indices = select_frame_indices(
                frame_count,
                fps,
                sampling_interval_ms=config.require_int("content_visual_inference_sampling_interval_ms"),
                max_frames=config.require_int("content_visual_inference_max_frames"),
                scene_change_threshold=config.require_float("content_visual_inference_scene_change_threshold"),
                motion_threshold=config.require_float("content_visual_inference_motion_threshold"),
                object_change_threshold=config.require_float("content_visual_inference_object_change_threshold"),
                max_segments=config.require_int("content_visual_inference_max_segments"),
            )
            frames = load_frames(video_path, indices)
            frames_processed = len(frames)
            observations = run_relation_pipeline(frames, config, fps)
            record.observations = observations
            record.provenance = build_provenance(config)
            record.provenance["detector_version"] = config.require_str("content_visual_inference_detector_model")
            record.provenance["tracker_version"] = config.require_str("content_visual_inference_tracker_revision")
            record.status = JobStatus.SUCCEEDED
            record.completed_at = _iso_now()
    except InferenceUnavailableError as error:
        record.status = JobStatus.FAILED
        record.error_code = str(error)
        record.error_message = "Inference stack or artifacts unavailable."
        record.completed_at = _iso_now()
    except Exception as error:  # noqa: BLE001 — bounded job failure surface
        record.status = JobStatus.FAILED
        record.error_code = "processing_failed"
        record.error_message = error.__class__.__name__
        record.completed_at = _iso_now()
    finally:
        elapsed = time.perf_counter() - started
        record.usage = {
            "frames_processed": frames_processed,
            "bytes_downloaded": bytes_downloaded,
            "wall_time_seconds": round(elapsed, 3),
            "measured": True,
        }


def _download_source(url: str, dest: str, timeout_seconds: int) -> int:
    with httpx.stream("GET", url, timeout=timeout_seconds, follow_redirects=True) as response:
        response.raise_for_status()
        total = 0
        with open(dest, "wb") as handle:
            for chunk in response.iter_bytes():
                total += len(chunk)
                handle.write(chunk)
    return total


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
