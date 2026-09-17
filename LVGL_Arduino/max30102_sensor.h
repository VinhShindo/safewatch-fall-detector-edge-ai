#ifndef MAX30102_SENSOR_H
#define MAX30102_SENSOR_H

#include <Arduino.h>
#include <Wire.h>
#include "MAX30105.h"

static TwoWire maxI2C = TwoWire(1);
static MAX30105 particleSensor;

static float currentBPM = 0.0f;
static bool fingerDetected = false;
static unsigned long lastBeatTime = 0;
static float prevIRAvg = 0;
static bool rising = false;

static const int IR_BUFFER_SIZE = 40;
static float irBuffer[IR_BUFFER_SIZE];
static int irIndex = 0;

static const int BPM_HISTORY_SIZE = 5;
static float bpmHistory[BPM_HISTORY_SIZE];
static int bpmIndex = 0;

inline void init_max30102() {
  Serial.println("Khởi tạo MAX30102...");
  maxI2C.begin(15, 16);
  maxI2C.setClock(400000);

  if (!particleSensor.begin(maxI2C, 0x57)) {
    Serial.println("LỖI: Không tìm thấy MAX30102!");
    while (1);
  }
  Serial.println("Đã tìm thấy MAX30102. Đặt ngón tay lên và giữ yên.");

  // Tăng cường độ tín hiệu 
  byte ledBrightness = 0x4F;   // 127 (trước là 0x3F = 63)
  byte sampleAverage = 0x04;   // lấy trung bình 4 mẫu (nhanh hơn)
  byte ledMode = 0x02;         // chỉ dùng Red + IR
  byte sampleRate = 0x02;      // 200 Hz
  int pulseWidth = 0x03;       // 411 us
  int adcRange = 0x03;         // 16384 nA

  particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange);
  particleSensor.setPulseAmplitudeRed(0x0A);
  particleSensor.setPulseAmplitudeIR(0x0A);
  particleSensor.setPulseAmplitudeGreen(0);

  for (int i = 0; i < IR_BUFFER_SIZE; i++) irBuffer[i] = 0;
  for (int i = 0; i < BPM_HISTORY_SIZE; i++) bpmHistory[i] = 0;
}

inline void update_max30102() {
  static unsigned long lastRead = 0;
  unsigned long now = millis();
  if (now - lastRead < 10) return;
  lastRead = now;

  float rawIR = particleSensor.getIR();

  // Lưu vào buffer trượt
  irBuffer[irIndex] = rawIR;
  irIndex++;
  if (irIndex >= IR_BUFFER_SIZE) irIndex = 0;

  float irAvg = 0;
  for (int i = 0; i < IR_BUFFER_SIZE; i++) irAvg += irBuffer[i];
  irAvg /= IR_BUFFER_SIZE;

  // Giảm ngưỡng phát hiện ngón tay (từ 50000 xuống 30000)
  fingerDetected = (irAvg > 30000);

  if (!fingerDetected) {
    currentBPM = 0;
    prevIRAvg = irAvg;
    lastBeatTime = 0;
    return;
  }

  // Phát hiện đỉnh nhịp tim bằng đạo hàm
  if (irAvg > prevIRAvg && !rising) {
    rising = true;
  } else if (irAvg < prevIRAvg && rising) {
    rising = false;
    if (lastBeatTime != 0) {
      unsigned long interval = now - lastBeatTime;
      if (interval >= 400 && interval <= 2000) {
        float instantBPM = 60000.0f / interval;
        if (instantBPM >= 40 && instantBPM <= 150) {
          bpmHistory[bpmIndex] = instantBPM;
          bpmIndex++;
          if (bpmIndex >= BPM_HISTORY_SIZE) bpmIndex = 0;

          float sum = 0;
          int count = 0;
          for (int i = 0; i < BPM_HISTORY_SIZE; i++) {
            if (bpmHistory[i] > 0) {
              sum += bpmHistory[i];
              count++;
            }
          }
          if (count > 0) currentBPM = sum / count;
        }
      }
    }
    lastBeatTime = now;
  }
  prevIRAvg = irAvg;
}

inline float get_bpm() {
  return currentBPM;
}

inline bool is_finger_detected() {
  return fingerDetected;
}

#endif