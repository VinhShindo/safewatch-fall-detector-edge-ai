# -*- coding: utf-8 -*-
"""
normalization.py
=================
Chuẩn hóa feature bằng mean/std được tính với trọng số ngang nhau
giữa hai domain WEDA và QMI (để WEDA đông hơn không lấn át QMI).

Nguồn gốc trong notebook Colab: Cell 11
"""

import numpy as np

from .config import FEATURE_COUNT


def domain_weighted_mean_std(weda_data, qmi_data):
    """
    Cho WEDA và QMI trọng số ngang nhau khi tính mean/std.
    Tránh WEDA đông hơn làm lấn át QMI. (Cell 11)
    """
    weda_flat = weda_data.reshape(-1, FEATURE_COUNT)
    qmi_flat = qmi_data.reshape(-1, FEATURE_COUNT)

    weda_mean = weda_flat.mean(axis=0)
    qmi_mean = qmi_flat.mean(axis=0)

    weda_variance = weda_flat.var(axis=0)
    qmi_variance = qmi_flat.var(axis=0)

    combined_mean = 0.5 * weda_mean + 0.5 * qmi_mean

    combined_variance = 0.5 * (
        weda_variance + np.square(weda_mean - combined_mean)
    ) + 0.5 * (qmi_variance + np.square(qmi_mean - combined_mean))

    combined_std = np.sqrt(combined_variance)
    combined_std = np.maximum(combined_std, 1e-6)

    return combined_mean.astype(np.float32), combined_std.astype(np.float32)


def make_normalizer(feature_mean, feature_std):
    """
    Trả về hàm normalize_features đóng gói cùng mean/std đã tính.
    (tương đương closure `normalize_features` trong Cell 11)
    """

    def normalize_features(X):
        return ((X - feature_mean) / feature_std).astype(np.float32)

    return normalize_features
