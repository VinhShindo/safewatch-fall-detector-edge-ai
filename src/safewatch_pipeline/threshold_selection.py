# -*- coding: utf-8 -*-
"""
threshold_selection.py
========================
Chọn ngưỡng FALL_THRESHOLD tối ưu trên tập validation QMI (ưu tiên
recall >= 85%), và suy ra HIGH_FALL_THRESHOLD dùng để xác nhận té
ngã ngay lập tức (không cần đủ số cửa sổ liên tiếp).

Nguồn gốc trong notebook Colab: Cell 19
"""

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, fbeta_score, precision_score, recall_score

from .config import FALL
from .evaluation import evaluate_float_model


def select_fall_threshold(model, X_qmi_validation, y_qmi_validation):
    """(Cell 19)"""
    qmi_validation_probabilities = model.predict(X_qmi_validation, verbose=0)[:, FALL]

    threshold_results = []

    for threshold in np.arange(0.35, 0.96, 0.01):
        predictions = (qmi_validation_probabilities >= threshold).astype(np.int64)

        threshold_results.append(
            {
                "threshold": float(threshold),
                "precision": precision_score(
                    y_qmi_validation, predictions, zero_division=0
                ),
                "recall": recall_score(
                    y_qmi_validation, predictions, zero_division=0
                ),
                "f1": f1_score(y_qmi_validation, predictions, zero_division=0),
                # F2 ưu tiên recall hơn precision
                "f2": fbeta_score(
                    y_qmi_validation, predictions, beta=2, zero_division=0
                ),
            }
        )

    threshold_table = pd.DataFrame(threshold_results)

    # Ưu tiên threshold có recall >= 85%
    eligible_thresholds = threshold_table[threshold_table["recall"] >= 0.85]

    if len(eligible_thresholds) > 0:
        best_threshold_row = eligible_thresholds.sort_values(
            ["precision", "f1", "threshold"],
            ascending=[False, False, False],
        ).iloc[0]
    else:
        best_threshold_row = threshold_table.sort_values(
            ["f2", "recall", "precision"], ascending=False
        ).iloc[0]

    fall_threshold = float(best_threshold_row["threshold"])

    high_fall_threshold = float(min(0.98, max(0.85, fall_threshold + 0.15)))

    consecutive_required = 2

    print("Threshold được chọn:")
    print(best_threshold_row)
    print("\nFALL_THRESHOLD:", fall_threshold)
    print("HIGH_FALL_THRESHOLD:", high_fall_threshold)

    return {
        "threshold_table": threshold_table,
        "best_threshold_row": best_threshold_row,
        "fall_threshold": fall_threshold,
        "high_fall_threshold": high_fall_threshold,
        "consecutive_required": consecutive_required,
    }


def evaluate_with_selected_threshold(
    model,
    X_qmi_validation,
    y_qmi_validation,
    X_weda_test,
    y_weda_test,
    fall_threshold,
):
    """(Cell 19, phần đánh giá cuối)"""
    _ = evaluate_float_model(
        model,
        X_qmi_validation,
        y_qmi_validation,
        title="QMI PERSON A — session validation",
        threshold=fall_threshold,
    )

    # Kiểm tra model có quên WEDA quá nhiều không
    _ = evaluate_float_model(
        model,
        X_weda_test,
        y_weda_test,
        title="WEDA test sau fine-tune",
        threshold=fall_threshold,
    )
