#ifndef MAX30102_SENSOR_H
#define MAX30102_SENSOR_H

#include <Arduino.h>
#include <Wire.h>
#include "MAX30105.h"
#include "spo2_algorithm.h"

static TwoWire maxI2C = TwoWire(1);
static MAX30105 particleSensor;
static bool max30102BusStarted = false;
static bool max30102Available = false;

static float currentBPM = 0.0f;
static bool fingerDetected = false;
static unsigned long lastBeatTime = 0;
static float prevIRAvg = 0;
static bool rising = false;

static const int IR_BUFFER_SIZE = 40;
static float irBuffer[IR_BUFFER_SIZE];
static int irIndex = 0;
static int irSamplesFilled = 0;

static const int BPM_HISTORY_SIZE = 5;
static float bpmHistory[BPM_HISTORY_SIZE];
static int bpmIndex = 0;
static int pendingBpm = 0;
static uint8_t pendingBpmCount = 0;
static uint8_t redLedCurrent = 0x10;
static uint8_t irLedCurrent = 0x10;
static constexpr uint8_t MIN_LED_CURRENT = 0x04;
static constexpr int SPO2_RECALCULATE_SAMPLES = 25;
static uint32_t spo2IrRing[BUFFER_SIZE];
static uint32_t spo2RedRing[BUFFER_SIZE];
static uint32_t spo2IrWindow[BUFFER_SIZE];
static uint32_t spo2RedWindow[BUFFER_SIZE];
static int spo2WriteIndex = 0;
static int spo2SampleCount = 0;
static int spo2SamplesSinceCalculation = 0;
static int spo2History[BPM_HISTORY_SIZE];
static int spo2HistoryIndex = 0;
static int spo2HistoryCount = 0;
static volatile int currentSpO2 = 0;
static volatile bool currentSpO2Valid = false;

inline int get_spo2();
inline bool is_spo2_valid();

static int medianOfValues(const float *values, int count) {
  float sorted[BPM_HISTORY_SIZE];
  for (int i = 0; i < count; ++i) sorted[i] = values[i];
  for (int i = 1; i < count; ++i) {
    const float value = sorted[i];
    int j = i - 1;
    while (j >= 0 && sorted[j] > value) {
      sorted[j + 1] = sorted[j];
      --j;
    }
    sorted[j + 1] = value;
  }
  return static_cast<int>(lroundf(sorted[count / 2]));
}

static void addSpO2Sample(uint32_t ir, uint32_t red) {
  spo2IrRing[spo2WriteIndex] = ir;
  spo2RedRing[spo2WriteIndex] = red;
  spo2WriteIndex = (spo2WriteIndex + 1) % BUFFER_SIZE;
  if (spo2SampleCount < BUFFER_SIZE) ++spo2SampleCount;
  if (spo2SampleCount < BUFFER_SIZE) return;
  if (++spo2SamplesSinceCalculation < SPO2_RECALCULATE_SAMPLES) return;
  spo2SamplesSinceCalculation = 0;

  for (int index = 0; index < BUFFER_SIZE; ++index) {
    const int sourceIndex = (spo2WriteIndex + index) % BUFFER_SIZE;
    spo2IrWindow[index] = spo2IrRing[sourceIndex];
    spo2RedWindow[index] = spo2RedRing[sourceIndex];
  }

  int32_t calculatedSpO2 = 0;
  int32_t calculatedHeartRate = 0;
  int8_t validSpO2 = 0;
  int8_t validHeartRate = 0;
  maxim_heart_rate_and_oxygen_saturation(
      spo2IrWindow, BUFFER_SIZE, spo2RedWindow,
      &calculatedSpO2, &validSpO2, &calculatedHeartRate, &validHeartRate);
  if (validSpO2 == 1 && calculatedSpO2 >= 70 && calculatedSpO2 <= 100) {
    spo2History[spo2HistoryIndex] = calculatedSpO2;
    spo2HistoryIndex = (spo2HistoryIndex + 1) % BPM_HISTORY_SIZE;
    if (spo2HistoryCount < BPM_HISTORY_SIZE) ++spo2HistoryCount;
    float values[BPM_HISTORY_SIZE];
    for (int i = 0; i < spo2HistoryCount; ++i) values[i] = static_cast<float>(spo2History[i]);
    currentSpO2 = medianOfValues(values, spo2HistoryCount);
    currentSpO2Valid = true;
  }
  (void)calculatedHeartRate;
  (void)validHeartRate;
}

static void resetVitalHistory() {
  bpmIndex = 0;
  pendingBpm = 0;
  pendingBpmCount = 0;
  lastBeatTime = 0;
  prevIRAvg = 0;
  rising = false;
  spo2WriteIndex = 0;
  spo2SampleCount = 0;
  spo2SamplesSinceCalculation = 0;
  spo2HistoryIndex = 0;
  spo2HistoryCount = 0;
  currentBPM = 0;
  currentSpO2 = 0;
  currentSpO2Valid = false;
  for (int i = 0; i < BPM_HISTORY_SIZE; ++i) {
    bpmHistory[i] = 0;
    spo2History[i] = 0;
  }
}

