import os

import cv2
import numpy as np
import pytest

from relateanything_runtime.config import GovernedProcessingConfig, parse_submit_body
from relateanything_runtime.pipeline.inference import run_relation_pipeline
from tests.test_config_fixture import VALID_SUBMIT_BODY

pytestmark = pytest.mark.skipif(
    os.environ.get("RELATEANYTHING_RUN_INFERENCE_E2E") != "1",
    reason="Set RELATEANYTHING_RUN_INFERENCE_E2E=1 with artifacts and relsgg installed",
)


def _governed_config() -> GovernedProcessingConfig:
    _, _, _, _, config = parse_submit_body(VALID_SUBMIT_BODY)
    return config


def test_inference_smoke_produces_observations_and_provenance() -> None:
    assert os.environ.get("RELATEANYTHING_ARTIFACT_ROOT")
    assert os.environ.get("RELATEANYTHING_UPSTREAM_PATH")
    config = _governed_config()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.rectangle(frame, (40, 40), (120, 120), (255, 255, 255), thickness=-1)
    cv2.rectangle(frame, (180, 140), (260, 220), (200, 200, 200), thickness=-1)
    frames = [(0, frame), (30, frame)]
    observations = run_relation_pipeline(frames, config, fps=30.0)
    assert isinstance(observations, list)
    import re

    track_key = re.compile(r"^track-\d+$")
    for row in observations:
        assert track_key.match(row["subject_track_key"])
        assert track_key.match(row["object_track_key"])
