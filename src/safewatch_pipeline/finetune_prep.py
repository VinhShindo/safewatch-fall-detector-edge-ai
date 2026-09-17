# -*- coding: utf-8 -*-
"""
finetune_prep.py
=================
Chuẩn bị tập fine-tune cho người dùng cá nhân (PERSON_A): augment
dữ liệu QMI + trộn thêm một phần dữ liệu WEDA để tránh "catastrophic
forgetting".

Nguồn gốc trong notebook Colab:
- Cell 15.5 ("CELL 15.5 — CẤU HÌNH FINE-TUNE PERSON_A"): các hằng số
  QMI_AUGMENT_COPIES, WEDA_REPLAY_RATIO đã chuyển vào config.py.
- Cell 16: logic augment + trộn WEDA replay + shuffle.
"""

import numpy as np

from .augmentation import augment_windows, create_class_weights
from .config import QMI_AUGMENT_COPIES, SEED, WEDA_REPLAY_RATIO


def build_finetune_dataset(
    X_qmi_train,
    y_qmi_train,
    X_weda_train,
    y_weda_train,
    qmi_augment_copies=QMI_AUGMENT_COPIES,
    weda_replay_ratio=WEDA_REPLAY_RATIO,
    seed=SEED,
):
    """(Cell 16)"""
    if len(X_qmi_train) == 0:
        raise RuntimeError("X_qmi_train đang rỗng.")

    if len(X_weda_train) == 0:
        raise RuntimeError("X_weda_train đang rỗng.")

    if len(X_qmi_train) != len(y_qmi_train):
        raise RuntimeError(
            "Số cửa sổ X_qmi_train không bằng số nhãn y_qmi_train."
        )

    if len(X_weda_train) != len(y_weda_train):
        raise RuntimeError(
            "Số cửa sổ X_weda_train không bằng số nhãn y_weda_train."
        )

    X_qmi_augmented, y_qmi_augmented = augment_windows(
        X_qmi_train, y_qmi_train, copies=qmi_augment_copies, seed=seed + 100
    )

    rng = np.random.default_rng(seed)

    # Tính số cửa sổ WEDA replay
    target_weda_count = int(
        len(X_qmi_augmented) * weda_replay_ratio / max(1e-6, 1.0 - weda_replay_ratio)
    )

    use_replacement = target_weda_count > len(X_weda_train)

    weda_replay_indices = rng.choice(
        len(X_weda_train), size=target_weda_count, replace=use_replacement
    )

    X_finetune = np.concatenate(
        [X_qmi_augmented, X_weda_train[weda_replay_indices]], axis=0
    )

    y_finetune = np.concatenate(
        [y_qmi_augmented, y_weda_train[weda_replay_indices]], axis=0
    )

    shuffle_indices = rng.permutation(len(X_finetune))

    X_finetune = X_finetune[shuffle_indices]
    y_finetune = y_finetune[shuffle_indices]

    finetune_class_weights = create_class_weights(y_finetune)

    print("Fine-tune shape:", X_finetune.shape)
    print(
        "Class counts:",
        dict(zip(*np.unique(y_finetune, return_counts=True))),
    )
    print("Class weights:", finetune_class_weights)

    return X_finetune, y_finetune, finetune_class_weights
