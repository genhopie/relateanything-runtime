from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from relateanything_runtime.config import GovernedProcessingConfig
from relateanything_runtime.config_keys import LOCKED_ARTIFACT_PINS
from relateanything_runtime.pipeline.inference import InferenceUnavailableError

_GROUNDING_DINO_TEXT_CONFIG_REGISTERED = False


def _ensure_grounding_dino_text_config_registered() -> None:
    global _GROUNDING_DINO_TEXT_CONFIG_REGISTERED
    if _GROUNDING_DINO_TEXT_CONFIG_REGISTERED:
        return
    from transformers.models.auto.configuration_auto import CONFIG_MAPPING
    from transformers.models.bert.configuration_bert import BertConfig

    class GroundingDinoTextPrenetConfig(BertConfig):
        model_type = "grounding-dino-text-prenet"

    CONFIG_MAPPING.register("grounding-dino-text-prenet", GroundingDinoTextPrenetConfig, exist_ok=True)
    _GROUNDING_DINO_TEXT_CONFIG_REGISTERED = True


class GroundingDinoDetector:
    """Grounding DINO detector using locked local artifact revision only."""

    def __init__(self, config: GovernedProcessingConfig) -> None:
        try:
            from transformers import AutoConfig, AutoModelForZeroShotObjectDetection, AutoProcessor
            from transformers.models.bert.configuration_bert import BertConfig
            import torch
        except ImportError:
            raise InferenceUnavailableError("detector_stack_missing") from None

        root = Path(os.environ["RELATEANYTHING_ARTIFACT_ROOT"]) / "detector"
        if not root.is_dir():
            raise InferenceUnavailableError("detector_artifacts_missing")

        revision = config.require_str("content_visual_inference_detector_revision")
        if revision != LOCKED_ARTIFACT_PINS["detector_revision"]:
            raise InferenceUnavailableError("detector_revision_mismatch")

        _ensure_grounding_dino_text_config_registered()
        artifact_root = str(root)
        self._processor = AutoProcessor.from_pretrained(artifact_root)
        model_config = AutoConfig.from_pretrained(artifact_root)
        model_config.text_config = BertConfig()
        self._model = AutoModelForZeroShotObjectDetection.from_pretrained(artifact_root, config=model_config)
        self._device = os.environ.get("RELATEANYTHING_DEVICE", "cpu")
        self._model.to(self._device)
        self._config = config
        self._torch = torch

    def detect(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        import cv2

        vocabulary_raw = self._config.require_str("content_visual_inference_relation_vocabulary")
        try:
            labels = json.loads(vocabulary_raw)
        except json.JSONDecodeError:
            labels = [part.strip() for part in vocabulary_raw.split(",") if part.strip()]
        text_labels = [str(label) for label in labels[:10]] or ["object"]
        min_conf = self._config.require_float("content_visual_inference_min_detector_confidence")
        max_per_frame = self._config.require_int("content_visual_inference_max_objects_per_frame")

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        inputs = self._processor(images=rgb, text=text_labels, return_tensors="pt").to(self._device)
        with self._torch.no_grad():
            outputs = self._model(**inputs)
        results = self._processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=min_conf,
            text_threshold=min_conf,
            target_sizes=[(rgb.shape[0], rgb.shape[1])],
        )[0]
        boxes = results.get("boxes")
        scores = results.get("scores")
        if boxes is None or len(boxes) == 0:
            return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32)
        box_array = boxes[:max_per_frame].detach().cpu().numpy().astype(np.float32).reshape(-1, 4)
        score_array = (
            scores[:max_per_frame].detach().cpu().numpy().astype(np.float32).reshape(-1)
            if scores is not None
            else np.ones((box_array.shape[0],), dtype=np.float32)
        )
        return box_array, score_array


_DETECTOR_INSTANCE: GroundingDinoDetector | None = None
_DETECTOR_KEY: str | None = None


def get_grounding_dino_detector(config: GovernedProcessingConfig) -> GroundingDinoDetector:
    global _DETECTOR_INSTANCE, _DETECTOR_KEY
    key = f"{os.environ.get('RELATEANYTHING_ARTIFACT_ROOT', '')}:{config.require_str('content_visual_inference_detector_revision')}"
    if _DETECTOR_INSTANCE is None or _DETECTOR_KEY != key:
        _DETECTOR_INSTANCE = GroundingDinoDetector(config)
        _DETECTOR_KEY = key
    return _DETECTOR_INSTANCE
