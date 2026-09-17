# -*- coding: utf-8 -*-
"""
finetune_train.py
==================
Fine-tune model đã pretrain trên WEDA cho dữ liệu cá nhân PERSON_A,
theo 2 giai đoạn "progressive unfreezing" (mở khóa dần các lớp conv).

Nguồn gốc trong notebook Colab:
- Cell 17: giai đoạn 1 — khóa toàn bộ phần convolution
- Cell 18: giai đoạn 2 — mở conv2, lưu model đã fine-tune
"""

import tensorflow as tf

from models.model import compile_model
from utils.config import OUTPUT_DIR, ensure_output_dir


def finetune_stage1(
    model,
    X_finetune,
    y_finetune,
    X_qmi_validation,
    y_qmi_validation,
    finetune_class_weights,
):
    """
    Giai đoạn 1 (Cell 17): khóa toàn bộ phần convolution (conv1, pool1,
    conv2), chỉ huấn luyện phần dense phía sau với learning rate nhỏ.
    """
    for layer in model.layers:
        if layer.name in {"conv1", "pool1", "conv2"}:
            layer.trainable = False
        else:
            layer.trainable = True

    compile_model(model, learning_rate=1e-4)

    history_finetune_stage1 = model.fit(
        X_finetune,
        y_finetune,
        validation_data=(X_qmi_validation, y_qmi_validation),
        epochs=35,
        batch_size=16,
        class_weight=finetune_class_weights,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=6, restore_best_weights=True, verbose=1
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=3, min_lr=1e-6, verbose=1
            ),
        ],
        verbose=1,
    )

    return history_finetune_stage1


def finetune_stage2(
    model,
    X_finetune,
    y_finetune,
    X_qmi_validation,
    y_qmi_validation,
    finetune_class_weights,
    output_dir=OUTPUT_DIR,
):
    """
    Giai đoạn 2 (Cell 18): giữ conv1 bị khóa, mở conv2 để thích nghi
    nhẹ với người A, learning rate rất nhỏ. Sau đó lưu model.
    """
    ensure_output_dir()

    # Giữ conv1 bị khóa, mở conv2 để thích nghi nhẹ với người A
    for layer in model.layers:
        layer.trainable = layer.name != "conv1"

    compile_model(model, learning_rate=1e-5)

    history_finetune_stage2 = model.fit(
        X_finetune,
        y_finetune,
        validation_data=(X_qmi_validation, y_qmi_validation),
        epochs=12,
        batch_size=16,
        class_weight=finetune_class_weights,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=4, restore_best_weights=True, verbose=1
            ),
        ],
        verbose=1,
    )

    finetuned_model_path = output_dir / "person_a_finetuned_5hz.keras"
    model.save(finetuned_model_path)

    print("Đã lưu:", finetuned_model_path)

    return history_finetune_stage2, finetuned_model_path
