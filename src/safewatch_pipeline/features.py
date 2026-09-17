# -*- coding: utf-8 -*-
"""
features.py
============
Đọc file CSV gia tốc, chuẩn hóa đơn vị, resample về TARGET_HZ và
sinh ra 4 feature dùng cho model.

Nguồn gốc trong notebook Colab:
- Cell 4 / Cell 5 (hai cell trùng nội dung nhau trong notebook gốc):
    SessionRecord, normalize_column_name, parse_list_cell,
    read_three_axis_csv, accel_to_g, ensure_finite
- Cell 5A (định nghĩa resample & feature):
    resample_accel, raw_accel_to_features
"""

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import FEATURE_COUNT, GRAVITY, TARGET_HZ, WINDOW_SIZE


# ---------------------------------------------------------------------------
# Cell 4 / Cell 5
# ---------------------------------------------------------------------------
@dataclass
class SessionRecord:
    session_id: str
    source: str
    activity: str
    label: int
    accel_g: np.ndarray
    user_id: str
    path: str


def normalize_column_name(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def parse_list_cell(value):
    """
    Hỗ trợ trường hợp một cell CSV chứa cả list.
    (Cell 4/5)
    """
    import ast

    if isinstance(value, (list, tuple, np.ndarray)):
        return np.asarray(value, dtype=np.float32)

    if not isinstance(value, str):
        return None

    text = value.strip()

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (list, tuple, np.ndarray)):
            return np.asarray(parsed, dtype=np.float32)
    except (ValueError, SyntaxError):
        pass

    cleaned = text.strip("[]()")
    array = np.fromstring(cleaned.replace(";", ","), sep=",")

    if array.size <= 1:
        array = np.fromstring(cleaned, sep=" ")

    if array.size > 1:
        return array.astype(np.float32)

    return None


def read_three_axis_csv(path):
    """
    Đọc linh hoạt file accelerometer của WEDA. (Cell 4/5)

    Hỗ trợ:
    - x, y, z;
    - ax, ay, az;
    - accel_x, accel_y, accel_z;
    - file không có header;
    - file có timestamp ở cột đầu.
    """
    read_attempts = []

    configurations = [
        {},
        {"sep": None, "engine": "python"},
        {"header": None},
        {"header": None, "sep": None, "engine": "python"},
    ]

    for configuration in configurations:
        try:
            dataframe = pd.read_csv(path, **configuration)
            read_attempts.append(dataframe)
        except Exception:
            continue

    axis_aliases = {
        "x": {"x", "ax", "accx", "accelx", "accelerationx", "accelerometerx", "xaxis"},
        "y": {"y", "ay", "accy", "accely", "accelerationy", "accelerometery", "yaxis"},
        "z": {"z", "az", "accz", "accelz", "accelerationz", "accelerometerz", "zaxis"},
    }

    for dataframe in read_attempts:
        if dataframe.empty:
            continue

        normalized_names = {
            column: normalize_column_name(column) for column in dataframe.columns
        }

        axis_columns = {}
        for axis_name, aliases in axis_aliases.items():
            for original_name, normalized_name in normalized_names.items():
                if normalized_name in aliases:
                    axis_columns[axis_name] = original_name
                    break

        # Đã tìm được x/y/z theo tên cột
        if len(axis_columns) == 3:
            selected_columns = [axis_columns["x"], axis_columns["y"], axis_columns["z"]]

            # Trường hợp một dòng chứa ba list
            if len(dataframe) == 1:
                parsed_columns = [
                    parse_list_cell(dataframe[column].iloc[0])
                    for column in selected_columns
                ]

                if all(value is not None for value in parsed_columns):
                    minimum_length = min(len(value) for value in parsed_columns)
                    return np.column_stack(
                        [value[:minimum_length] for value in parsed_columns]
                    ).astype(np.float32)

            numeric = dataframe[selected_columns].apply(pd.to_numeric, errors="coerce")
            numeric = numeric.dropna()

            if len(numeric) >= 2:
                return numeric.to_numpy(dtype=np.float32)

        # Fallback cho file không có header
        numeric_dataframe = dataframe.apply(pd.to_numeric, errors="coerce")

        valid_columns = []
        for column in numeric_dataframe.columns:
            column_name = normalize_column_name(column)

            if any(
                token in column_name
                for token in ("time", "timestamp", "index", "sample", "sequence")
            ):
                continue

            valid_ratio = numeric_dataframe[column].notna().mean()
            if valid_ratio >= 0.90:
                valid_columns.append(column)

        if len(valid_columns) >= 3:
            # Nếu có timestamp ở cột đầu, ba cột cuối thường là x/y/z
            selected_columns = valid_columns[-3:]
            result = (
                numeric_dataframe[selected_columns].dropna().to_numpy(dtype=np.float32)
            )

            if len(result) >= 2:
                return result

    raise ValueError(f"Không đọc được ba trục gia tốc: {path}")


def accel_to_g(accel, unit="auto"):
    """
    Tự nhận diện đơn vị g hoặc m/s². (Cell 4/5)
    """
    accel = np.asarray(accel, dtype=np.float32)
    magnitude = np.linalg.norm(accel, axis=1)
    median_magnitude = float(np.nanmedian(magnitude))

    if unit == "g":
        return accel, "g"

    if unit == "m_s2":
        return accel / GRAVITY, "m_s2"

    if unit != "auto":
        raise ValueError(f"Đơn vị không hợp lệ: {unit}")

    # Dữ liệu đã ở đơn vị g
    if 0.20 <= median_magnitude <= 3.50:
        return accel, "g"

    # Dữ liệu đang ở m/s²
    if 4.00 <= median_magnitude <= 25.00:
        return accel / GRAVITY, "m_s2"

    raise ValueError(
        "Không xác định được đơn vị gia tốc. "
        f"Median magnitude={median_magnitude:.4f}"
    )


