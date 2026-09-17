# -*- coding: utf-8 -*-
"""
splitting.py
============
Chia train/validation/test cho WEDA (theo user) và QMI (theo session).

Nguồn gốc trong notebook Colab: Cell 9
"""

import numpy as np
from sklearn.model_selection import train_test_split

from .config import FALL, NON_FALL, SEED


def contains_both_classes(records):
    """(Cell 9)"""
    return {record.label for record in records} == {NON_FALL, FALL}


def split_weda_by_user(
    records,
    train_ratio=0.70,
    validation_ratio=0.15,
    seed=SEED,
):
    """(Cell 9) — chia theo user để tránh rò rỉ dữ liệu (data leakage)."""
    users = sorted(
        {record.user_id for record in records if record.user_id != "UNKNOWN"}
    )

    if len(users) < 5:
        raise RuntimeError(
            "Không đọc được đủ user WEDA. Hãy kiểm tra tên file."
        )

    for attempt in range(1000):
        rng = np.random.default_rng(seed + attempt)

        shuffled_users = np.asarray(users, dtype=object)
        rng.shuffle(shuffled_users)

        number_of_users = len(shuffled_users)

        number_train = max(1, int(round(number_of_users * train_ratio)))
        number_validation = max(1, int(round(number_of_users * validation_ratio)))

        train_users = set(shuffled_users[:number_train])
        validation_users = set(
            shuffled_users[number_train : number_train + number_validation]
        )
        test_users = set(shuffled_users[number_train + number_validation :])

        train_records = [r for r in records if r.user_id in train_users]
        validation_records = [r for r in records if r.user_id in validation_users]
        test_records = [r for r in records if r.user_id in test_users]

        if (
            test_users
            and contains_both_classes(train_records)
            and contains_both_classes(validation_records)
            and contains_both_classes(test_records)
        ):
            return train_records, validation_records, test_records

    raise RuntimeError("Không tạo được WEDA split có đủ FALL và NON_FALL.")


def split_qmi_by_session(records, validation_ratio=0.20, seed=SEED):
    """(Cell 9) — chia stratified theo session."""
    indices = np.arange(len(records))
    labels = np.asarray([record.label for record in records], dtype=np.int64)

    train_indices, validation_indices = train_test_split(
        indices,
        test_size=validation_ratio,
        random_state=seed,
        stratify=labels,
    )

    train_records = [records[index] for index in train_indices]
    validation_records = [records[index] for index in validation_indices]

    return train_records, validation_records


def print_split(name, records, class_names):
    """(Cell 9)"""
    import pandas as pd

    labels = pd.Series([class_names[record.label] for record in records])
    print(name, "sessions:", len(records), labels.value_counts().to_dict())
