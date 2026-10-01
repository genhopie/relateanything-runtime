from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from relateanything_runtime.config import GovernedProcessingConfig
from relateanything_runtime.pipeline.bytetrack_tracking import (
    create_bytetrack_tracker,
    stable_track_key,
    update_tracks,
)
from relateanything_runtime.pipeline.detector import get_grounding_dino_detector
from relateanything_runtime.pipeline.inference import InferenceUnavailableError, verify_bundled_artifacts
from relateanything_runtime.pipeline.relsgg_checkpoint import adapt_checkpoint_for_installed_relsgg


def process_sampled_frames(
    frames: list[tuple[int, np.ndarray]],
    config: GovernedProcessingConfig,
    fps: float,
) -> list[dict[str, Any]]:
    verify_bundled_artifacts(config)
    upstream = os.environ.get("RELATEANYTHING_UPSTREAM_PATH", "").strip()
    if not upstream:
        raise InferenceUnavailableError("upstream_path_missing")
    try:
        from relsgg import RelateAnything  # type: ignore[import-not-found]
    except ImportError:
        raise InferenceUnavailableError("relsgg_import_failed") from None

    relation_dir = Path(os.environ["RELATEANYTHING_ARTIFACT_ROOT"]) / "relation"
    checkpoint = relation_dir / "model.pth"
    if not checkpoint.is_file():
        raise InferenceUnavailableError("relation_weights_missing")
    model = _load_relate_anything_from_locked_checkpoint(
        str(checkpoint),
        device=os.environ.get("RELATEANYTHING_DEVICE", "cpu"),
    )

    vocabulary_raw = config.require_str("content_visual_inference_relation_vocabulary")
    try:
        vocabulary = json.loads(vocabulary_raw)
    except json.JSONDecodeError:
        vocabulary = [part.strip() for part in vocabulary_raw.split(",") if part.strip()]
    if not vocabulary:
        raise InferenceUnavailableError("relation_vocabulary_empty")
    model.set_vocabulary([str(item) for item in vocabulary])

    min_relation = config.require_float("content_visual_inference_min_relation_confidence")
    max_objects = config.require_int("content_visual_inference_max_objects_per_frame")
    detector = get_grounding_dino_detector(config)
    tracker = create_bytetrack_tracker(config, fps)
    observations: list[dict[str, Any]] = []

    for frame_ordinal, frame in frames:
        boxes, scores = detector.detect(frame)
        timestamp_seconds = frame_ordinal / max(fps, 1.0)
        tracked = update_tracks(tracker, frame, boxes, scores, timestamp_seconds=timestamp_seconds)
        if tracked.xyxy is None or len(tracked.xyxy) < 2:
            continue
        tracker_ids = tracked.tracker_id
        if tracker_ids is None:
            continue
        valid_mask = tracker_ids >= 0
        if int(np.sum(valid_mask)) < 2:
            continue

        boxes_for_relations = tracked.xyxy[valid_mask].astype(np.float32)
        id_for_index = [int(tid) for tid in tracker_ids[valid_mask]]
        triplets = model.predict(frame, boxes_for_relations, topk=max_objects)
        start_ms = int(timestamp_seconds * 1000)
        end_ms = start_ms + config.require_int("content_visual_inference_sampling_interval_ms")
        for triplet in triplets:
            if float(triplet.score) < min_relation:
                continue
            sub_idx = int(triplet.subject_idx)
            obj_idx = int(triplet.object_idx)
            if sub_idx < 0 or obj_idx < 0 or sub_idx >= len(id_for_index) or obj_idx >= len(id_for_index):
                continue
            sub_track = id_for_index[sub_idx]
            obj_track = id_for_index[obj_idx]
            observations.append(
                {
                    "start_time_ms": start_ms,
                    "end_time_ms": end_ms,
                    "frame_ordinal": frame_ordinal,
                    "subject_track_key": stable_track_key(sub_track),
                    "subject_label": triplet.subject_label,
                    "subject_region": _box_region(triplet.subject_box, frame.shape),
                    "predicate": triplet.predicate,
                    "object_track_key": stable_track_key(obj_track),
                    "object_label": triplet.object_label,
                    "object_region": _box_region(triplet.object_box, frame.shape),
                    "confidence": float(triplet.score),
                }
            )
    return observations


def _load_relate_anything_from_locked_checkpoint(checkpoint_path: str, *, device: str) -> Any:
    from relsgg import RelateAnything  # type: ignore[import-not-found]
    from relsgg.checkpoint import build_model_from_ckpt, load_checkpoint  # type: ignore[import-not-found]
    from relsgg.scoring import ScoreContract  # type: ignore[import-not-found]
    from relsgg.text.student import resolve_student_path  # type: ignore[import-not-found]
    from relsgg.vocabulary import DEFAULT_PREDICATES  # type: ignore[import-not-found]

    ckpt = adapt_checkpoint_for_installed_relsgg(load_checkpoint(checkpoint_path))
    model = build_model_from_ckpt(ckpt, strict=True)  # ckpt already validated in adapt_*
    text_student = ckpt["args"].get("text_student") or "text_student.pt"
    text_student = resolve_student_path(text_student, near=checkpoint_path)
    relate_anything = RelateAnything(
        model,
        list(DEFAULT_PREDICATES),
        text_student,
        device=device,
    )
    relate_anything.set_vocabulary(relate_anything.predicates)
    contract = ScoreContract.for_checkpoint(checkpoint_path)
    if contract.is_calibrated:
        relate_anything._set_contract(contract)
    return relate_anything


def _box_region(box: np.ndarray, shape: tuple[int, ...]) -> dict[str, float]:
    height, width = shape[0], shape[1]
    x1, y1, x2, y2 = [float(v) for v in box.reshape(4)]
    return {
        "x": x1 / max(width, 1),
        "y": y1 / max(height, 1),
        "w": max(x2 - x1, 0) / max(width, 1),
        "h": max(y2 - y1, 0) / max(height, 1),
    }
