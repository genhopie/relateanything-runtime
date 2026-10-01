from __future__ import annotations

import cv2
import numpy as np


def select_frame_indices(
    frame_count: int,
    fps: float,
    *,
    sampling_interval_ms: int,
    max_frames: int,
    scene_change_threshold: float,
    motion_threshold: float,
    object_change_threshold: float,
    max_segments: int,
) -> list[int]:
    if frame_count <= 0 or max_frames <= 0:
        return []
    if sampling_interval_ms <= 0:
        return []
    step = max(1, int(round((sampling_interval_ms / 1000.0) * max(fps, 1.0))))
    indices = list(range(0, frame_count, step))
    if len(indices) > max_frames:
        indices = indices[:max_frames]
    if max_segments > 0 and len(indices) > max_segments:
        stride = max(1, len(indices) // max_segments)
        indices = indices[::stride][:max_segments]
    _ = (scene_change_threshold, motion_threshold, object_change_threshold)
    return indices


def read_video_metadata(path: str) -> tuple[int, float]:
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise ValueError("video_open_failed")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    capture.release()
    return frame_count, fps


def load_frames(path: str, indices: list[int]) -> list[tuple[int, np.ndarray]]:
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise ValueError("video_open_failed")
    frames: list[tuple[int, np.ndarray]] = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        frames.append((index, frame))
    capture.release()
    return frames
