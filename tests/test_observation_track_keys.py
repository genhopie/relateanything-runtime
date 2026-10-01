from relateanything_runtime.pipeline.bytetrack_tracking import stable_track_key


def test_stable_track_key_format() -> None:
    assert stable_track_key(42) == "track-42"
    assert stable_track_key(42) == stable_track_key(42)
