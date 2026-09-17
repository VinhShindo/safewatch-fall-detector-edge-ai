# -*- coding: utf-8 -*-
"""
augmentation.py
================
Data augmentation (dịch nhẹ theo thời gian + nhiễu Gaussian) và
tính class weight cân bằng.

Nguồn gốc trong notebook Colab: Cell 12
"""

import numpy as np
from sklearn.utils.class_weight import compute_class_weight


def shift_window_without_wrap(window, shift):
    """(Cell 12)"""
    shifted = window.copy()

    if shift > 0:
        shifted[shift:] = window[:-shift]
        shifted[:shift] = window[0]
    elif shift < 0:
        shift_abs = abs(shift)
        shifted[:-shift_abs] = window[shift_abs:]
        shifted[-shift_abs:] = window[-1]

    return shifted


def augment_windows(X, y, copies, seed):
    """(Cell 12)"""
    rng = np.random.default_rng(seed)

    augmented_X = [X]
    augmented_y = [y]

    for _ in range(copies):
        batch = X.copy()

        shifts = rng.integers(-1, 2, size=len(batch))

        for index, shift in enumerate(shifts):
            batch[index] = shift_window_without_wrap(batch[index], int(shift))

        noise = rng.normal(loc=0.0, scale=0.025, size=batch.shape).astype(np.float32)
        batch = batch + noise

        augmented_X.append(batch.astype(np.float32))
        augmented_y.append(y.copy())

    return (
        np.concatenate(augmented_X, axis=0),
        np.concatenate(augmented_y, axis=0),
    )


def create_class_weights(y):
    """(Cell 12)"""
    classes = np.unique(y)

    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y)

    return {int(class_id): float(weight) for class_id, weight in zip(classes, weights)}
