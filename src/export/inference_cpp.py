# -*- coding: utf-8 -*-
"""
inference_cpp.py
==================
Sinh file C++ chạy inference bằng TensorFlow Lite Micro trên thiết
bị nhúng (đọc cửa sổ gia tốc thô -> tính feature -> lượng tử hóa ->
chạy interpreter -> giải lượng tử -> trả xác suất FALL).

Nguồn gốc trong notebook Colab: Cell 24
"""

from pathlib import Path

from utils.config import OUTPUT_DIR, ensure_output_dir


def export_inference_cpp(output_dir: Path = OUTPUT_DIR):
    """(Cell 24)"""
    ensure_output_dir()

    inference_header_path = output_dir / "fall_inference.h"
    inference_source_path = output_dir / "fall_inference.cpp"

    inference_header_path.write_text(
        """#pragma once

#include "fall_model_config.h"

bool FallInferenceBegin();

bool RunFallInference(
    const float accel_window_g[kWindowSize][3],
    float* fall_probability
);
""",
        encoding="utf-8",
    )

    inference_source_path.write_text(
        r'''#include "fall_inference.h"

#include <cmath>
#include <cstdint>

#include "fall_model_data.h"

#include "tensorflow/lite/micro/all_ops_resolver.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "tensorflow/lite/version.h"

namespace {

alignas(16)
uint8_t g_tensor_arena[kTensorArenaSize];

const tflite::Model* g_model = nullptr;

tflite::MicroInterpreter*
    g_interpreter = nullptr;

TfLiteTensor* g_input = nullptr;
TfLiteTensor* g_output = nullptr;


float Clamp(
    float value,
    float minimum,
    float maximum
) {
    if (value < minimum) {
        return minimum;
    }

    if (value > maximum) {
        return maximum;
    }

    return value;
}


int8_t QuantizeFeature(
    float value,
    int feature_index
) {
    const float normalized =
        (
            value
            - kFeatureMean[feature_index]
        )
        / kFeatureStd[feature_index];

    int quantized =
        static_cast<int>(
            std::lround(
                normalized
                / kInputScale
            )
        )
        + kInputZeroPoint;

    if (quantized < -128) {
        quantized = -128;
    }

    if (quantized > 127) {
        quantized = 127;
    }

    return static_cast<int8_t>(
        quantized
    );
}


float DequantizeOutput(
    int8_t value
) {
    return (
        static_cast<int>(value)
        - kOutputZeroPoint
    ) * kOutputScale;
}

}  // namespace


bool FallInferenceBegin() {
    g_model = tflite::GetModel(
        g_fall_model_data
    );

    if (
        g_model->version()
        != TFLITE_SCHEMA_VERSION
    ) {
        return false;
    }

    static tflite::AllOpsResolver
        resolver;

    static tflite::MicroInterpreter
        static_interpreter(
            g_model,
            resolver,
            g_tensor_arena,
            kTensorArenaSize
        );

    g_interpreter =
        &static_interpreter;

    if (
        g_interpreter
            ->AllocateTensors()
        != kTfLiteOk
    ) {
        return false;
    }

    g_input =
        g_interpreter->input(0);

    g_output =
        g_interpreter->output(0);

    if (
        g_input == nullptr
        || g_output == nullptr
        || g_input->type
            != kTfLiteInt8
        || g_output->type
            != kTfLiteInt8
    ) {
        return false;
    }

    return true;
}


bool RunFallInference(
    const float
        accel_window_g[kWindowSize][3],

    float* fall_probability
) {
    if (
        g_interpreter == nullptr
        || g_input == nullptr
        || g_output == nullptr
        || fall_probability == nullptr
    ) {
        return false;
    }

    int tensor_index = 0;

    float previous_x =
        accel_window_g[0][0];

    float previous_y =
        accel_window_g[0][1];

    float previous_z =
        accel_window_g[0][2];

    float previous_magnitude =
        std::sqrt(
            previous_x * previous_x
            + previous_y * previous_y
            + previous_z * previous_z
        );

    for (
        int sample = 0;
        sample < kWindowSize;
        ++sample
    ) {
        const float x =
            accel_window_g[sample][0];

        const float y =
            accel_window_g[sample][1];

        const float z =
            accel_window_g[sample][2];

        const float magnitude =
            std::sqrt(
                x * x
                + y * y
                + z * z
            );

        const float deviation =
            std::fabs(
                magnitude - 1.0f
            );

        float delta_magnitude = 0.0f;
        float angle_change = 0.0f;

        if (sample > 0) {
            delta_magnitude =
                magnitude
                - previous_magnitude;

            const float denominator =
                std::fmax(
                    previous_magnitude
                    * magnitude,
                    1e-6f
                );

            const float dot_product =
                previous_x * x
                + previous_y * y
                + previous_z * z;

            const float cosine =
                Clamp(
                    dot_product
                    / denominator,
                    -1.0f,
                    1.0f
                );

            angle_change =
                std::acos(cosine);
        }

        const float
            features[kFeatureCount] = {
                magnitude,
                deviation,
                delta_magnitude,
                angle_change
            };

        for (
            int feature = 0;
            feature < kFeatureCount;
            ++feature
        ) {
            g_input
                ->data
                .int8[tensor_index++] =
                    QuantizeFeature(
                        features[feature],
                        feature
                    );
        }

        previous_x = x;
        previous_y = y;
        previous_z = z;

        previous_magnitude =
            magnitude;
    }

    if (
        g_interpreter->Invoke()
        != kTfLiteOk
    ) {
        return false;
    }

    *fall_probability =
        DequantizeOutput(
            g_output
                ->data
                .int8[kClassFall]
        );

    return true;
}
''',
        encoding="utf-8",
    )

    print("Đã tạo:")
    print("-", inference_header_path)
    print("-", inference_source_path)

    return inference_header_path, inference_source_path