inline bool init_max30102() {
  Serial.println("Khởi tạo MAX30102...");
  if (!max30102BusStarted) {
    maxI2C.begin(15, 16);
    maxI2C.setClock(I2C_SPEED_FAST);
    max30102BusStarted = true;
  }

  if (!particleSensor.begin(maxI2C, I2C_SPEED_FAST, MAX30105_ADDRESS)) {
    maxI2C.beginTransmission(MAX30105_ADDRESS);
    const uint8_t i2cStatus = maxI2C.endTransmission();
    Serial.printf("LỖI: Không tìm thấy MAX30102 tại 0x57 (I2C status=%u).\n", i2cStatus);
    max30102Available = false;
    return false;
  }
  Serial.println("Đã tìm thấy MAX30102. Đặt ngón tay lên và giữ yên.");

  byte ledBrightness = 0x10;
  byte sampleAverage = 0x04;   // lấy trung bình 4 mẫu (nhanh hơn)
  byte ledMode = 0x02;         // chỉ dùng Red + IR
  int sampleRate = 100;        // 100 Hz, averaged by four to the algorithm's 25 Hz
  int pulseWidth = 411;        // 411 us
  int adcRange = 4096;         // MAX30102 reference configuration

  particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange);
  redLedCurrent = ledBrightness;
  irLedCurrent = ledBrightness;
  particleSensor.setPulseAmplitudeRed(redLedCurrent);
  particleSensor.setPulseAmplitudeIR(irLedCurrent);
  particleSensor.setPulseAmplitudeGreen(0);

  for (int i = 0; i < IR_BUFFER_SIZE; i++) irBuffer[i] = 0;
  irIndex = 0;
  irSamplesFilled = 0;
  resetVitalHistory();
  max30102Available = true;
  return true;
}

inline void update_max30102() {
  if (!max30102Available) return;
  particleSensor.check();
  bool discardCurrentBatch = false;
  while (particleSensor.available()) {
    const unsigned long now = millis();
    const uint32_t rawIR = particleSensor.getFIFOIR();
    const uint32_t rawRed = particleSensor.getFIFORed();
    particleSensor.nextSample();
    if (discardCurrentBatch) continue;

    if (rawIR >= 245000 || rawRed >= 245000) {
      const uint8_t previousRedCurrent = redLedCurrent;
      const uint8_t previousIrCurrent = irLedCurrent;
      redLedCurrent = max(MIN_LED_CURRENT, static_cast<uint8_t>(redLedCurrent / 2));
      irLedCurrent = max(MIN_LED_CURRENT, static_cast<uint8_t>(irLedCurrent / 2));
      if (redLedCurrent != previousRedCurrent || irLedCurrent != previousIrCurrent) {
        particleSensor.setPulseAmplitudeRed(redLedCurrent);
        particleSensor.setPulseAmplitudeIR(irLedCurrent);
        resetVitalHistory();
        Serial.printf("[MAX30102] Optical saturation; reducing LED current RED=0x%02X IR=0x%02X\n",
                      redLedCurrent, irLedCurrent);
      } else {
        resetVitalHistory();
        Serial.println("[MAX30102] Signal remains saturated at minimum LED current.");
      }
      discardCurrentBatch = true;
      continue;
    }

    irBuffer[irIndex] = static_cast<float>(rawIR);
    irIndex = (irIndex + 1) % IR_BUFFER_SIZE;
    if (irSamplesFilled < IR_BUFFER_SIZE) ++irSamplesFilled;
    float irAvg = 0;
    for (int i = 0; i < irSamplesFilled; ++i) irAvg += irBuffer[i];
    irAvg /= irSamplesFilled;
    fingerDetected = irAvg > 30000;

    static unsigned long lastDiagnosticsMs = 0;
    if (now - lastDiagnosticsMs >= 5000) {
      lastDiagnosticsMs = now;
      Serial.printf("[MAX30102] rawIR=%lu rawRed=%lu avgIR=%.0f finger=%d BPM=%.0f SpO2=%d valid=%d samples=%d LED=%02X/%02X\n",
            static_cast<unsigned long>(rawIR), static_cast<unsigned long>(rawRed), irAvg, fingerDetected,
            currentBPM, get_spo2(), is_spo2_valid(), spo2SampleCount, redLedCurrent, irLedCurrent);
    }

    if (!fingerDetected) {
      resetVitalHistory();
      prevIRAvg = irAvg;
      continue;
    }

    addSpO2Sample(rawIR, rawRed);

    if (irAvg > prevIRAvg && !rising) {
      rising = true;
    } else if (irAvg < prevIRAvg && rising) {
      rising = false;
      if (lastBeatTime != 0) {
        const unsigned long interval = now - lastBeatTime;
        if (interval >= 400 && interval <= 2000) {
          const float instantBPM = 60000.0f / interval;
          if (instantBPM >= 40 && instantBPM <= 150) {
            bpmHistory[bpmIndex] = instantBPM;
            bpmIndex = (bpmIndex + 1) % BPM_HISTORY_SIZE;
            float sum = 0;
            int count = 0;
            for (int i = 0; i < BPM_HISTORY_SIZE; ++i) {
              if (bpmHistory[i] > 0) { sum += bpmHistory[i]; ++count; }
            }
            if (count > 0) currentBPM = sum / count;
          }
        }
      }
      lastBeatTime = now;
    }
    prevIRAvg = irAvg;
  }
}

inline float get_bpm() {
  return currentBPM;
}

inline bool is_finger_detected() {
  return fingerDetected;
}

inline int get_spo2() {
  return currentSpO2Valid ? currentSpO2 : 0;
}

inline bool is_spo2_valid() {
  return currentSpO2Valid;
}

#endif