def ensure_finite(array, name):
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} chứa NaN hoặc Infinity.")


# ---------------------------------------------------------------------------
# Cell 5A — Resample & feature engineering
# ---------------------------------------------------------------------------
def resample_accel(timestamps_ms, accel, target_hz=TARGET_HZ):
    """
    Resample dữ liệu gia tốc theo timestamp về đúng target_hz. (Cell 5A)

    Input:
        timestamps_ms: mảng timestamp đơn vị millisecond
        accel: mảng shape (N, 3), gồm ax, ay, az
        target_hz: tần số đích, mặc định 5 Hz

    Output:
        mảng gia tốc shape (M, 3)
    """
    timestamps_ms = np.asarray(timestamps_ms, dtype=np.float64)
    accel = np.asarray(accel, dtype=np.float32)

    if timestamps_ms.ndim != 1:
        raise ValueError("timestamps_ms phải là mảng một chiều.")

    if accel.ndim != 2 or accel.shape[1] != 3:
        raise ValueError("accel phải có shape (N, 3).")

    if len(timestamps_ms) != len(accel):
        raise ValueError("Số timestamp không bằng số mẫu gia tốc.")

    if len(timestamps_ms) < 2:
        return np.empty((0, 3), dtype=np.float32)

    # Loại NaN và Infinity
    valid_mask = np.isfinite(timestamps_ms) & np.all(np.isfinite(accel), axis=1)
    timestamps_ms = timestamps_ms[valid_mask]
    accel = accel[valid_mask]

    if len(timestamps_ms) < 2:
        return np.empty((0, 3), dtype=np.float32)

    # Sắp xếp theo timestamp
    sort_indices = np.argsort(timestamps_ms)
    timestamps_ms = timestamps_ms[sort_indices]
    accel = accel[sort_indices]

    # Loại các timestamp trùng nhau
    unique_timestamps, unique_indices = np.unique(timestamps_ms, return_index=True)
    accel = accel[unique_indices]

    if len(unique_timestamps) < 2:
        return np.empty((0, 3), dtype=np.float32)

    # Đưa timestamp về giây, bắt đầu từ 0
    time_seconds = (unique_timestamps - unique_timestamps[0]) / 1000.0
    duration_seconds = float(time_seconds[-1])
    target_interval = 1.0 / float(target_hz)

    target_times = np.arange(
        0.0, duration_seconds + 1e-9, target_interval, dtype=np.float64
    )

    # Không đủ 20 mẫu để tạo cửa sổ 4 giây
    if len(target_times) < WINDOW_SIZE:
        return np.empty((0, 3), dtype=np.float32)

    # Nội suy riêng từng trục
    accel_resampled = np.column_stack(
        [np.interp(target_times, time_seconds, accel[:, axis]) for axis in range(3)]
    )

    return accel_resampled.astype(np.float32)


def raw_accel_to_features(accel_g):
    """
    Chuyển ax, ay, az thành 4 feature. (Cell 5A)

    Input:
        accel_g shape (N, 3), đơn vị g

    Output:
        shape (N, 4)

    Feature:
        0. magnitude_g
        1. abs(magnitude_g - 1g)
        2. delta_magnitude_g
        3. angle_change_rad
    """
    accel_g = np.asarray(accel_g, dtype=np.float32)

    if accel_g.ndim != 2 or accel_g.shape[1] != 3:
        raise ValueError("accel_g phải có shape (N, 3).")

    if len(accel_g) == 0:
        return np.empty((0, FEATURE_COUNT), dtype=np.float32)

    if not np.all(np.isfinite(accel_g)):
        raise ValueError("accel_g chứa NaN hoặc Infinity.")

    # Độ lớn vector gia tốc
    magnitude = np.linalg.norm(accel_g, axis=1)

    # Mức lệch khỏi trọng lực 1g
    deviation_from_gravity = np.abs(magnitude - 1.0)

    # Mức thay đổi magnitude giữa hai mẫu
    delta_magnitude = np.zeros(len(accel_g), dtype=np.float32)
    if len(accel_g) > 1:
        delta_magnitude[1:] = np.diff(magnitude)

    # Góc thay đổi giữa hai vector liên tiếp
    angle_change = np.zeros(len(accel_g), dtype=np.float32)
    if len(accel_g) > 1:
        previous_vectors = accel_g[:-1]
        current_vectors = accel_g[1:]

        previous_norms = np.linalg.norm(previous_vectors, axis=1)
        current_norms = np.linalg.norm(current_vectors, axis=1)

        denominator = previous_norms * current_norms
        denominator = np.maximum(denominator, 1e-6)

        dot_products = np.sum(previous_vectors * current_vectors, axis=1)
        cosine_values = dot_products / denominator
        cosine_values = np.clip(cosine_values, -1.0, 1.0)

        angle_change[1:] = np.arccos(cosine_values)

    features = np.column_stack(
        [magnitude, deviation_from_gravity, delta_magnitude, angle_change]
    )
    features = features.astype(np.float32)

    if not np.all(np.isfinite(features)):
        raise ValueError("Feature tạo ra chứa NaN hoặc Infinity.")

    return features
