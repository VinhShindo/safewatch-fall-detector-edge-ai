#pragma once

#include "fall_model_config.h"

bool FallInferenceBegin();

bool RunFallInference(
    const float accel_window_g[kWindowSize][3],
    float* fall_probability
);
