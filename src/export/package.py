# -*- coding: utf-8 -*-
"""
package.py
===========
Sinh README hướng dẫn tích hợp firmware và đóng gói toàn bộ file
xuất ra (.keras, .tflite, .h/.cc/.cpp, .ino, README) thành 1 file
ZIP để tải về / triển khai.

Nguồn gốc trong notebook Colab: Cell 26

LƯU Ý: notebook gốc chạy trên Colab và gọi
`google.colab.files.download(...)` ở cuối để tự động tải file ZIP
xuống máy người dùng qua trình duyệt. Trên script local, bước này
được bỏ qua (không có trình duyệt) — file ZIP vẫn được tạo ra tại
PACKAGE_PATH, người dùng tự copy/tải theo nhu cầu.
"""

import zipfile
from pathlib import Path

from utils.config import (
    CLASS_NAMES,
    CONTENT_DIR,
    PACKAGE_PATH,
    TARGET_HZ,
    WINDOW_SECONDS,
    WINDOW_SIZE,
    FEATURE_COUNT,
    ensure_output_dir,
)


def write_readme(
    output_dir: Path,
    fall_threshold: float,
    high_fall_threshold: float,
    consecutive_required: int,
):
    """(Cell 26 — phần README)"""
    output_dir.mkdir(parents=True, exist_ok=True)
    readme_path = output_dir / "README_FIRMWARE.md"

    readme_path.write_text(
        f"""SAFEWATCH PERSON A — MODEL 5 HZ

MODEL
- Input: [1, {WINDOW_SIZE}, {FEATURE_COUNT}]
- Input dtype: INT8
- Output: [NON_FALL, FALL]
- Tần số: {TARGET_HZ} Hz
- Cửa sổ: {WINDOW_SECONDS} giây
- Chạy inference lại mỗi 1 giây

FEATURES
1. magnitude_g
2. abs(magnitude_g - 1g)
3. delta_magnitude_g
4. acceleration vector angle change

THRESHOLD
- FALL threshold: {fall_threshold:.4f}
- HIGH FALL threshold: {high_fall_threshold:.4f}
- Consecutive windows: {consecutive_required}

FILE ESP32
- fall_model_data.h
- fall_model_data.cc
- fall_model_config.h
- fall_inference.h
- fall_inference.cpp
- SafeWatch_Fall_Detector.ino

BẮT BUỘC
1. Nối ReadQmi8658AccelG() với driver QMI8658.
2. Dữ liệu đưa vào phải ở đơn vị g.
3. Nối ShowStatusOnDisplay() với LCD/LVGL.
4. Nối SendFallToBackend() với HTTPS API.
5. Không lưu Telegram Bot Token trên ESP32.
6. Backend C# chịu trách nhiệm gửi Telegram.

Nếu AllocateTensors() thất bại:
- tăng kTensorArenaSize lên 128 * 1024.
""",
        encoding="utf-8",
    )

    return readme_path


def build_package_zip(
    finetuned_model_path: Path,
    tflite_path: Path,
    model_header_path: Path,
    model_source_path: Path,
    config_header_path: Path,
    config_json_path: Path,
    inference_header_path: Path,
    inference_source_path: Path,
    arduino_template_path: Path,
    readme_path: Path,
    package_path: Path = PACKAGE_PATH,
):
    """(Cell 26 — đóng gói ZIP)"""
    files_to_package = [
        finetuned_model_path,
        tflite_path,
        model_header_path,
        model_source_path,
        config_header_path,
        config_json_path,
        inference_header_path,
        inference_source_path,
        arduino_template_path,
        readme_path,
    ]

    with zipfile.ZipFile(
        package_path, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        for file_path in files_to_package:
            if Path(file_path).exists():
                zip_file.write(file_path, arcname=Path(file_path).name)

    print("Đã tạo package:", package_path)
    print("Kích thước:", round(package_path.stat().st_size / 1024, 2), "KB")

    return package_path


def maybe_download_in_colab(package_path: Path):
    """
    (Cell 26 — cuối cell) Chỉ hoạt động khi chạy trong Google Colab.
    Trên script local, hàm này bỏ qua (no-op) và chỉ in đường dẫn.
    """
    try:
        from google.colab import files  # type: ignore

        files.download(str(package_path))
    except ImportError:
        print(
            "Không chạy trong Google Colab — bỏ qua bước tải xuống "
            f"tự động. File package đã sẵn sàng tại: {package_path}"
        )
