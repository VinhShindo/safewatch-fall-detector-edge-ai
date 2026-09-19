# -*- coding: utf-8 -*-
"""
augmentation.py
================
Data augmentation (shift, noise, scale, time-warp, mixup) và class weights.

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


def time_warp_window(window, factor):
    """Resample a feature window to simulate a different event speed."""
    sample_positions = np.linspace(0.0, len(window) - 1, len(window))
    warped_positions = np.clip(
        (sample_positions - sample_positions.mean()) * factor
        + sample_positions.mean(),
        0.0,
        len(window) - 1,
    )
    warped = np.column_stack(
        [np.interp(warped_positions, sample_positions, window[:, feature]) for feature in range(window.shape[1])]
    )
    return warped.astype(np.float32)


def _scale_features(window, scale):
    scaled = window.copy()
    # magnitude, deviation, SMA scale linearly; variance is quadratic;
    # delta and jerk scale linearly; angle is dimensionless.
    for index in (0, 1, 2, 4, 6):
        scaled[:, index] *= scale
    scaled[:, 5] *= scale * scale
    return scaled


def _mixup_windows(X, y, rng, count):
    """Create opposite-class interpolations with a dominant hard label.

    The training loss is sparse categorical cross-entropy, so the dominant
    source label is retained instead of emitting soft labels.
    """
    class_indices = {int(label): np.flatnonzero(y == label) for label in np.unique(y)}
    if len(class_indices) < 2 or count == 0:
        return np.empty((0,) + X.shape[1:], dtype=np.float32), np.empty(0, dtype=y.dtype)

    mixed_X = []
    mixed_y = []
    labels = sorted(class_indices)
    for _ in range(count):
        first_label = int(rng.choice(labels))
        other_labels = [label for label in labels if label != first_label]
        second_label = int(rng.choice(other_labels))
        first_index = int(rng.choice(class_indices[first_label]))
        first = X[first_index]
        candidates = class_indices[second_label]
        distances = np.mean(
            np.square(X[candidates] - first[None, ...]), axis=(1, 2)
        )
        second = X[candidates[int(np.argmin(distances))]]
        weight = float(rng.uniform(0.7, 0.9))
        mixed_X.append(weight * first + (1.0 - weight) * second)
        mixed_y.append(first_label)
    return np.asarray(mixed_X, dtype=np.float32), np.asarray(mixed_y, dtype=y.dtype)


def augment_windows(X, y, copies, seed):
    """Apply sensor-gain, temporal, noise, and opposite-class mixup changes."""
    rng = np.random.default_rng(seed)

    augmented_X = [X]
    augmented_y = [y]

    for _ in range(copies):
        batch = X.copy()

        shifts = rng.integers(-1, 2, size=len(batch))

        for index, shift in enumerate(shifts):
            batch[index] = shift_window_without_wrap(batch[index], int(shift))

        for index in range(len(batch)):
            batch[index] = _scale_features(
                batch[index], float(rng.uniform(0.9, 1.1))
            )
            batch[index] = time_warp_window(
                batch[index], float(rng.uniform(0.9, 1.1))
            )

        noise = rng.normal(loc=0.0, scale=0.01, size=batch.shape).astype(np.float32)
        batch = batch + noise

        augmented_X.append(batch.astype(np.float32))
        augmented_y.append(y.copy())

    augmented_X = np.concatenate(augmented_X, axis=0)
    augmented_y = np.concatenate(augmented_y, axis=0)
    mixup_X, mixup_y = _mixup_windows(
        augmented_X, augmented_y, rng, count=max(1, len(augmented_X) // 10)
    )
    return np.concatenate([augmented_X, mixup_X]), np.concatenate([augmented_y, mixup_y])


def create_class_weights(y):
    """(Cell 12)"""
    classes = np.unique(y)

    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y)

    return {int(class_id): float(weight) for class_id, weight in zip(classes, weights)}
