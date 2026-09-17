# -*- coding: utf-8 -*-
"""
weda.py
=======
Nạp các session từ bộ dữ liệu WEDA-FALL (5 Hz).

Nguồn gốc trong notebook Colab: Cell 5.5
("CELL 5.5 — KHÔI PHỤC CẤU HÌNH CHUNG")
- parse_weda_user_and_trial
- load_weda_sessions
"""

import re

import numpy as np
import pandas as pd

from ..config import FALL, NON_FALL, WINDOW_SIZE
from ..features import SessionRecord, accel_to_g, ensure_finite, read_three_axis_csv


def parse_weda_user_and_trial(path):
    """
    Ví dụ:
    U02_R03_accel.csv
    (Cell 5.5)
    """
    match = re.search(r"U(\d+)_R(\d+)", path.stem, flags=re.IGNORECASE)

    if match:
        user_id = f"U{int(match.group(1)):02d}"
        trial_id = f"R{int(match.group(2)):02d}"
        return user_id, trial_id

    # Fallback chỉ lấy user
    user_match = re.search(r"U(\d+)", path.stem, flags=re.IGNORECASE)

    if user_match:
        return f"U{int(user_match.group(1)):02d}", path.stem

    return "UNKNOWN", path.stem


def load_weda_sessions(root):
    """(Cell 5.5)"""
    records = []
    failures = []
    detected_units = {}

    accel_files = sorted(root.rglob("*_accel.csv"))

    if not accel_files:
        raise FileNotFoundError(f"Không có file *_accel.csv trong {root}")

    for path in accel_files:
        activity = path.parent.name.upper()

        if not (activity.startswith("F") or activity.startswith("D")):
            continue

        binary_label = FALL if activity.startswith("F") else NON_FALL

        user_id, trial_id = parse_weda_user_and_trial(path)

        try:
            accel_raw = read_three_axis_csv(path)
            accel_g, detected_unit = accel_to_g(accel_raw, unit="auto")

            detected_units[detected_unit] = detected_units.get(detected_unit, 0) + 1

            ensure_finite(accel_g, str(path))

            if len(accel_g) < WINDOW_SIZE:
                continue

            records.append(
                SessionRecord(
                    session_id=f"WEDA_{activity}_{user_id}_{trial_id}",
                    source="WEDA",
                    activity=activity,
                    label=binary_label,
                    accel_g=accel_g,
                    user_id=user_id,
                    path=str(path),
                )
            )

        except Exception as error:
            failures.append((str(path), str(error)))

    print("WEDA session hợp lệ:", len(records))
    print("Đơn vị phát hiện:", detected_units)
    print("Số file lỗi/bỏ qua:", len(failures))

    if failures:
        print("\nMột số lỗi đầu tiên:")
        for failure in failures[:5]:
            print(failure)

    return records


def print_weda_distributions(weda_sessions, class_names):
    """In phân phối activity/nhãn WEDA (phần cuối Cell 5.5)."""
    print("\nPhân phối activity WEDA:")
    print(
        pd.Series([record.activity for record in weda_sessions])
        .value_counts()
        .sort_index()
    )

    print("\nPhân phối nhãn WEDA:")
    print(
        pd.Series(
            [class_names[record.label] for record in weda_sessions]
        ).value_counts()
    )
