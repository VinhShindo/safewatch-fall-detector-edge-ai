# -*- coding: utf-8 -*-
"""
audit.py
========
Thống kê & trực quan hóa nhanh dữ liệu session trước khi cắt cửa sổ.

Nguồn gốc trong notebook Colab: Cell 8
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from utils.config import CLASS_NAMES, FALL, NON_FALL, TARGET_HZ
from utils.config import CLASS_NAMES, FALL, NON_FALL, TARGET_HZ


def summarize_sessions(records, name):
    """(Cell 8)"""
    summary = pd.DataFrame(
        {
            "activity": [record.activity for record in records],
            "label": [CLASS_NAMES[record.label] for record in records],
            "samples": [len(record.accel_g) for record in records],
            "median_magnitude": [
                float(np.median(np.linalg.norm(record.accel_g, axis=1)))
                for record in records
            ],
            "max_magnitude": [
                float(np.max(np.linalg.norm(record.accel_g, axis=1)))
                for record in records
            ],
        }
    )

    print(f"\n===== {name} =====")
    print(summary.groupby("label").size())
    print(summary[["samples", "median_magnitude", "max_magnitude"]].describe())

    return summary


def plot_example_sessions(qmi_sessions, target_hz=TARGET_HZ, show=True):
    """
    Vẽ magnitude của một session FALL và một session NON_FALL của QMI.
    (Cell 8, phần vẽ đồ thị)
    """
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))

    for axis, target_label in zip(axes, [FALL, NON_FALL]):
        record = next(
            record for record in qmi_sessions if record.label == target_label
        )

        magnitude = np.linalg.norm(record.accel_g, axis=1)
        time_axis = np.arange(len(magnitude)) / target_hz

        axis.plot(time_axis, magnitude)
        axis.set_title(f"{record.activity} — {record.session_id}")
        axis.set_xlabel("Thời gian (giây)")
        axis.set_ylabel("Magnitude (g)")
        axis.grid(True, alpha=0.3)

    plt.tight_layout()

    if show:
        plt.show()

    return fig
