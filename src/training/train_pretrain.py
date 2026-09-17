# -*- coding: utf-8 -*-
"""
train_pretrain.py
==================
Huấn luyện (pretrain) model trên toàn bộ dữ liệu WEDA-FALL.

Nguồn gốc trong notebook Colab: Cell 14
"""

import tensorflow as tf

from utils.config import OUTPUT_DIR, ensure_output_dir


def pretrain_on_weda(
    model,
    X_weda_train,
    y_weda_train,
    X_weda_validation,
    y_weda_validation,
    weda_class_weights,
    output_dir=OUTPUT_DIR,
):
    """(Cell 14)"""
    ensure_output_dir()

    pretrain_model_path = output_dir / "weda_pretrained_5hz.keras"

    pretrain_callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=8, restore_best_weights=True, verbose=1
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5, verbose=1
        ),
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(pretrain_model_path),
            monitor="val_loss",
            save_best_only=True,
            verbose=1,
        ),
    ]

    history_pretrain = model.fit(
        X_weda_train,
        y_weda_train,
        validation_data=(X_weda_validation, y_weda_validation),
        epochs=60,
        batch_size=32,
        class_weight=weda_class_weights,
        callbacks=pretrain_callbacks,
        verbose=1,
    )

    print("Đã lưu model WEDA:", pretrain_model_path)

    return history_pretrain, pretrain_model_path
