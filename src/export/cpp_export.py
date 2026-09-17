# -*- coding: utf-8 -*-
"""
cpp_export.py
==============
Sinh các file C/C++ và JSON mô tả model để nhúng vào firmware
ESP32-S3: mảng byte của model TFLite, và các hằng số cấu hình
(mean/std, scale/zero-point, threshold...).

Nguồn gốc trong notebook Colab:
- Cell 22.5 ("CELL 22.5 — KHÔI PHỤC CẤU HÌNH CHO CELL 23"): đọc lại
  interpreter/model TFLite để lấy input_scale, input_zero_point,
  output_scale, output_zero_point, kiểm tra shape/dtype. Các hằng số
  cấu hình khác đã nằm sẵn trong config.py.
- Cell 23: sinh fall_model_data.h/.cc, fall_model_config.h,
  fall_model_config.json.
"""

import json
from pathlib import Path

import numpy as np
import tensorflow as tf

from utils.config import (
    CLASS_NAMES,
    FALL,
    FEATURE_COUNT,
    NON_FALL,
    OUTPUT_DIR,
    SAMPLE_INTERVAL_MS,
    TARGET_HZ,
    WINDOW_SECONDS,
    WINDOW_SIZE,
    ensure_output_dir,
)

ARRAY_NAME = "g_fall_model_data"


def restore_quantization_params(tflite_path: Path):
    """
    (Cell 22.5) Đọc lại thông số quantization từ file .tflite, đồng
    thời kiểm tra shape/dtype input/output như notebook gốc.
    """
    if not tflite_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy model TFLite: {tflite_path}\n"
            "Hãy chạy lại bước export TFLite (Cell 21) trước."
        )

    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    input_scale, input_zero_point = input_details["quantization"]
    output_scale, output_zero_point = output_details["quantization"]

    if tuple(input_details["shape"]) != (1, WINDOW_SIZE, FEATURE_COUNT):
        raise RuntimeError(
            "Input model không đúng [1, 20, 4]. "
            f"Input hiện tại: {input_details['shape']}"
        )

    if input_details["dtype"] != np.int8:
        raise RuntimeError("Model input chưa phải INT8.")

    if output_details["dtype"] != np.int8:
        raise RuntimeError("Model output chưa phải INT8.")

    return {
        "input_details": input_details,
        "output_details": output_details,
        "input_scale": input_scale,
        "input_zero_point": input_zero_point,
        "output_scale": output_scale,
        "output_zero_point": output_zero_point,
    }


def validate_feature_mean_std(feature_mean, feature_std):
    """(Cell 22.5)"""
    feature_mean = np.asarray(feature_mean, dtype=np.float32)
    feature_std = np.asarray(feature_std, dtype=np.float32)

    if feature_mean.shape != (FEATURE_COUNT,):
        raise RuntimeError(
            f"feature_mean phải có shape (4,), nhưng hiện là {feature_mean.shape}."
        )

    if feature_std.shape != (FEATURE_COUNT,):
        raise RuntimeError(
            f"feature_std phải có shape (4,), nhưng hiện là {feature_std.shape}."
        )

    if np.any(feature_std <= 0):
        raise RuntimeError("feature_std chứa giá trị không hợp lệ.")

    return feature_mean, feature_std


