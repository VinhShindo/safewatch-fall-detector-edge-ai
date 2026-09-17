#pragma once

#include <cstddef>
#include <cstdint>

constexpr int kSampleRateHz =
    5;

constexpr uint32_t kSampleIntervalMs =
    200;

constexpr int kWindowSize =
    20;

constexpr int kFeatureCount =
    4;

constexpr int kInferenceStrideSamples =
    5;

constexpr int kClassNonFall =
    0;

constexpr int kClassFall =
    1;

constexpr float kFeatureMean[kFeatureCount] = {
    1.06550443f, 0.201837435f, -0.00276578846f, 0.239764288f
};

constexpr float kFeatureStd[kFeatureCount] = {
    0.45514974f, 0.413175732f, 0.553217053f, 0.439213574f
};

constexpr float kInputScale =
    0.0918425768614f;

constexpr int kInputZeroPoint =
    -23;

constexpr float kOutputScale =
    0.00390625f;

constexpr int kOutputZeroPoint =
    -128;

constexpr float kFallThreshold =
    0.710000f;

constexpr float kHighFallThreshold =
    0.860000f;

constexpr int kConsecutiveRequired =
    2;

constexpr size_t kTensorArenaSize =
    96 * 1024;
