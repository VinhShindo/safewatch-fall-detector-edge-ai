# -*- coding: utf-8 -*-
"""
config.py
=========
Toàn bộ hằng số / cấu hình dùng chung cho pipeline.

Nguồn gốc trong notebook Colab:
- Cell 5A  : TARGET_HZ, WINDOW_SECONDS, WINDOW_SIZE, FEATURE_COUNT, GRAVITY
- Cell 5.5 : NON_FALL, FALL, CLASS_NAMES, SEED, các đường dẫn CONTENT_DIR/...
- Cell 9.5 : INFERENCE_STRIDE_SAMPLES, MAX_*_NONFALL_WINDOWS_*
- Cell 15.5: QMI_AUGMENT_COPIES, WEDA_REPLAY_RATIO
- Cell 22.5: SAMPLE_INTERVAL_MS

Việc gom các hằng số bị khai báo rải rác/khai báo lại nhiều lần
trong notebook (do các cell "khôi phục cấu hình") vào một nơi
duy nhất giúp pipeline chạy tuần tự bằng script mà không cần các
bước "chạy lại cell trước" thủ công.
"""

from pathlib import Path

import os
from datetime import datetime

import tensorflow as tf
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"

with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
    _CONFIG = yaml.safe_load(config_file) or {}


def _path_config(section, key):
    return (CONFIG_PATH.parent / _CONFIG[section][key]).resolve()


def _configure_runtime():
    runtime = _CONFIG["runtime"]
    intra_threads = int(runtime["intra_op_parallelism_threads"])
    inter_threads = int(runtime["inter_op_parallelism_threads"])
    tf.config.threading.set_intra_op_parallelism_threads(intra_threads)
    tf.config.threading.set_inter_op_parallelism_threads(inter_threads)

    if not bool(runtime["use_gpu"]):
        tf.config.set_visible_devices([], "GPU")


_configure_runtime()

# =========================================================
# NHÃN NHỊ PHÂN (Cell 5.5)
# =========================================================
NON_FALL = 0
FALL = 1
CLASS_NAMES = ["NON_FALL", "FALL"]

# =========================================================
# SEED (Cell 5.5 / Cell 15.5)
# =========================================================
SEED = int(_CONFIG["runtime"]["seed"])
USE_GPU = bool(_CONFIG["runtime"]["use_gpu"])

# =========================================================
# CẤU HÌNH TÍN HIỆU / CỬA SỔ (Cell 5A)
# =========================================================
TARGET_HZ = int(_CONFIG["signal"]["target_hz"])
WINDOW_SECONDS = float(_CONFIG["signal"]["window_seconds"])
WINDOW_SIZE = int(TARGET_HZ * WINDOW_SECONDS)  # 20 mẫu
FEATURE_COUNT = int(_CONFIG["signal"]["feature_count"])
GRAVITY = float(_CONFIG["signal"]["gravity"])

# Cell 22.5
SAMPLE_INTERVAL_MS = int(1000 / TARGET_HZ)  # 200 ms

# =========================================================
# CẤU HÌNH CẮT CỬA SỔ (Cell 9.5)
# =========================================================
INFERENCE_STRIDE_SAMPLES = int(
    _CONFIG["windowing"]["inference_stride_samples"]
)

# WEDA: có thể lấy nhiều cửa sổ hơn vì dữ liệu lớn
MAX_WEDA_NONFALL_WINDOWS_TRAIN = int(
    _CONFIG["windowing"]["max_weda_nonfall_windows_train"]
)
MAX_WEDA_NONFALL_WINDOWS_EVAL = int(
    _CONFIG["windowing"]["max_weda_nonfall_windows_eval"]
)

# QMI của người A: hạn chế số cửa sổ/session
# để tránh một session tạo quá nhiều mẫu gần giống nhau
MAX_QMI_NONFALL_WINDOWS_TRAIN = int(
    _CONFIG["windowing"]["max_qmi_nonfall_windows_train"]
)
MAX_QMI_NONFALL_WINDOWS_EVAL = int(
    _CONFIG["windowing"]["max_qmi_nonfall_windows_eval"]
)

# =========================================================
# CẤU HÌNH FINE-TUNE PERSON_A (Cell 15.5)
# =========================================================
# Mỗi cửa sổ QMI gốc tạo thêm 5 bản augmentation
QMI_AUGMENT_COPIES = int(_CONFIG["fine_tuning"]["qmi_augment_copies"])

# Tập fine-tune gồm khoảng:
# 70% dữ liệu QMI cá nhân
# 30% dữ liệu WEDA replay
WEDA_REPLAY_RATIO = float(_CONFIG["fine_tuning"]["weda_replay_ratio"])

# =========================================================
# QMI FILE -> ACTIVITY (Cell 7)
# =========================================================
QMI_FILE_ACTIVITY = {
    "fall_left": "Fall_Left",
    "fall_right": "Fall_Right",
    "fall_back": "Fall_Back",
    "fall_front": "Fall_Front",
    "walking": "Walking",
    "sitting": "Sitting",
    "standing": "Standing",
    "jumping": "Jumping",
    "doing": "Other",
}

# =========================================================
# ĐƯỜNG DẪN (Cell 3 / Cell 5.5)
# =========================================================
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
QMI_DATA_DIR = _path_config("paths", "qmi_dir")
WEDA_5HZ_DIR = _path_config("paths", "weda_dir")
MERGE_DIR = _path_config("paths", "merge_dir")
OUTPUT_DIR = _path_config("paths", "output_root")
NEXT_DAY_DIR = _path_config("paths", "next_day_dir")
RUN_ID = os.environ.get(
    "SAFEWATCH_RUN_ID", datetime.now().strftime("%Y%m%d_%H%M%S_%f")
)
OUTPUT_DIR = OUTPUT_DIR / RUN_ID
PACKAGE_PATH = OUTPUT_DIR / "safewatch_person_a_5hz_esp32_package.zip"

# Giữ các tên cũ để module export tương thích, nhưng pipeline không còn dùng ZIP.
CONTENT_DIR = OUTPUT_DIR
QMI_ZIP_PATH = PROJECT_ROOT / "data_records.zip"
QMI_EXTRACT_DIR = QMI_DATA_DIR
WEDA_REPO_DIR = WEDA_5HZ_DIR.parents[1]


def ensure_output_dir() -> Path:
    """Tạo OUTPUT_DIR nếu chưa có (tương đương Cell 5.5)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR
