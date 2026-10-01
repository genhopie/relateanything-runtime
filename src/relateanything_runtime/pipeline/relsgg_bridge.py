from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from relateanything_runtime.config import GovernedProcessingConfig
from relateanything_runtime.pipeline.inference import InferenceUnavailableError, verify_bundled_artifacts


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
    model = RelateAnything.from_pretrained(str(relation_dir), device=os.environ.get("RELATEANYTHING_DEVICE", "cpu"))

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
    observations: list[dict[str, Any]] = []

    for frame_ordinal, frame in frames:
        boxes = _detect_boxes(frame, config)
        if boxes.shape[0] < 2:
            continue
        triplets = model.predict(frame, boxes, topk=max_objects)
        start_ms = int((frame_ordinal / max(fps, 1.0)) * 1000)
        end_ms = start_ms + config.require_int("content_visual_inference_sampling_interval_ms")
        for triplet in triplets:
            if float(triplet.score) < min_relation:
                continue
            observations.append(
                {
                    "start_time_ms": start_ms,
                    "end_time_ms": end_ms,
                    "frame_ordinal": frame_ordinal,
                    "subject_track_key": f"track-{triplet.subject_idx}-{frame_ordinal}",
                    "subject_label": triplet.subject_label,
                    "subject_region": _box_region(triplet.subject_box, frame.shape),
                    "predicate": triplet.predicate,
                    "object_track_key": f"track-{triplet.object_idx}-{frame_ordinal}",
                    "object_label": triplet.object_label,
                    "object_region": _box_region(triplet.object_box, frame.shape),
                    "confidence": float(triplet.score),
                }
            )
    return observations


def _box_region(box: np.ndarray, shape: tuple[int, ...]) -> dict[str, float]:
    height, width = shape[0], shape[1]
    x1, y1, x2, y2 = [float(v) for v in box.reshape(4)]
    return {
        "x": x1 / max(width, 1),
        "y": y1 / max(height, 1),
        "w": max(x2 - x1, 0) / max(width, 1),
        "h": max(y2 - y1, 0) / max(height, 1),
    }


def _detect_boxes(frame: np.ndarray, config: GovernedProcessingConfig) -> np.ndarray:
    """Grounding DINO open-vocabulary detection using bundled detector weights."""
    try:
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor  # type: ignore[import-not-found]
        import torch
    except ImportError:
        raise InferenceUnavailableError("detector_stack_missing") from None

    root = Path(os.environ["RELATEANYTHING_ARTIFACT_ROOT"]) / "detector"
    processor = AutoProcessor.from_pretrained(str(root))
    model = AutoModelForZeroShotObjectDetection.from_pretrained(str(root))
    device = os.environ.get("RELATEANYTHING_DEVICE", "cpu")
    model.to(device)

    vocabulary_raw = config.require_str("content_visual_inference_relation_vocabulary")
    try:
        labels = json.loads(vocabulary_raw)
    except json.JSONDecodeError:
        labels = [part.strip() for part in vocabulary_raw.split(",") if part.strip()]
    text_labels = [str(label) for label in labels[:10]] or ["object"]
    min_conf = config.require_float("content_visual_inference_min_detector_confidence")
    max_per_frame = config.require_int("content_visual_inference_max_objects_per_frame")

    import cv2

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    inputs = processor(images=rgb, text=text_labels, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    results = processor.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        box_threshold=min_conf,
        text_threshold=min_conf,
        target_sizes=[(rgb.shape[0], rgb.shape[1])],
    )[0]
    boxes = results.get("boxes")
    if boxes is None or len(boxes) == 0:
        return np.zeros((0, 4), dtype=np.float32)
    array = boxes[:max_per_frame].detach().cpu().numpy().astype(np.float32)
    return array.reshape(-1, 4)
