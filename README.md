<div align="center">

# ⌚ SafeWatch — Edge AI Fall Detection Smartwatch

**Đồng hồ thông minh phát hiện té ngã bằng AI nhúng trực tiếp trên chip — không cần cloud để quyết định.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-ESP32--S3-blue)]()
[![TensorFlow Lite Micro](https://img.shields.io/badge/TFLite-Micro-orange)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![Made in Vietnam](https://img.shields.io/badge/made%20in-Vietnam-red)]()

<img src="docs/images/watch.jpg" alt="SafeWatch" width="320"/>

</div>

---

## 📖 Giới thiệu

**SafeWatch** là một đồng hồ thông minh tự chế dựa trên **ESP32-S3**, có khả năng:

- 🧠 **Phát hiện té ngã bằng AI ngay tại thiết bị** (TFLite Micro, model INT8 ~20 KB)
- 💓 Đo nhịp tim realtime bằng cảm biến **MAX30102**
- 📡 Gửi **cảnh báo khẩn cấp về backend C#** khi xác nhận té ngã
- 📲 Backend chuyển tiếp cảnh báo qua **Telegram Bot**
- 🖥️ Giao diện đồng hồ đẹp mắt với **LVGL 8** trên màn hình TFT 240×240
- ⚙️ **Captive portal** để cấu hình WiFi & địa chỉ backend không cần nạp lại code

> **Điểm khác biệt:** Toàn bộ suy luận AI chạy **trên chip ESP32-S3** — không phụ thuộc cloud, phản hồi < 100 ms, hoạt động cả khi mất mạng. Đây là mô hình **Edge AI** thực thụ.

---

## 🎬 Demo

| Phát hiện té ngã | Giao diện đồng hồ | Cấu hình WiFi |
|:---:|:---:|:---:|
| ![fall](docs/images/demo_fall.gif) | ![ui](docs/images/demo_ui.gif) | ![wifi](docs/images/demo_wifi.gif) |

📺 Video demo đầy đủ: [YouTube link]

---

## ✨ Tính năng chi tiết

### 🧠 AI Fall Detection (Edge)
- Model CNN 1D (`Conv1D ×2 → GAP → Dense → Softmax`) huấn luyện trên **WEDA-FALL + dữ liệu tự thu (QMI)**
- 4 đặc trưng/cửa sổ, cửa sổ 4 giây @ 5 Hz (20 mẫu)
- Quantize **INT8** → giảm dung lượng còn ~20 KB, chạy realtime trên ESP32
- Ngưỡng **0.85** + cơ chế **2 cửa sổ liên tiếp** để tránh false positive
- Đếm ngược SOS 10 giây, cho phép người dùng **hủy** nếu báo nhầm

### 💓 Sức khỏe
- Nhịp tim (BPM) từ MAX30102, phát hiện đỉnh bằng đạo hàm
- Lọc trung bình trượt (5 mẫu gần nhất)
- Phát hiện có/không có ngón tay

### 🔋 Phần cứng & Nguồn
- Đọc pin qua ADC, hiệu chỉnh 3 điểm, ước lượng % theo đường cong discharge
- Hiển thị trạng thái sạc, icon pin động

### 🌐 Kết nối
- WiFi STA + fallback AP mode
- NTP đồng bộ giờ (timezone UTC+7)
- Web server cấu hình (`/` cho WiFi, `/config` cho backend)
- Lưu credentials vào NVS (`Preferences`)

### 🔔 Cảnh báo
- Gửi JSON POST đến backend C#: `timestamp`, `confidence`, `heart_rate`, `battery`, `rssi`, `accel`, `gyro`
- Backend xác thực device ID + forward Telegram
- **Không lưu token Telegram trên thiết bị** (bảo mật)

---

## 🏗️ Kiến trúc hệ thống

```
┌──────────────────────────────────────────────────────────┐
│                    SafeWatch (ESP32-S3)                  │
│                                                          │
│  QMI8658 (IMU) ──┐                                       │
│                  ├──► Low-pass filter ──► 20-sample ring │
│  MAX30102 ───────┘                            │          │
│                                               ▼          │
│                                     Feature extraction   │
│                                     (4 features/sample)  │
│                                               ▼          │
│                              ┌────────────────────────┐  │
│                              │  TFLite Micro INT8     │  │
│                              │  CNN 1D Fall Detector  │  │
│                              │  Input: [1, 20, 4]     │  │
│                              │  Output: P(fall)       │  │
│                              └────────────┬───────────┘  │
│                                           ▼              │
│                              P(fall) ≥ 0.85 → SOS UI     │
│                                           ▼              │
│                              HTTP POST JSON              │
└───────────────────────────────────────────┼──────────────┘
                                            ▼
                            ┌────────────────────────────┐
                            │   Backend C# ASP.NET Core  │
                            │   /alert  (POST)           │
                            │   ↓                        │
                            │   Telegram Bot API         │
                            └────────────────────────────┘
                                            ▼
                                      📱 Người thân
```

Chi tiết: [`docs/architecture.md`](docs/architecture.md)

---

## 🧰 Phần cứng (Bill of Materials)

| Linh kiện | Model | SL | Ghi chú |
|-----------|-------|----|---------|
| MCU | ESP32-S3 (8 MB PSRAM) | 1 | VD: Waveshare ESP32-S3-Touch-LCD-1.28 |
| IMU | QMI8658 (6-axis) | 1 | I2C 0x6B, SDA=6, SCL=7 |
| HR sensor | MAX30102 | 1 | I2C 0x57, SDA=15, SCL=16 |
| Display | ST7789 240×240 | 1 | Qua SPI |
| Touch | CST816S | 1 | I2C |
| Pin | Li-Po 3.7V 500 mAh | 1 | PIN_BATTERY = GPIO1 |

Chi tiết đấu dây: [`docs/wiring.md`](firmware/docs/wiring.md)

---

## 🚀 Cài đặt & Build

### 1. Firmware (ESP32-S3)

**Yêu cầu:**
- Arduino IDE 2.x **hoặc** PlatformIO
- Board package: `esp32 by Espressif` ≥ 3.0.0
- Thư viện:
  - `lvgl` ≥ 8.3
  - `TFT_eSPI` (cấu hình `User_Setup.h` cho ST7789)
  - `TensorFlowLite_ESP32`
  - `QMI8658`
  - `MAX30105`
  - `CST816S`
  - `ArduinoJson` ≥ 6.x
  - `NTPClient`
  - `Preferences` (built-in)

```bash
git clone https://github.com/<user>/safewatch.git
cd safewatch/firmware
# Mở main.cpp bằng Arduino IDE hoặc:
pio run -t upload
```

### 2. Training pipeline (Python)

```bash
cd training
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Dữ liệu đã chuẩn bị tại data/raw/QMI và data/raw/WEDA-FALL/dataset/5Hz
source /home/vinh_shindo/FuelSentinel-AI/.venv/bin/activate
cd src && PYTHONPATH=. python3 train.py
```

Script sẽ xuất ra:
- `weda_pretrained_5hz.keras`
- `person_a_finetuned_5hz.keras`
- `safewatch_person_a_5hz_int8.tflite`
- `fall_model_data.h/.cc`, `fall_model_config.h`
- `fall_inference.h/.cpp`
- `SafeWatch_Fall_Detector.ino`
- Package ZIP sẵn sàng nạp vào firmware.

### 3. Backend (C# ASP.NET Core)

```bash
cd backend
dotnet restore
dotnet run --urls "http://0.0.0.0:5000"
```

Cấu hình Telegram Bot Token trong `appsettings.json`:

```json
{
  "Telegram": {
    "BotToken": "YOUR_BOT_TOKEN",
    "ChatId": "YOUR_CHAT_ID"
  },
  "Devices": {
    "AllowedIds": ["SW-0005"]
  }
}
```

---

## 📊 Hiệu năng model

| Chỉ số | Giá trị |
|--------|--------|
| Input shape | `[1, 20, 4]` INT8 |
| Output | Softmax 2 lớp (NonFall / Fall) |
| Kích thước model | ~20 KB |
| Tensor arena | 70 KB |
| Thời gian suy luận | ~15–25 ms (ESP32-S3 @ 240 MHz) |
| Tần số lấy mẫu | 5 Hz (200 ms/mẫu) |
| Cửa sổ | 4 giây (20 mẫu) |
| Stride suy luận | 5 mẫu (1 giây/lần) |
| Ngưỡng cảnh báo | P(fall) ≥ 0.85 |

Chi tiết huấn luyện: [`docs/ai-model.md`](docs/ai-model.md)

---

## 🔌 API Backend

**POST** `/alert`

```json
{
  "timestamp": "2026-09-16T03:21:45Z",
  "type": "fall",
  "confidence": 0.923,
  "heart_rate": 82,
  "battery": 67,
  "rssi": -58,
  "accel": { "ax": 0.12, "ay": -0.05, "az": 1.02 },
  "gyro":  { "gx": 12.3, "gy": -4.1, "gz": 0.9 }
}
```

Headers:
```
Content-Type: application/json
X-Device-Id: SW-0005
```

Response `200 OK` → backend gửi Telegram.

Chi tiết: [`docs/api-reference.md`](docs/api-reference.md)

---

## 🗺️ Roadmap

- [x] Firmware ESP32-S3 với TFLite Micro
- [x] Training pipeline cho model 5 Hz
- [x] Backend C# + Telegram
- [ ] OTA update qua WiFi
- [ ] Bổ sung gyroscope vào model (6 features)
- [ ] Sleep mode + wake on motion
- [ ] App mobile (Flutter) thay vì captive portal
- [ ] Hỗ trợ đa người dùng (multi-device)

---

## 🤝 Đóng góp

Mọi đóng góp đều được chào đón! Đọc [`CONTRIBUTING.md`](CONTRIBUTING.md) trước khi mở PR.

---

## 📄 Giấy phép

Dự án phát hành dưới giấy phép **MIT** — xem [`LICENSE`](LICENSE).

---

## 🙏 Ghi nhận

- Dataset [**WEDA-FALL**](https://github.com/joaojtmarques/WEDA-FALL) — João Marques et al.
- [TensorFlow Lite Micro](https://github.com/tensorflow/tflite-micro)
- [LVGL](https://lvgl.io/)

---

## 📬 Liên hệ

**Tác giả:** [Tên bạn]  
**Email:** [email của bạn]  
**Facebook / LinkedIn:** [link]  

> Nếu bạn thấy dự án hữu ích, hãy ⭐ repo này nhé!