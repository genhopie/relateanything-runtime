from relateanything_runtime.config_keys import LOCKED_ARTIFACT_PINS


def test_locked_pins_present() -> None:
    assert LOCKED_ARTIFACT_PINS["detector_revision"] == "c0605c367b39f7589694dfcb61046322dc07ac4a"
    assert len(LOCKED_ARTIFACT_PINS["relation_model_weight_sha256"]) == 64
