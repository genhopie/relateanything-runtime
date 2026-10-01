import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RELATEANYTHING_RUN_INFERENCE_E2E") != "1",
    reason="Set RELATEANYTHING_RUN_INFERENCE_E2E=1 with artifacts and upstream installed",
)


def test_inference_e2e_placeholder() -> None:
    """Executed only when explicit E2E gate and artifacts are present."""
    artifact_root = os.environ.get("RELATEANYTHING_ARTIFACT_ROOT")
    upstream = os.environ.get("RELATEANYTHING_UPSTREAM_PATH")
    assert artifact_root and upstream
    from pathlib import Path

    assert (Path(artifact_root) / "relation" / "model.pth").is_file()
    assert (Path(artifact_root) / "detector" / "model.safetensors").is_file()
