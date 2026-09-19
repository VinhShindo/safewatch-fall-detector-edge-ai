SAFEWATCH PERSON A — MODEL 5 HZ

MODEL
- Input: [1, 20, 7]
- Input dtype: INT8
- Output: [NON_FALL, FALL]
- Tần số: 5 Hz
- Cửa sổ: 4.0 giây
- Chạy inference lại mỗi 1 giây

FEATURES
1. magnitude_g
2. abs(magnitude_g - 1g)
3. delta_magnitude_g
4. acceleration vector angle change
5. sma_magnitude_g (rolling window 3)
6. tail_magnitude_variance (last 10 samples)
7. jerk_magnitude_g

THRESHOLD
- FALL threshold: 0.6700
- HIGH FALL threshold: 0.8500
- Consecutive windows: 2

FILE ESP32
- fall_model_data.h
- fall_model_data.cc
- fall_model_config.h
- fall_inference.h
- fall_inference.cpp
- SafeWatch_Fall_Detector.ino

BẮT BUỘC
1. Nối ReadQmi8658AccelG() với driver QMI8658.
2. Dữ liệu đưa vào phải ở đơn vị g.
3. Nối ShowStatusOnDisplay() với LCD/LVGL.
4. Nối SendFallToBackend() với HTTPS API.
5. Không lưu Telegram Bot Token trên ESP32.
6. Backend C# chịu trách nhiệm gửi Telegram.

Nếu AllocateTensors() thất bại:
- tăng kTensorArenaSize lên 128 * 1024.
