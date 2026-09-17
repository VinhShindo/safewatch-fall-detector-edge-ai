# -*- coding: utf-8 -*-
"""
qmi.py
======
Nạp các session từ dữ liệu cá nhân QMI (person A), gồm resample
6.25 Hz thực tế -> 5 Hz.

Nguồn gốc trong notebook Colab: Cell 7
- QMI_FILE_ACTIVITY (đã chuyển sang config.py)
- load_qmi_sessions
"""

import numpy as np
import pandas as pd

from utils.config import FALL, GRAVITY, NON_FALL, QMI_FILE_ACTIVITY, TARGET_HZ, WINDOW_SIZE
from features.temporal_features import SessionRecord, ensure_finite, resample_accel


def load_qmi_sessions(root):
    """(Cell 7)"""
    records = []
    failures = []

    csv_files = sorted(root.rglob("*.csv"))

    for path in csv_files:
        file_key = path.stem.lower()
        activity = QMI_FILE_ACTIVITY.get(file_key)

        if activity is None:
            print("Bỏ qua file chưa ánh xạ:", path.name)
            continue

        binary_label = FALL if activity.lower().startswith("fall") else NON_FALL

        try:
            dataframe = pd.read_csv(path)

            required_columns = [
                "session_id",
                "timestamp_ms",
                "accel_x(m_s2)",
                "accel_y(m_s2)",
                "accel_z(m_s2)",
            ]

            missing_columns = [
                column for column in required_columns if column not in dataframe.columns
            ]

            if missing_columns:
                raise ValueError(f"Thiếu cột: {missing_columns}")

            grouped_sessions = dataframe.groupby("session_id", sort=False)

            for session_id, group in grouped_sessions:
                timestamps_ms = group["timestamp_ms"].to_numpy(dtype=np.float64)

                accel_m_s2 = group[
                    ["accel_x(m_s2)", "accel_y(m_s2)", "accel_z(m_s2)"]
                ].to_numpy(dtype=np.float32)

                # Chuyển m/s² → g
                accel_g = accel_m_s2 / GRAVITY

                # 6,25 Hz thực tế → 5 Hz
                accel_5hz = resample_accel(
                    timestamps_ms=timestamps_ms,
                    accel=accel_g,
                    target_hz=TARGET_HZ,
                )

                if len(accel_5hz) < WINDOW_SIZE:
                    continue

                ensure_finite(accel_5hz, f"{path.name}/{session_id}")

                records.append(
                    SessionRecord(
                        session_id=f"QMI_{file_key}_{session_id}",
                        source="QMI",
                        activity=activity,
                        label=binary_label,
                        accel_g=accel_5hz,
                        user_id="PERSON_A",
                        path=str(path),
                    )
                )

        except Exception as error:
            failures.append((str(path), str(error)))

    print("QMI session hợp lệ:", len(records))
    print("File lỗi:", len(failures))

    if failures:
        for failure in failures:
            print(failure)

    return records


def print_qmi_summary(qmi_sessions, class_names):
    """In tóm tắt session theo hoạt động (phần cuối Cell 7)."""
    qmi_summary = pd.DataFrame(
        {
            "activity": [record.activity for record in qmi_sessions],
            "label": [class_names[record.label] for record in qmi_sessions],
            "samples_5hz": [len(record.accel_g) for record in qmi_sessions],
        }
    )

    print("\nSố session theo hoạt động:")
    print(qmi_summary.groupby(["activity", "label"]).size())

    print("\nSố mẫu sau khi xuống 5 Hz:")
    print(qmi_summary["samples_5hz"].describe())

    return qmi_summary
