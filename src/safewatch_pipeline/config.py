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

# =========================================================
# NHÃN NHỊ PHÂN (Cell 5.5)
# =========================================================
NON_FALL = 0
FALL = 1
CLASS_NAMES = ["NON_FALL", "FALL"]

# =========================================================
# SEED (Cell 5.5 / Cell 15.5)
# =========================================================
SEED = 42

# =========================================================
# CẤU HÌNH TÍN HIỆU / CỬA SỔ (Cell 5A)
# =========================================================
TARGET_HZ = 5
WINDOW_SECONDS = 4.0
WINDOW_SIZE = int(TARGET_HZ * WINDOW_SECONDS)  # 20 mẫu
FEATURE_COUNT = 4
GRAVITY = 9.80665

# Cell 22.5
SAMPLE_INTERVAL_MS = int(1000 / TARGET_HZ)  # 200 ms

# =========================================================
# CẤU HÌNH CẮT CỬA SỔ (Cell 9.5)
# =========================================================
INFERENCE_STRIDE_SAMPLES = TARGET_HZ  # 5 mẫu = chạy inference mỗi 1 giây

# WEDA: có thể lấy nhiều cửa sổ hơn vì dữ liệu lớn
MAX_WEDA_NONFALL_WINDOWS_TRAIN = 4
MAX_WEDA_NONFALL_WINDOWS_EVAL = 2

# QMI của người A: hạn chế số cửa sổ/session
# để tránh một session tạo quá nhiều mẫu gần giống nhau
MAX_QMI_NONFALL_WINDOWS_TRAIN = 2
MAX_QMI_NONFALL_WINDOWS_EVAL = 1

# =========================================================
# CẤU HÌNH FINE-TUNE PERSON_A (Cell 15.5)
# =========================================================
# Mỗi cửa sổ QMI gốc tạo thêm 5 bản augmentation
QMI_AUGMENT_COPIES = 5

# Tập fine-tune gồm khoảng:
# 70% dữ liệu QMI cá nhân
# 30% dữ liệu WEDA replay
WEDA_REPLAY_RATIO = 0.30

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
CONTENT_DIR = Path("/content")

QMI_ZIP_PATH = CONTENT_DIR / "data_records.zip"
QMI_EXTRACT_DIR = CONTENT_DIR / "qmi_person_a"

WEDA_REPO_DIR = CONTENT_DIR / "WEDA-FALL"
WEDA_5HZ_DIR = WEDA_REPO_DIR / "dataset" / "5Hz"

OUTPUT_DIR = CONTENT_DIR / "safewatch_5hz_output"

NEXT_DAY_DIR = CONTENT_DIR / "qmi_person_a_next_day"

PACKAGE_PATH = CONTENT_DIR / "safewatch_person_a_5hz_esp32_package.zip"


def ensure_output_dir() -> Path:
    """Tạo OUTPUT_DIR nếu chưa có (tương đương Cell 5.5)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR
