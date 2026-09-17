# -*- coding: utf-8 -*-
"""
arduino_export.py
===================
Sinh file .ino mẫu cho ESP32-S3 (đọc cảm biến QMI8658, chạy vòng lặp
đệm cửa sổ, chạy inference, xử lý kết quả, hiển thị và gửi backend).

Nguồn gốc trong notebook Colab: Cell 25
"""

from pathlib import Path

from utils.config import OUTPUT_DIR, ensure_output_dir


def export_arduino_sketch(output_dir: Path = OUTPUT_DIR):
    """(Cell 25)"""
    ensure_output_dir()

    arduino_template_path = output_dir / "SafeWatch_Fall_Detector.ino"

    arduino_template_path.write_text(
        r'''#include <Arduino.h>

#include "fall_model_config.h"
#include "fall_inference.h"


float g_accel_ring[kWindowSize][3] = {};

int g_write_index = 0;
int g_sample_count = 0;

int g_samples_since_inference = 0;
int g_consecutive_fall_windows = 0;

uint32_t g_last_sample_ms = 0;


/*
 * THAY HÀM NÀY BẰNG DRIVER QMI8658
 * ĐANG CHẠY TRÊN BO MẠCH CỦA BẠN.
from utils.config import OUTPUT_DIR, ensure_output_dir
 * Giá trị đầu ra bắt buộc ở đơn vị g.
 */
from utils.config import OUTPUT_DIR, ensure_output_dir
bool ReadQmi8658AccelG(
    float* ax_g,
    float* ay_g,
    float* az_g
) {
    /*
    Ví dụ nếu thư viện trả m/s²:

    float ax_ms2;
    float ay_ms2;
    float az_ms2;

    qmi.getAccel(
        &ax_ms2,
        &ay_ms2,
        &az_ms2
    );

    *ax_g = ax_ms2 / 9.80665f;
    *ay_g = ay_ms2 / 9.80665f;
    *az_g = az_ms2 / 9.80665f;

    return true;
    */

    return false;
}


void CopyRingChronologically(
    float output[kWindowSize][3]
) {
    const int oldest_index =
        (
            g_sample_count
            < kWindowSize
        )
        ? 0
        : g_write_index;

    for (
        int i = 0;
        i < kWindowSize;
        ++i
    ) {
        const int source_index =
            (
                oldest_index + i
            ) % kWindowSize;

        output[i][0] =
            g_accel_ring[source_index][0];

        output[i][1] =
            g_accel_ring[source_index][1];

        output[i][2] =
            g_accel_ring[source_index][2];
    }
}


void ShowStatusOnDisplay(
    const char* status,
    float fall_probability
) {
    /*
     * Thay bằng hàm LVGL/LCD thực tế.
     */

    Serial.printf(
        "Status=%s | P(FALL)=%.3f\n",
        status,
        fall_probability
    );
}


void SendFallToBackend(
    float fall_probability
) {
    /*
     * Gửi HTTPS POST đến ASP.NET Core.
     * Backend mới gửi Telegram.
     */

    Serial.printf(
        "TODO POST fall event: %.3f\n",
        fall_probability
    );
}


void HandlePrediction(
    float fall_probability
) {
    bool confirmed_fall = false;

    if (
        fall_probability
        >= kHighFallThreshold
    ) {
        confirmed_fall = true;

        g_consecutive_fall_windows = 0;
    }

    else if (
        fall_probability
        >= kFallThreshold
    ) {
        ++g_consecutive_fall_windows;

        if (
            g_consecutive_fall_windows
            >= kConsecutiveRequired
        ) {
            confirmed_fall = true;

            g_consecutive_fall_windows = 0;
        }
    }

    else {
        g_consecutive_fall_windows = 0;
    }

    if (confirmed_fall) {
        ShowStatusOnDisplay(
            "NGA",
            fall_probability
        );

        SendFallToBackend(
            fall_probability
        );
    }

    else {
        ShowStatusOnDisplay(
            "KHONG NGA",
            fall_probability
        );
    }
}


void setup() {
    Serial.begin(115200);

    delay(1000);

    /*
     * Khởi tạo QMI8658 và LCD trước đây.
     */

    if (!FallInferenceBegin()) {
        Serial.println(
            "Khoi tao TFLite Micro that bai."
        );

        while (true) {
            delay(1000);
        }
    }

    Serial.println(
        "SafeWatch model san sang."
    );
}


void loop() {
    const uint32_t now = millis();

    if (
        now - g_last_sample_ms
        < kSampleIntervalMs
    ) {
        return;
    }

    /*
     * Giữ lịch 200 ms,
     * hạn chế cộng dồn sai số.
     */
    g_last_sample_ms +=
        kSampleIntervalMs;

    float ax_g = 0.0f;
    float ay_g = 0.0f;
    float az_g = 0.0f;

    if (
        !ReadQmi8658AccelG(
            &ax_g,
            &ay_g,
            &az_g
        )
    ) {
        Serial.println(
            "Khong doc duoc QMI8658."
        );

        return;
    }

    g_accel_ring[g_write_index][0] =
        ax_g;

    g_accel_ring[g_write_index][1] =
        ay_g;

    g_accel_ring[g_write_index][2] =
        az_g;

    g_write_index =
        (
            g_write_index + 1
        ) % kWindowSize;

    if (
        g_sample_count
        < kWindowSize
    ) {
        ++g_sample_count;
    }

    if (
        g_sample_count
        < kWindowSize
    ) {
        return;
    }

    ++g_samples_since_inference;

    if (
        g_samples_since_inference
        < kInferenceStrideSamples
    ) {
        return;
    }

    g_samples_since_inference = 0;

    float
        chronological_window
        [kWindowSize][3];

    CopyRingChronologically(
        chronological_window
    );

    float fall_probability = 0.0f;

    const bool success =
        RunFallInference(
            chronological_window,
            &fall_probability
        );

    if (success) {
        HandlePrediction(
            fall_probability
        );
    }

    else {
        Serial.println(
            "Inference that bai."
        );
    }
}
''',
        encoding="utf-8",
    )

    print("Đã tạo:", arduino_template_path)

    return arduino_template_path
