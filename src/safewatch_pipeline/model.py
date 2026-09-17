# -*- coding: utf-8 -*-
"""
model.py
========
Kiến trúc CNN 1D nhẹ dùng cho phát hiện té ngã (chạy được trên
vi điều khiển sau khi lượng tử hóa INT8).

Nguồn gốc trong notebook Colab: Cell 13
"""

import tensorflow as tf

from .config import FEATURE_COUNT, WINDOW_SIZE


def build_model():
    """(Cell 13)"""
    inputs = tf.keras.Input(shape=(WINDOW_SIZE, FEATURE_COUNT), name="sensor_window")

    x = tf.keras.layers.Conv1D(
        filters=16, kernel_size=3, padding="same", activation="relu", name="conv1"
    )(inputs)

    x = tf.keras.layers.MaxPooling1D(pool_size=2, name="pool1")(x)

    x = tf.keras.layers.Conv1D(
        filters=24, kernel_size=3, padding="same", activation="relu", name="conv2"
    )(x)

    x = tf.keras.layers.GlobalAveragePooling1D(name="global_average")(x)

    x = tf.keras.layers.Dense(units=16, activation="relu", name="dense_features")(x)

    x = tf.keras.layers.Dropout(rate=0.20, name="dropout")(x)

    outputs = tf.keras.layers.Dense(units=2, activation="softmax", name="class_output")(x)

    return tf.keras.Model(inputs=inputs, outputs=outputs, name="safewatch_fall_5hz")


def compile_model(model, learning_rate):
    """(Cell 13)"""
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="accuracy")],
    )
