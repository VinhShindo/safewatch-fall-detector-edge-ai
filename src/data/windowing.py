# -*- coding: utf-8 -*-
"""
windowing.py
============
Cắt các session thành cửa sổ cố định (WINDOW_SIZE mẫu) và sinh
feature cho từng cửa sổ.

Nguồn gốc trong notebook Colab:
- Cell 9.5 ("CELL 9.5 — CẤU HÌNH CẮT CỬA SỔ"): các hằng số cấu hình
  đã được chuyển vào config.py.
- Cell 10: clip_window_start, get_fall_window_starts,
  get_nonfall_window_starts, sessions_to_windows.
"""

import numpy as np

from utils.config import FALL, INFERENCE_STRIDE_SAMPLES, WINDOW_SIZE
from features.temporal_features import ensure_finite, raw_accel_to_features


def clip_window_start(session_length, start_index):
    """(Cell 10)"""
    return max(0, min(start_index, session_length - WINDOW_SIZE))


def get_fall_window_starts(accel_g, training):
    """(Cell 10)"""
    magnitude = np.linalg.norm(accel_g, axis=1)

    # Tìm điểm lệch khỏi gravity mạnh nhất
    impact_score = np.abs(magnitude - 1.0)
    impact_index = int(np.argmax(impact_score))

    center_start = clip_window_start(len(accel_g), impact_index - WINDOW_SIZE // 2)

    # Tạo thêm một ít cửa sổ dịch trái/phải
    offsets = [-2, 0, 2] if training else [0]

    starts = {
        clip_window_start(len(accel_g), center_start + offset) for offset in offsets
    }

    return sorted(starts)


def get_nonfall_window_starts(session_length, max_windows):
    """(Cell 10)"""
    if session_length < WINDOW_SIZE:
        return []

    possible_starts = list(
        range(0, session_length - WINDOW_SIZE + 1, INFERENCE_STRIDE_SAMPLES)
    )

    if not possible_starts:
        return [0]

    if len(possible_starts) <= max_windows:
        return possible_starts

    selected_indices = np.linspace(0, len(possible_starts) - 1, max_windows, dtype=int)

    return sorted({possible_starts[index] for index in selected_indices})


def sessions_to_windows(sessions, training, max_nonfall_windows):
    """(Cell 10)"""
    X = []
    y = []

    session_ids = []
    activities = []
    sources = []

    for record in sessions:
        accel_g = record.accel_g

        if len(accel_g) < WINDOW_SIZE:
            continue

        if record.label == FALL:
            window_starts = get_fall_window_starts(accel_g, training=training)
        else:
            window_starts = get_nonfall_window_starts(
                session_length=len(accel_g),
                max_windows=max_nonfall_windows,
            )

        for start in window_starts:
            raw_window = accel_g[start : start + WINDOW_SIZE]

            if len(raw_window) != WINDOW_SIZE:
                continue

            feature_window = raw_accel_to_features(raw_window)
            ensure_finite(feature_window, record.session_id)

            X.append(feature_window)
            y.append(record.label)

            session_ids.append(record.session_id)
            activities.append(record.activity)
            sources.append(record.source)

    return (
        np.asarray(X, dtype=np.float32),
        np.asarray(y, dtype=np.int64),
        np.asarray(session_ids, dtype=object),
        np.asarray(activities, dtype=object),
        np.asarray(sources, dtype=object),
    )
