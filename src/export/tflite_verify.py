# -*- coding: utf-8 -*-
"""
tflite_verify.py
==================
import matplotlib.pyplot as plt
đợi, chạy inference bằng interpreter và so sánh với model Keras gốc.

Nguồn gốc trong notebook Colab: Cell 22
"""
from utils.config import CLASS_NAMES, FALL, FEATURE_COUNT, NON_FALL, WINDOW_SIZE
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from sklearn.metrics import ConfusionMatrixDisplay, classification_report, confusion_matrix

from utils.config import CLASS_NAMES, FALL, FEATURE_COUNT, NON_FALL, WINDOW_SIZE


def load_tflite_interpreter(tflite_path: Path):
    """(Cell 22 — phần khởi tạo interpreter & kiểm tra input/output)"""
    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    print("===== INPUT =====")
    print("Shape:", input_details["shape"])
    print("Dtype:", input_details["dtype"])
    print("Quantization:", input_details["quantization"])

    print("\n===== OUTPUT =====")
    print("Shape:", output_details["shape"])
    print("Dtype:", output_details["dtype"])
    print("Quantization:", output_details["quantization"])

    assert input_details["dtype"] == np.int8
    assert output_details["dtype"] == np.int8
    assert tuple(input_details["shape"]) == (1, WINDOW_SIZE, FEATURE_COUNT)

    input_scale, input_zero_point = input_details["quantization"]
    output_scale, output_zero_point = output_details["quantization"]

    if input_scale <= 0:
        raise RuntimeError("Input scale không hợp lệ.")

    if output_scale <= 0:
        raise RuntimeError("Output scale không hợp lệ.")

    return interpreter, input_details, output_details


def make_quantize_dequantize_fns(input_details, output_details):
    """(Cell 22)"""
    input_scale, input_zero_point = input_details["quantization"]
    output_scale, output_zero_point = output_details["quantization"]

    def quantize_input(float_input):
        quantized = np.round(float_input / input_scale + input_zero_point)
        quantized = np.clip(quantized, -128, 127)
        return quantized.astype(np.int8)

    def dequantize_output(int8_output):
        return (int8_output.astype(np.float32) - output_zero_point) * output_scale

    return quantize_input, dequantize_output


def predict_tflite_fall_probability(
    X, interpreter, input_details, output_details, quantize_input, dequantize_output
):
    """(Cell 22)"""
    probabilities = []

    for sample in X:
        sample_int8 = quantize_input(sample[None, ...])

        interpreter.set_tensor(input_details["index"], sample_int8)
        interpreter.invoke()

        output_int8 = interpreter.get_tensor(output_details["index"])[0]
        output_float = dequantize_output(output_int8)

        probabilities.append(float(output_float[FALL]))

    return np.asarray(probabilities, dtype=np.float32)


def verify_int8_model(
    tflite_path: Path,
    X_qmi_validation,
    y_qmi_validation,
    fall_threshold: float,
    qmi_validation_probabilities_keras=None,
    show=True,
):
    """
    Luồng đầy đủ của Cell 22: nạp interpreter, chạy inference INT8
    trên tập validation QMI, in classification report + ma trận
    nhầm lẫn, và (nếu có xác suất Keras để so sánh) tính tỉ lệ đồng
    thuận Keras <-> INT8.
    """
    interpreter, input_details, output_details = load_tflite_interpreter(tflite_path)
    quantize_input, dequantize_output = make_quantize_dequantize_fns(
        input_details, output_details
    )

    qmi_int8_probabilities = predict_tflite_fall_probability(
        X_qmi_validation,
        interpreter,
        input_details,
        output_details,
        quantize_input,
        dequantize_output,
    )

    qmi_int8_predictions = (qmi_int8_probabilities >= fall_threshold).astype(np.int64)

    print(
        classification_report(
            y_qmi_validation,
            qmi_int8_predictions,
            target_names=CLASS_NAMES,
            digits=4,
            zero_division=0,
        )
    )

    matrix_int8 = confusion_matrix(
        y_qmi_validation, qmi_int8_predictions, labels=[NON_FALL, FALL]
    )

    ConfusionMatrixDisplay(
        confusion_matrix=matrix_int8, display_labels=CLASS_NAMES
    ).plot(values_format="d")

    plt.title("QMI validation — TFLite Full INT8")

    if show:
        plt.show()

    if qmi_validation_probabilities_keras is not None:
        keras_predictions = (
            qmi_validation_probabilities_keras >= fall_threshold
        ).astype(np.int64)

        agreement_rate = np.mean(keras_predictions == qmi_int8_predictions)

        print("Đồng thuận Keras ↔ INT8:", f"{agreement_rate:.2%}")

    print("\nFULL INT8: OK")

    return qmi_int8_probabilities, qmi_int8_predictions
