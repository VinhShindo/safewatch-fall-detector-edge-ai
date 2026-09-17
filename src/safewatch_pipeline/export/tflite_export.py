# -*- coding: utf-8 -*-
"""
tflite_export.py
==================
Lượng tử hóa model Keras đã fine-tune sang TFLite Full INT8, dùng
representative dataset lấy từ cả WEDA và QMI train.

Nguồn gốc trong notebook Colab: Cell 21
"""

import shutil
from pathlib import Path

import numpy as np
import tensorflow as tf

from ..config import CONTENT_DIR, OUTPUT_DIR, SEED, ensure_output_dir


def export_int8_tflite(
    model,
    X_weda_train,
    X_qmi_train,
    output_dir: Path = OUTPUT_DIR,
    content_dir: Path = CONTENT_DIR,
    seed: int = SEED,
):
    """(Cell 21)"""
    ensure_output_dir()

    tflite_path = output_dir / "safewatch_person_a_5hz_int8.tflite"

    representative_pool = np.concatenate([X_weda_train, X_qmi_train], axis=0).astype(
        np.float32
    )

    rng = np.random.default_rng(seed)

    representative_count = min(500, len(representative_pool))

    representative_indices = rng.choice(
        len(representative_pool), size=representative_count, replace=False
    )

    representative_data = representative_pool[representative_indices]

    def representative_dataset():
        for index in range(len(representative_data)):
            sample = representative_data[index : index + 1].astype(np.float32)
            yield [sample]

    def configure_int8_converter(converter):
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = representative_dataset
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS_INT8
        ]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8
        return converter

    try:
        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        converter = configure_int8_converter(converter)
        tflite_int8_model = converter.convert()

    except Exception as direct_error:
        print("Convert trực tiếp gặp lỗi:")
        print(direct_error)
        print("\nThử chuyển qua SavedModel...")

        temp_saved_model = content_dir / "temporary_saved_model"

        if temp_saved_model.exists():
            shutil.rmtree(temp_saved_model)

        if hasattr(model, "export"):
            model.export(temp_saved_model)
        else:
            tf.saved_model.save(model, temp_saved_model)

        converter = tf.lite.TFLiteConverter.from_saved_model(str(temp_saved_model))
        converter = configure_int8_converter(converter)
        tflite_int8_model = converter.convert()

    with open(tflite_path, "wb") as output_file:
        output_file.write(tflite_int8_model)

    print("Đã tạo:", tflite_path)
    print("Kích thước:", round(tflite_path.stat().st_size / 1024, 2), "KB")

    return tflite_path
