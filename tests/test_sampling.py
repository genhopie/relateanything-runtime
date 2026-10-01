from relateanything_runtime.pipeline.sampling import select_frame_indices


def test_bounded_frame_selection() -> None:
    indices = select_frame_indices(
        10_000,
        30.0,
        sampling_interval_ms=1000,
        max_frames=5,
        scene_change_threshold=0.2,
        motion_threshold=0.1,
        object_change_threshold=0.1,
        max_segments=3,
    )
    assert len(indices) <= 5
    assert all(index < 10_000 for index in indices)
