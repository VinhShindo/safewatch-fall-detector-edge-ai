# -*- coding: utf-8 -*-
"""
next_day_test.py
==================
Kiểm thử tùy chọn trên dữ liệu QMI thu thập ở "ngày hôm sau" (một
bộ dữ liệu hoàn toàn không dùng để train/validate), để đánh giá khả
năng tổng quát hóa theo thời gian của model đã fine-tune.

Nguồn gốc trong notebook Colab: Cell 20

LƯU Ý: notebook gốc dùng `google.colab.files.upload()` để chọn ZIP
kiểm thử thủ công (`RUN_NEXT_DAY_TEST = False` mặc định tắt bước
này). Bản refactor giữ nguyên cờ bật/tắt nhưng nhận đường dẫn ZIP
qua tham số hàm thay vì upload trình duyệt.
"""

import shutil
import zipfile
from pathlib import Path

from .config import (
    CONTENT_DIR,
    MAX_QMI_NONFALL_WINDOWS_EVAL,
    NEXT_DAY_DIR,
)
from .data_loading.qmi import load_qmi_sessions
from .evaluation import evaluate_float_model
from .windowing import sessions_to_windows

# Mặc định tắt, giống notebook gốc (Cell 20: RUN_NEXT_DAY_TEST = False)
RUN_NEXT_DAY_TEST = False


def run_next_day_test(
    next_day_zip_path,
    model,
    normalize_features,
    fall_threshold,
    content_dir: Path = CONTENT_DIR,
    next_day_dir: Path = NEXT_DAY_DIR,
    max_nonfall_windows=MAX_QMI_NONFALL_WINDOWS_EVAL,
):
    """(Cell 20)"""
    next_day_zip_path = Path(next_day_zip_path)

    if next_day_dir.exists():
        shutil.rmtree(next_day_dir)

    next_day_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(next_day_zip_path, "r") as zip_file:
        zip_file.extractall(next_day_dir)

    next_day_sessions = load_qmi_sessions(next_day_dir)

    X_next_day_raw, y_next_day, next_day_groups, _, _ = sessions_to_windows(
        next_day_sessions,
        training=False,
        max_nonfall_windows=max_nonfall_windows,
    )

    X_next_day = normalize_features(X_next_day_raw)

    return evaluate_float_model(
        model,
        X_next_day,
        y_next_day,
        title="FINAL TEST — PERSON A NGÀY HÔM SAU",
        threshold=fall_threshold,
    )