def export_cpp_and_config(
    tflite_path: Path,
    feature_mean,
    feature_std,
    fall_threshold: float,
    high_fall_threshold: float,
    consecutive_required: int = 2,
    output_dir: Path = OUTPUT_DIR,
):
    """(Cell 23) — sinh toàn bộ file model/config cho firmware."""
    ensure_output_dir()
    input_details = quant["input_details"]
    output_details = quant["output_details"]
    input_scale = quant["input_scale"]
    input_zero_point = quant["input_zero_point"]
    output_scale = quant["output_scale"]
    output_zero_point = quant["output_zero_point"]

    feature_mean, feature_std = validate_feature_mean_std(feature_mean, feature_std)

    print("===== CẤU HÌNH ESP32-S3 =====")
    print("TARGET_HZ:", TARGET_HZ)
    print("SAMPLE_INTERVAL_MS:", SAMPLE_INTERVAL_MS)
    print("WINDOW_SIZE:", WINDOW_SIZE)
    print("FEATURE_COUNT:", FEATURE_COUNT)
    print("Input shape:", input_details["shape"])
    print("Input dtype:", input_details["dtype"])
    print("Input scale:", input_scale)
    print("Input zero point:", input_zero_point)
    print("Output scale:", output_scale)
    print("Output zero point:", output_zero_point)
    print("FALL_THRESHOLD:", fall_threshold)
    print("HIGH_FALL_THRESHOLD:", high_fall_threshold)
    print("CONSECUTIVE_REQUIRED:", consecutive_required)
    print("\nCELL 22.5: HOÀN THÀNH")

    model_header_path = output_dir / "fall_model_data.h"
    model_source_path = output_dir / "fall_model_data.cc"
    config_header_path = output_dir / "fall_model_config.h"
    config_json_path = output_dir / "fall_model_config.json"

    model_bytes = tflite_path.read_bytes()

    # ---- Header model ----
    model_header_path.write_text(
        f"""#pragma once

#include <cstddef>
#include <cstdint>

extern const unsigned char {ARRAY_NAME}[];
extern const unsigned int {ARRAY_NAME}_len;
""",
        encoding="utf-8",
    )

    # ---- Dữ liệu model (.cc) ----
    bytes_per_line = 12
    byte_lines = []

    for start in range(0, len(model_bytes), bytes_per_line):
        chunk = model_bytes[start : start + bytes_per_line]
        byte_lines.append(
            "    " + ", ".join(f"0x{value:02x}" for value in chunk) + ","
        )

    model_source_path.write_text(
        f"""#include "fall_model_data.h"

alignas(16) const unsigned char {ARRAY_NAME}[] = {{
{chr(10).join(byte_lines)}
}};

const unsigned int {ARRAY_NAME}_len =
    sizeof({ARRAY_NAME});
""",
        encoding="utf-8",
    )

    mean_cpp = ", ".join(f"{float(value):.9g}f" for value in feature_mean)
    std_cpp = ", ".join(f"{float(value):.9g}f" for value in feature_std)

    config_header_path.write_text(
        f"""#pragma once

#include <cstddef>
#include <cstdint>

constexpr int kSampleRateHz =
    {TARGET_HZ};

constexpr uint32_t kSampleIntervalMs =
    {SAMPLE_INTERVAL_MS};

constexpr int kWindowSize =
    {WINDOW_SIZE};

constexpr int kFeatureCount =
    {FEATURE_COUNT};

constexpr int kInferenceStrideSamples =
    {TARGET_HZ};

constexpr int kClassNonFall =
    {NON_FALL};

constexpr int kClassFall =
    {FALL};

constexpr float kFeatureMean[kFeatureCount] = {{
    {mean_cpp}
}};

constexpr float kFeatureStd[kFeatureCount] = {{
    {std_cpp}
}};

constexpr float kInputScale =
    {float(input_scale):.12g}f;

constexpr int kInputZeroPoint =
    {int(input_zero_point)};

constexpr float kOutputScale =
    {float(output_scale):.12g}f;

constexpr int kOutputZeroPoint =
    {int(output_zero_point)};

constexpr float kFallThreshold =
    {fall_threshold:.6f}f;

constexpr float kHighFallThreshold =
    {high_fall_threshold:.6f}f;

constexpr int kConsecutiveRequired =
    {consecutive_required};

constexpr size_t kTensorArenaSize =
    96 * 1024;
""",
        encoding="utf-8",
    )

    deployment_config = {
        "model_name": "safewatch_person_a_5hz_int8",
        "personalized_for": "PERSON_A",
        "sample_rate_hz": TARGET_HZ,
        "sample_interval_ms": SAMPLE_INTERVAL_MS,
        "window_seconds": WINDOW_SECONDS,
        "window_size": WINDOW_SIZE,
        "inference_stride_samples": TARGET_HZ,
        "features": [
            "magnitude_g",
            "abs_magnitude_minus_1g",
            "delta_magnitude_g",
            "acceleration_vector_angle_change_rad",
        ],
        "feature_mean": feature_mean.tolist(),
        "feature_std": feature_std.tolist(),
        "input_shape": [int(value) for value in input_details["shape"]],
        "output_shape": [int(value) for value in output_details["shape"]],
        "input_scale": float(input_scale),
        "input_zero_point": int(input_zero_point),
        "output_scale": float(output_scale),
        "output_zero_point": int(output_zero_point),
        "class_names": CLASS_NAMES,
        "fall_threshold": fall_threshold,
        "high_fall_threshold": high_fall_threshold,
        "consecutive_required": consecutive_required,
    }

    config_json_path.write_text(
        json.dumps(deployment_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Đã tạo:")
    print("-", model_header_path)
    print("-", model_source_path)
    print("-", config_header_path)
    print("-", config_json_path)

    return {
        "model_header_path": model_header_path,
        "model_source_path": model_source_path,
        "config_header_path": config_header_path,
        "config_json_path": config_json_path,
    }
