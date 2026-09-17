#ifndef IMU_SENSOR_H
#define IMU_SENSOR_H

#include <Arduino.h>
#include <Wire.h>
#include <QMI8658.h>

// --- Điều chỉnh tham số lọc (giảm alpha -> lọc yếu hơn -> nhạy hơn) ---
const float ALPHA_ACCEL = 0.05f;   // trước 0.06 -> 0.2 (phản ứng nhanh)
const float ALPHA_GYRO  = 0.02f;   // trước 0.03 -> 0.1

// --- Giảm deadzone để không bỏ sót dao động nhỏ ---
const float ACCEL_DEADZONE = 50.0f;   // trước 5.0 mg
const float GYRO_DEADZONE  = 30.0f;   // trước 2.0 mdps

static QMI8658 qmi;

static float rawAccX, rawAccY, rawAccZ;
static float rawGyroX, rawGyroY, rawGyroZ;
static float filtAccX = 0, filtAccY = 0, filtAccZ = 0;
static float filtGyroX = 0, filtGyroY = 0, filtGyroZ = 0;

static float offsetAccX = 0.0f, offsetAccY = 0.0f;
static float offsetGyroX = 0.0f, offsetGyroY = 0.0f, offsetGyroZ = 0.0f;
static bool isCalibrated = false;
static bool serialLogEnabled = false;

static inline float lowPassFilter(float newVal, float prevVal, float alpha, float deadzone) {
  float diff = newVal - prevVal;
  if (fabsf(diff) < deadzone) return prevVal;
  return alpha * newVal + (1.0f - alpha) * prevVal;
}

static inline void calculateAngles(float ax, float ay, float az, float &pitch, float &roll) {
  pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0f / PI;
  roll  = atan2(ay, az) * 180.0f / PI;
}

static inline void get_filtered_data(float &ax, float &ay, float &az, float &gx, float &gy, float &gz) {
  float accX_mg, accY_mg, accZ_mg;
  float gyroX_mdps, gyroY_mdps, gyroZ_mdps;

  if (isCalibrated) {
    accX_mg = filtAccX - offsetAccX;
    accY_mg = filtAccY - offsetAccY;
    gyroX_mdps = filtGyroX - offsetGyroX;
    gyroY_mdps = filtGyroY - offsetGyroY;
    gyroZ_mdps = filtGyroZ - offsetGyroZ;
  } else {
    accX_mg = filtAccX;
    accY_mg = filtAccY;
    gyroX_mdps = filtGyroX;
    gyroY_mdps = filtGyroY;
    gyroZ_mdps = filtGyroZ;
  }
  accZ_mg = -filtAccZ;   // đảo dấu Z

  const float GRAVITY = 9.80665f;
  ax = accX_mg / 1000.0f * GRAVITY;
  ay = accY_mg / 1000.0f * GRAVITY;
  az = accZ_mg / 1000.0f * GRAVITY;

  gx = gyroX_mdps / 1000.0f;
  gy = gyroY_mdps / 1000.0f;
  gz = gyroZ_mdps / 1000.0f;

  // Giảm zero tolerance (giữ nguyên)
  const float ACCEL_ZERO_TOLERANCE = 0.02f;
  const float GYRO_ZERO_TOLERANCE  = 0.002f;
  if (fabsf(ax) < ACCEL_ZERO_TOLERANCE) ax = 0.0f;
  if (fabsf(ay) < ACCEL_ZERO_TOLERANCE) ay = 0.0f;
  if (fabsf(gx) < GYRO_ZERO_TOLERANCE) gx = 0.0f;
  if (fabsf(gy) < GYRO_ZERO_TOLERANCE) gy = 0.0f;
  if (fabsf(gz) < GYRO_ZERO_TOLERANCE) gz = 0.0f;
}

inline void setSerialLogging(bool enable) { serialLogEnabled = enable; }

inline void calibrate_sensor() {
  Serial.println("Đang Calibration... Hãy giữ yên đồng hồ trong 2 giây!");
  float sumAccX = 0, sumAccY = 0;
  float sumGyroX = 0, sumGyroY = 0, sumGyroZ = 0;
  int samples = 200;
  for (int i = 0; i < samples; i++) {
    if (qmi.readAccel(rawAccX, rawAccY, rawAccZ) &&
        qmi.readGyro(rawGyroX, rawGyroY, rawGyroZ)) {
      sumAccX += rawAccX;
      sumAccY += rawAccY;
      sumGyroX += rawGyroX;
      sumGyroY += rawGyroY;
      sumGyroZ += rawGyroZ;
    }
    delay(10);
  }
  offsetAccX = sumAccX / samples;
  offsetAccY = sumAccY / samples;
  offsetGyroX = sumGyroX / samples;
  offsetGyroY = sumGyroY / samples;
  offsetGyroZ = sumGyroZ / samples;
  isCalibrated = true;
  Serial.println("Calibration hoàn tất!");
}

inline void imu_init() {
  Wire.begin(6, 7);
  Wire.setClock(400000);
  if (!qmi.begin(Wire, 0x6B)) {
    Serial.println("Không tìm thấy QMI8658 tại 0x6B, thử 0x6A...");
    if (!qmi.begin(Wire, 0x6A)) {
      Serial.println("LỖI: Không tìm thấy QMI8658!");
    } else {
      Serial.println("Đã tìm thấy QMI8658 tại 0x6A");
    }
  } else {
    Serial.println("Đã tìm thấy QMI8658 tại 0x6B");
  }
  calibrate_sensor();
}

inline void imu_update() {
  if (qmi.readAccel(rawAccX, rawAccY, rawAccZ) &&
      qmi.readGyro(rawGyroX, rawGyroY, rawGyroZ)) {
    filtAccX = lowPassFilter(rawAccX, filtAccX, ALPHA_ACCEL, ACCEL_DEADZONE);
    filtAccY = lowPassFilter(rawAccY, filtAccY, ALPHA_ACCEL, ACCEL_DEADZONE);
    filtAccZ = lowPassFilter(rawAccZ, filtAccZ, ALPHA_ACCEL, ACCEL_DEADZONE);
    filtGyroX = lowPassFilter(rawGyroX, filtGyroX, ALPHA_GYRO, GYRO_DEADZONE);
    filtGyroY = lowPassFilter(rawGyroY, filtGyroY, ALPHA_GYRO, GYRO_DEADZONE);
    filtGyroZ = lowPassFilter(rawGyroZ, filtGyroZ, ALPHA_GYRO, GYRO_DEADZONE);
  }
}

#endif