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
    7;

constexpr int kInferenceStrideSamples =
    5;

constexpr int kClassNonFall =
    0;

constexpr int kClassFall =
    1;

constexpr float kFeatureMean[kFeatureCount] = {
    1.2716496f, 0.368211776f, -0.00104199408f, 0.245181158f, 1.27275443f, 0.468478173f, -0.000902013853f
};

constexpr float kFeatureStd[kFeatureCount] = {
    0.795343518f, 0.755502462f, 0.639513612f, 0.446070611f, 0.687526286f, 0.909933448f, 0.999177337f
};

constexpr float kInputScale =
    0.0747461542487f;

constexpr int kInputZeroPoint =
    11;

constexpr float kOutputScale =
    0.00390625f;

constexpr int kOutputZeroPoint =
    -128;

constexpr float kFallThreshold =
    0.670000f;

constexpr float kHighFallThreshold =
    0.850000f;

constexpr int kConsecutiveRequired =
    2;

constexpr size_t kTensorArenaSize =
    96 * 1024;
