#include <lvgl.h>
#include <TFT_eSPI.h>
#include "lv_conf.h"
#include "CST816S.h"
#include "imu_sensor.h"
#include "max30102_sensor.h"
#include "fall_model_data.h"

#include <TensorFlowLite_ESP32.h>
#include <tensorflow/lite/micro/all_ops_resolver.h>
#include <tensorflow/lite/micro/micro_error_reporter.h>
#include <tensorflow/lite/micro/micro_interpreter.h>
#include <tensorflow/lite/schema/schema_generated.h>
#include <tensorflow/lite/c/common.h>

#include <WiFi.h>
#include <WiFiUdp.h>
#include <NTPClient.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <time.h>
#include <math.h>
#include <esp32-hal-psram.h>

// --------------------------- Cấu hình người dùng ---------------------------
static constexpr long GMT_OFFSET_SECONDS = 7L * 3600L;   // UTC+7
#define USE_REAL_HEART_RATE 1

// ========== CẤU HÌNH MODEL (từ notebook) ==========
#define FALL_SAMPLE_INTERVAL_MS  200     // 5 Hz
#define NUM_FEATURES              4
#define FALL_WINDOW_SAMPLES       20      // 4 giây
static int FALL_MODEL_INPUT_LEN = FALL_WINDOW_SAMPLES * NUM_FEATURES;  // 80

static const float FEATURE_MEAN[NUM_FEATURES] = {
  1.0655044f,
  0.20183744f,
  -0.00276579f,
  0.23976429f
};

static const float FEATURE_STD[NUM_FEATURES] = {
  0.45514974f,
  0.41317573f,
  0.55321705f,
  0.4392136f
};
#define FALL_THRESHOLD          0.85f

static float accelWindow[FALL_WINDOW_SAMPLES][3];
static int   windowSampleIndex = 0;
static unsigned long lastFallSampleTime = 0;

// --------------------------- Cấu hình board --------------------------------
static constexpr uint16_t SCREEN_WIDTH = 240;
static constexpr uint16_t SCREEN_HEIGHT = 240;

static constexpr uint8_t PIN_I2C_SDA = 6;
static constexpr uint8_t PIN_I2C_SCL = 7;
static constexpr uint8_t PIN_BATTERY = 1;
static constexpr uint8_t PIN_BACKLIGHT = 2;

TFT_eSPI tft = TFT_eSPI();
CST816S touch(6, 7, 13, 5);

WebServer server(80);
Preferences preferences;
String apiHost = "";
int apiPort = 5248;
String backendUrl = "";

// --------------- NTP Client -------------------
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 0, 60000); // offset 0, giờ UTC


#define FALL_COOLDOWN_MS 10000

static bool fallDetected = false;
static bool sosActive = false;
static unsigned long sosStartTime = 0;
static unsigned long sosDismissTime = 0;
static bool fallCooldown = false;

static int sosCountdown = 10;
static unsigned long sosCountdownTimer = 0;
static lv_obj_t *countdownLabel = nullptr;

// Lưu điểm số ngã khi phát hiện, dùng để gửi vào cảnh báo sau đếm ngược
static float lastFallScore = 0.0f;
static int currentBatteryPercent = 0;   // lưu % pin cập nhật liên tục
static int currentWiFiRSSI = 0;   // cường độ tín hiệu WiFi (dBm)

// TensorFlow Lite objects
namespace {
tflite::MicroErrorReporter micro_error_reporter;
tflite::AllOpsResolver resolver;
const tflite::Model *model = nullptr;
tflite::MicroInterpreter *interpreter = nullptr;
TfLiteTensor *input_tensor = nullptr;
TfLiteTensor *output_tensor = nullptr;
constexpr int kTensorArenaSize = 70 * 1024;
uint8_t tensor_arena[kTensorArenaSize];
}

// --------------------------- LVGL Buffer --------------------------------
static lv_disp_draw_buf_t drawBuffer;
static lv_color_t *lvBuffer = nullptr;
static constexpr uint16_t LVGL_BUF_ROWS = 10;

// ------------------------------- UI Objects --------------------------------
static lv_obj_t *batteryArc, *batteryLabel, *batteryIconLabel, *pinBox;
static lv_obj_t *timeLabel, *dateLabel;
static lv_obj_t *heartCard, *heartIcon, *heartRateLabel, *heartBpmLabel;
static lv_obj_t *statusCard, *statusIcon, *statusLabel;
static lv_obj_t *sosOverlay = NULL;

#define FONT_TIME_BIG &lv_font_montserrat_32
#define FONT_TIME_SMALL &lv_font_montserrat_16
#define FONT_HEART_RATE &lv_font_montserrat_34
#define FONT_NORMAL &lv_font_montserrat_14

#if LV_USE_LOG != 0
void my_print(const char *buf) { Serial.printf(buf); Serial.flush(); }
#endif

static lv_color_t rgb(uint32_t hex) { return lv_color_hex(hex); }
static void setObjectNoScroll(lv_obj_t *obj) { lv_obj_clear_flag(obj, LV_OBJ_FLAG_SCROLLABLE); }

static void displayFlush(lv_disp_drv_t *disp_drv, const lv_area_t *area, lv_color_t *color_p) {
  uint32_t w = (area->x2 - area->x1 + 1);
  uint32_t h = (area->y2 - area->y1 + 1);
  tft.startWrite();
  tft.setAddrWindow(area->x1, area->y1, w, h);
  tft.pushColors((uint16_t *)&color_p->full, w * h, true);
  tft.endWrite();
  lv_disp_flush_ready(disp_drv);
}

void my_touchpad_read(lv_indev_drv_t *indev_drv, lv_indev_data_t *data) {
  bool touched = touch.available();
  if (!touched) {
    data->state = LV_INDEV_STATE_REL;
  } else {
    data->state = LV_INDEV_STATE_PR;
    data->point.x = touch.data.x;
    data->point.y = SCREEN_HEIGHT - 1 - touch.data.y;
  }
}

static lv_obj_t *createLabel(lv_obj_t *parent, const char *text, const lv_font_t *font, lv_color_t color) {
  lv_obj_t *label = lv_label_create(parent);
  lv_label_set_text(label, text);
  lv_obj_set_style_text_font(label, font, 0);
  lv_obj_set_style_text_color(label, color, 0);
  return label;
}

// ================== SOS UI ==================
static void dismissSOS() {
  if (sosActive) {
    lv_obj_add_flag(sosOverlay, LV_OBJ_FLAG_HIDDEN);
    sosActive = false;
    fallDetected = false;
    fallCooldown = true;
    sosDismissTime = millis();
    windowSampleIndex = 0;
    Serial.println("SOS dismissed by user, no alert sent.");
  }
}

static void showSosScreen() {
  sosStartTime = millis();
  sosCountdown = 10;
  sosCountdownTimer = millis();
  lv_label_set_text(countdownLabel, "10");
  lv_obj_clear_flag(sosOverlay, LV_OBJ_FLAG_HIDDEN);
}

static void createSosOverlay() {
  sosOverlay = lv_obj_create(lv_scr_act());
  lv_obj_set_size(sosOverlay, SCREEN_WIDTH, SCREEN_HEIGHT);
  lv_obj_set_pos(sosOverlay, 0, 0);
  lv_obj_set_style_bg_color(sosOverlay, rgb(0xCC0000), 0);
  lv_obj_set_style_bg_opa(sosOverlay, LV_OPA_80, 0);
  lv_obj_set_style_border_width(sosOverlay, 0, 0);
  lv_obj_add_flag(sosOverlay, LV_OBJ_FLAG_CLICKABLE);
  lv_obj_add_flag(sosOverlay, LV_OBJ_FLAG_HIDDEN);

  lv_obj_t *sosLabel = lv_label_create(sosOverlay);
  lv_label_set_text(sosLabel, "SOS");
  lv_obj_set_style_text_color(sosLabel, rgb(0xFFFFFF), 0);
  lv_obj_set_style_text_font(sosLabel, &lv_font_montserrat_48, 0);
  lv_obj_align(sosLabel, LV_ALIGN_CENTER, 0, 0);

  countdownLabel = lv_label_create(sosOverlay);
  lv_label_set_text(countdownLabel, "10");
  lv_obj_set_style_text_color(countdownLabel, rgb(0xFFFF00), 0);
  lv_obj_set_style_text_font(countdownLabel, &lv_font_montserrat_28, 0);
  lv_obj_align(countdownLabel, LV_ALIGN_TOP_MID, 0, 10);

  lv_obj_t *tapLabel = lv_label_create(sosOverlay);
  lv_label_set_text(tapLabel, "Tap to dismiss");
  lv_obj_set_style_text_color(tapLabel, rgb(0xCCCCCC), 0);
  lv_obj_set_style_text_font(tapLabel, &lv_font_montserrat_16, 0);
  lv_obj_align(tapLabel, LV_ALIGN_CENTER, 0, 65);

  lv_obj_add_event_cb(sosOverlay, [](lv_event_t *e) {
    if (sosActive) {
      dismissSOS();
    }
  }, LV_EVENT_CLICKED, NULL);
}

// ================== MAIN UI ==================
static void createWatchUi() {
  lv_obj_t *screen = lv_scr_act();
  setObjectNoScroll(screen);
  lv_obj_set_style_bg_color(screen, rgb(0x0A0D15), 0);
  lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, 0);

  batteryArc = lv_arc_create(screen);
  lv_obj_set_size(batteryArc, 224, 224);
  lv_obj_center(batteryArc);
  lv_arc_set_rotation(batteryArc, 135);
  lv_arc_set_bg_angles(batteryArc, 0, 270);
  lv_arc_set_range(batteryArc, 0, 100);
  lv_arc_set_value(batteryArc, 75);
  lv_obj_remove_style(batteryArc, nullptr, LV_PART_KNOB);
  lv_obj_clear_flag(batteryArc, LV_OBJ_FLAG_CLICKABLE);
  lv_obj_set_style_arc_width(batteryArc, 8, LV_PART_MAIN);
  lv_obj_set_style_arc_width(batteryArc, 8, LV_PART_INDICATOR);
  lv_obj_set_style_arc_color(batteryArc, rgb(0x141E33), LV_PART_MAIN);
  lv_obj_set_style_arc_color(batteryArc, rgb(0x66D9A0), LV_PART_INDICATOR);

  pinBox = lv_obj_create(screen);
  lv_obj_set_size(pinBox, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
  lv_obj_set_style_bg_opa(pinBox, LV_OPA_TRANSP, 0);
  lv_obj_set_style_border_width(pinBox, 0, 0);
  lv_obj_set_style_pad_all(pinBox, 0, 0);
  lv_obj_clear_flag(pinBox, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_align(pinBox, LV_ALIGN_TOP_MID, 0, 18);

  batteryLabel = lv_label_create(pinBox);
  lv_label_set_text(batteryLabel, "68%");
  lv_obj_set_style_text_font(batteryLabel, FONT_NORMAL, 0);
  lv_obj_set_style_text_color(batteryLabel, rgb(0x66D9A0), 0);
  lv_obj_align(batteryLabel, LV_ALIGN_LEFT_MID, 0, 0);

  batteryIconLabel = lv_label_create(pinBox);
  lv_label_set_text(batteryIconLabel, LV_SYMBOL_BATTERY_3);
  lv_obj_set_style_text_font(batteryIconLabel, FONT_NORMAL, 0);
  lv_obj_set_style_text_color(batteryIconLabel, rgb(0x66D9A0), 0);
  lv_obj_align_to(batteryIconLabel, batteryLabel, LV_ALIGN_OUT_RIGHT_MID, 4, 0);

  timeLabel = createLabel(screen, "10:09", FONT_TIME_BIG, rgb(0xF5F8FA));
  lv_obj_align(timeLabel, LV_ALIGN_TOP_MID, 0, 44);

  dateLabel = createLabel(screen, "Mon, 23 Oct 2026", FONT_TIME_SMALL, rgb(0x91A5C2));
  lv_obj_align(dateLabel, LV_ALIGN_TOP_MID, 0, 76);

  heartCard = lv_obj_create(screen);
  setObjectNoScroll(heartCard);
  lv_obj_set_size(heartCard, 160, 60);
  lv_obj_align(heartCard, LV_ALIGN_TOP_MID, 0, 115);
  lv_obj_set_style_radius(heartCard, 12, 0);
  lv_obj_set_style_bg_color(heartCard, rgb(0x101826), 0);
  lv_obj_set_style_border_width(heartCard, 1, 0);
  lv_obj_set_style_border_color(heartCard, rgb(0x1F2A41), 0);
  lv_obj_set_style_pad_all(heartCard, 2, 0);
  lv_obj_set_style_pad_column(heartCard, 10, 0);
  lv_obj_set_flex_flow(heartCard, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(heartCard, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER);

  heartIcon = lv_label_create(heartCard);
  lv_label_set_text(heartIcon, "H");
  lv_obj_set_style_text_color(heartIcon, rgb(0xFF4D73), 0);
  lv_obj_set_style_text_font(heartIcon, FONT_HEART_RATE, 0);
  lv_obj_set_style_pad_right(heartIcon, -8, 0);
  lv_obj_set_style_pad_top(heartIcon, 9, 0);

  lv_obj_t *heartValCont = lv_obj_create(heartCard);
  lv_obj_set_size(heartValCont, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
  lv_obj_set_style_bg_opa(heartValCont, LV_OPA_TRANSP, 0);
  lv_obj_set_style_border_width(heartValCont, 0, 0);
  lv_obj_set_flex_flow(heartValCont, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(heartValCont, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START);
  heartRateLabel = createLabel(heartValCont, "--", &lv_font_montserrat_24, rgb(0xFFFFFF));
  heartBpmLabel = createLabel(heartValCont, "bpm", &lv_font_montserrat_16, rgb(0xD0D8E3));
  lv_obj_set_style_pad_left(heartBpmLabel, 6, 0);

  statusCard = lv_obj_create(screen);
  setObjectNoScroll(statusCard);
  lv_obj_set_size(statusCard, 130, 28);
  lv_obj_align(statusCard, LV_ALIGN_TOP_MID, 0, 182);
  lv_obj_set_style_radius(statusCard, 12, 0);
  lv_obj_set_style_bg_color(statusCard, rgb(0x101826), 0);
  lv_obj_set_style_border_width(statusCard, 1, 0);
  lv_obj_set_style_border_color(statusCard, rgb(0x1F2A41), 0);
  lv_obj_set_style_pad_all(statusCard, 0, 0);
  lv_obj_set_style_pad_column(statusCard, 6, 0);
  lv_obj_set_flex_flow(statusCard, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(statusCard, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER);

  statusIcon = lv_label_create(statusCard);
  lv_label_set_text(statusIcon, LV_SYMBOL_OK);
  lv_obj_set_style_text_color(statusIcon, rgb(0x36D399), 0);
  lv_obj_set_style_text_font(statusIcon, &lv_font_montserrat_14, 0);
  statusLabel = createLabel(statusCard, "Normal", &lv_font_montserrat_14, rgb(0xFFFFFF));

  createSosOverlay();
}

static void updateStatusUi() {
  if (sosActive) {
    lv_label_set_text(statusLabel, "FALL");
    lv_label_set_text(statusIcon, LV_SYMBOL_WARNING);
    lv_obj_set_style_text_color(statusLabel, rgb(0xFF0000), 0);
    lv_obj_set_style_text_color(statusIcon, rgb(0xFF0000), 0);
  } else {
    lv_label_set_text(statusLabel, "Normal");
    lv_label_set_text(statusIcon, LV_SYMBOL_OK);
    lv_obj_set_style_text_color(statusLabel, rgb(0xFFFFFF), 0);
    lv_obj_set_style_text_color(statusIcon, rgb(0x36D399), 0);
  }
}

// ------------------------------ Battery logic (đã hiệu chỉnh) ------------------------------
#define BATTERY_CALIBRATION 1.12f   // pin đầy hiển thị 100%

static float readBatteryVoltage() {
  constexpr int sampleCount = 24;
  uint32_t sum = 0;
  for (int i = 0; i < sampleCount; ++i) {
    sum += analogRead(PIN_BATTERY);
    delayMicroseconds(250);
  }
  const float raw = static_cast<float>(sum) / sampleCount;
  return raw * (3.3f / 4095.0f) * 3.0f * BATTERY_CALIBRATION;
}

static int batteryPercentFromVoltage(float voltage) {
  struct Point { float voltage; int percent; };
  static constexpr Point curve[] = {
    {4.20f, 100}, {4.10f, 90}, {4.00f, 80}, {3.90f, 65}, {3.80f, 45}, {3.70f, 25}, {3.60f, 12}, {3.50f, 5}, {3.30f, 0}
  };
  if (voltage >= curve[0].voltage) return 100;
  const size_t count = sizeof(curve) / sizeof(curve[0]);
  if (voltage <= curve[count - 1].voltage) return 0;
  for (size_t i = 0; i < count - 1; ++i) {
    const Point high = curve[i], low = curve[i + 1];
    if (voltage <= high.voltage && voltage >= low.voltage) {
      const float ratio = (voltage - low.voltage) / (high.voltage - low.voltage);
      return static_cast<int>(roundf(low.percent + ratio * (high.percent - low.percent)));
    }
  }
  return 0;
}

static void updateBatteryUi() {
  static bool initialized = false;
  static float filteredVoltage = 3.9f;
  static bool isCharging = false;
  static float lastRawVoltage = 0.0f;
  const float raw = readBatteryVoltage();
  if (raw > 4.15f && raw > lastRawVoltage + 0.02f) isCharging = true;
  else if (raw < 4.05f || raw < lastRawVoltage) isCharging = false;
  lastRawVoltage = raw;
  if (!isCharging) {
    if (!initialized) { filteredVoltage = raw; initialized = true; }
    else filteredVoltage = 0.85f * filteredVoltage + 0.15f * raw;
  }
  const int percent = batteryPercentFromVoltage(filteredVoltage);
  currentBatteryPercent = percent;   // lưu lại để gửi khi có alert
  lv_arc_set_value(batteryArc, percent);
  lv_label_set_text_fmt(batteryLabel, "%d%%", percent);
  if (isCharging) lv_label_set_text(batteryIconLabel, LV_SYMBOL_CHARGE);
  else if (percent > 60) lv_label_set_text(batteryIconLabel, LV_SYMBOL_BATTERY_3);
  else if (percent > 30) lv_label_set_text(batteryIconLabel, LV_SYMBOL_BATTERY_2);
  else if (percent > 10) lv_label_set_text(batteryIconLabel, LV_SYMBOL_BATTERY_1);
  else lv_label_set_text(batteryIconLabel, LV_SYMBOL_BATTERY_EMPTY);
  lv_color_t color = rgb(0x66D9A0);
  if (percent <= 15) color = rgb(0xFF4D5E);
  else if (percent <= 35) color = rgb(0xFFB84D);
  lv_obj_set_style_arc_color(batteryArc, color, LV_PART_INDICATOR);
  lv_obj_set_style_text_color(batteryLabel, color, 0);
}

// ------------------------------ Clock (ĐÃ SỬA) ------------------------------
static time_t compileTimestampUTC = 0;   // UTC timestamp lúc biên dịch
static bool ntpAvailable = false;

// ================== HÀM TÍNH EPOCH THỦ CÔNG ==================
static time_t dateTimeToEpoch(int year, int month, int day, int hour, int minute, int second) {
  if (month <= 2) { month += 12; year -= 1; }
  int a = year / 100;
  int b = 2 - a + a / 4;
  long julianDay = (long)(365.25 * (year + 4716)) + (int)(30.6001 * (month + 1)) + day + b - 1524;
  long daysSinceEpoch = julianDay - 2440588L;
  time_t totalSeconds = daysSinceEpoch * 86400L + hour * 3600L + minute * 60L + second;
  return totalSeconds;
}

static void parseCompileTime() {
  const char *date = __DATE__;
  const char *months[] = {"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"};
  int month = 0, day = 0, year = 0;
  char monthStr[4];
  sscanf(date, "%3s %d %d", monthStr, &day, &year);
  for (int i = 0; i < 12; i++) {
    if (strcmp(monthStr, months[i]) == 0) { month = i + 1; break; }
  }

  int hour = 0, minute = 0, second = 0;
  sscanf(__TIME__, "%d:%d:%d", &hour, &minute, &second);

  // __TIME__ là giờ địa phương (UTC+7), ta tính epoch UTC và trừ offset
  long localEpoch = dateTimeToEpoch(year, month, day, hour, minute, second);
  compileTimestampUTC = localEpoch - GMT_OFFSET_SECONDS;
}

static void updateClockUi() {
  time_t localTime;
  if (ntpAvailable) {
    time_t nowUTC = timeClient.getEpochTime();     // giây UTC
    localTime = nowUTC + GMT_OFFSET_SECONDS;       // giờ địa phương (UTC+7)
  } else {
    // fallback: compileTimestampUTC (UTC) + millis() + offset
    localTime = compileTimestampUTC + (millis() / 1000) + GMT_OFFSET_SECONDS;
  }

  struct tm now_tm;
  gmtime_r(&localTime, &now_tm);

  char bufferTime[8], bufferDate[32];
  strftime(bufferTime, sizeof(bufferTime), "%H:%M", &now_tm);
  const char* days[] = {"Sun","Mon","Tue","Wed","Thu","Fri","Sat"};
  const char* months[] = {"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"};
  snprintf(bufferDate, sizeof(bufferDate), "%s, %02d %s %d",
           days[now_tm.tm_wday], now_tm.tm_mday, months[now_tm.tm_mon], now_tm.tm_year+1900);
  lv_label_set_text(timeLabel, bufferTime);
  lv_label_set_text(dateLabel, bufferDate);
}

// ---------------------------- Heart-rate ----------------------------
static void updateHeartRateUi() {
  float bpm = get_bpm();
  bool finger = is_finger_detected();
  if (!finger) {
    lv_label_set_text(heartRateLabel, "--");
    lv_obj_set_style_text_color(heartIcon, rgb(0x666666), 0);
    lv_obj_set_style_text_color(heartRateLabel, rgb(0x666666), 0);
    lv_obj_set_style_text_color(heartBpmLabel, rgb(0x666666), 0);
  } else if (bpm < 1) {
    lv_label_set_text(heartRateLabel, "--");
    lv_obj_set_style_text_color(heartIcon, rgb(0xFFB84D), 0);
    lv_obj_set_style_text_color(heartRateLabel, rgb(0xFFB84D), 0);
    lv_obj_set_style_text_color(heartBpmLabel, rgb(0xFFB84D), 0);
  } else {
    lv_label_set_text_fmt(heartRateLabel, "%d", (int)bpm);
    lv_obj_set_style_text_color(heartIcon, rgb(0xFF4D73), 0);
    lv_obj_set_style_text_color(heartRateLabel, rgb(0xFFFFFF), 0);
    lv_obj_set_style_text_color(heartBpmLabel, rgb(0xD0D8E3), 0);
  }
}

// ================== HÀM GỬI ALERT LÊN SERVER ==================
static String getCurrentTimeISO8601() {
  time_t nowUTC;
  if (ntpAvailable) {
    nowUTC = timeClient.getEpochTime();
  } else {
    nowUTC = compileTimestampUTC + (millis() / 1000);
  }
  struct tm t;
  gmtime_r(&nowUTC, &t);
  char buf[25];
  snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02dZ",
           t.tm_year + 1900, t.tm_mon + 1, t.tm_mday,
           t.tm_hour, t.tm_min, t.tm_sec);
  return String(buf);
}

static void sendAlertToServer(float confidence) {
  if (backendUrl.length() == 0) {
    Serial.println("No backend configured, cannot send alert.");
    return;
  }

  HTTPClient http;
  String url = backendUrl + "/alert";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Id", "SW-0005");

  float ax, ay, az, gx, gy, gz;
  get_filtered_data(ax, ay, az, gx, gy, gz);
  float bpm = get_bpm();
  if (!is_finger_detected()) bpm = -1;

  StaticJsonDocument<256> doc;
  doc["timestamp"] = getCurrentTimeISO8601();
  doc["type"] = "fall";
  doc["confidence"] = confidence;
if (is_finger_detected()) {
    doc["heart_rate"] = (int)bpm;           // ép về số nguyên
} else {
    doc["heart_rate"] = nullptr;            // gửi null (JSON null)
}
  doc["battery"] = currentBatteryPercent;
  doc["rssi"] = currentWiFiRSSI;
  JsonObject accel = doc.createNestedObject("accel");
  accel["ax"] = ax;
  accel["ay"] = ay;
  accel["az"] = az;
  JsonObject gyro = doc.createNestedObject("gyro");
  gyro["gx"] = gx;
  gyro["gy"] = gy;
  gyro["gz"] = gz;

  String jsonStr;
  serializeJson(doc, jsonStr);

  Serial.println("Sending alert: " + jsonStr);
  int httpCode = http.POST(jsonStr);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("Alert sent, HTTP code: %d, response: %s\n", httpCode, response.c_str());
  } else {
    Serial.printf("Alert send failed, error: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

// ================== AI FALL DETECTION ==================
static bool init_fall_model() {
  model = tflite::GetModel(g_fall_model_data);
  if (model->version() != TFLITE_SCHEMA_VERSION) {
    Serial.println("Model version mismatch!");
    return false;
  }
  static tflite::MicroInterpreter static_interpreter(model, resolver, tensor_arena, kTensorArenaSize, &micro_error_reporter);
  interpreter = &static_interpreter;
  if (interpreter->AllocateTensors() != kTfLiteOk) {
    Serial.println("AllocateTensors failed!");
    return false;
  }
  input_tensor = interpreter->input(0);
  output_tensor = interpreter->output(0);
  Serial.printf("Model input: dims=%d, type=%d, bytes=%d\n", input_tensor->dims->size, input_tensor->type, input_tensor->bytes);
  for (int i=0; i<input_tensor->dims->size; i++) Serial.printf("  dim[%d] = %d\n", i, input_tensor->dims->data[i]);
  Serial.printf("Model output: dims=%d, type=%d, bytes=%d\n", output_tensor->dims->size, output_tensor->type, output_tensor->bytes);
  Serial.println("Fall detection model loaded.");
  return true;
}

// Chuẩn hóa và quantize 1 feature
static inline int8_t quantizeFeature(float value, int idx) {
  float norm = (value - FEATURE_MEAN[idx]) / FEATURE_STD[idx];
  int32_t q = (int32_t)roundf(norm / input_tensor->params.scale) + input_tensor->params.zero_point;
  if (q > 127) q = 127;
  if (q < -128) q = -128;
  return (int8_t)q;
}

static float run_fall_inference(float* input_data, int input_len) {
  if (!interpreter) return -1.0f;
  if (input_tensor->type == kTfLiteInt8) {
    float scale = input_tensor->params.scale;
    int zero_point = input_tensor->params.zero_point;
    int8_t* dst = input_tensor->data.int8;
    for (int i=0; i<input_tensor->bytes && i<input_len; i++) {
      int32_t q = round(input_data[i] / scale) + zero_point;
      if (q > 127) q = 127; if (q < -128) q = -128;
      dst[i] = (int8_t)q;
    }
  } else {
    memcpy(input_tensor->data.f, input_data, input_tensor->bytes);
  }
  if (interpreter->Invoke() != kTfLiteOk) {
    Serial.println("Invoke failed!");
    return -1.0f;
  }
  float fall_score = 0.0f;
  if (output_tensor->type == kTfLiteInt8) {
    float scale = output_tensor->params.scale;
    int zero_point = output_tensor->params.zero_point;
    if (output_tensor->bytes == 1) {
      fall_score = (output_tensor->data.int8[0] - zero_point) * scale;
    } else if (output_tensor->bytes == 2) {
      float v0 = (output_tensor->data.int8[0] - zero_point) * scale;
      float v1 = (output_tensor->data.int8[1] - zero_point) * scale;
      fall_score = v1;
    }
  } else {
    int out_size = output_tensor->bytes / sizeof(float);
    if (out_size >= 2) fall_score = output_tensor->data.f[1];
    else fall_score = output_tensor->data.f[0];
  }
  Serial.printf("Fall score: %.3f\n", fall_score);
  return fall_score;
}

// Tính 4 feature cho 1 mẫu accelerometer (đơn vị g)
static void computeFeatures(float ax_g, float ay_g, float az_g,
                            float prev_ax, float prev_ay, float prev_az,
                            float prev_mag, bool first_sample,
                            float &mag, float &dev, float &delta, float &ang) {
  mag = sqrtf(ax_g*ax_g + ay_g*ay_g + az_g*az_g);
  dev = fabsf(mag - 1.0f);
  if (first_sample) {
    delta = 0.0f;
    ang = 0.0f;
  } else {
    delta = mag - prev_mag;
    float prev_mag_sq = prev_mag * mag;
    if (prev_mag_sq < 1e-6f) prev_mag_sq = 1e-6f;
    float dot = prev_ax*ax_g + prev_ay*ay_g + prev_az*az_g;
    float cosv = dot / prev_mag_sq;
    if (cosv > 1.0f) cosv = 1.0f;
    if (cosv < -1.0f) cosv = -1.0f;
    ang = acosf(cosv);
  }
}

static void handleFallDetection() {
  unsigned long now = millis();

  // SOS countdown
  if (sosActive) {
    if (now - sosCountdownTimer >= 1000) {
      sosCountdownTimer = now;
      sosCountdown--;
      if (sosCountdown >= 0) lv_label_set_text_fmt(countdownLabel, "%d", sosCountdown);
      if (sosCountdown <= 0) {
        Serial.println("SOS countdown finished, sending emergency alert.");
        sendAlertToServer(lastFallScore);
        dismissSOS();
      }
    }
  }

  // Lấy mẫu mỗi 200 ms
  if (now - lastFallSampleTime >= FALL_SAMPLE_INTERVAL_MS) {
    lastFallSampleTime = now;

    // Đọc accelerometer (đơn vị g)
    float ax, ay, az, gx, gy, gz;
    get_filtered_data(ax, ay, az, gx, gy, gz);  // ax, ay, az đang là m/s² (theo hàm gốc)
    // Chuyển m/s² → g
    ax /= 9.80665f;
    ay /= 9.80665f;
    az /= 9.80665f;

    // Ghi vào buffer vòng
    accelWindow[windowSampleIndex][0] = ax;
    accelWindow[windowSampleIndex][1] = ay;
    accelWindow[windowSampleIndex][2] = az;
    windowSampleIndex = (windowSampleIndex + 1) % FALL_WINDOW_SAMPLES;

    // Khi đã đủ 20 mẫu
    if (windowSampleIndex == 0 && !sosActive && !fallCooldown) {
      // Chuẩn bị mảng features (80 float)
      float features[FALL_MODEL_INPUT_LEN];
      float prev_ax = accelWindow[0][0];
      float prev_ay = accelWindow[0][1];
      float prev_az = accelWindow[0][2];
      float prev_mag = sqrtf(prev_ax*prev_ax + prev_ay*prev_ay + prev_az*prev_az);
      int featIdx = 0;

      for (int i = 0; i < FALL_WINDOW_SAMPLES; i++) {
        float ax_s = accelWindow[i][0];
        float ay_s = accelWindow[i][1];
        float az_s = accelWindow[i][2];
        float mag, dev, delta, ang;
        computeFeatures(ax_s, ay_s, az_s, prev_ax, prev_ay, prev_az, prev_mag, i==0,
                        mag, dev, delta, ang);
        features[featIdx++] = mag;
        features[featIdx++] = dev;
        features[featIdx++] = delta;
        features[featIdx++] = ang;

        prev_ax = ax_s; prev_ay = ay_s; prev_az = az_s; prev_mag = mag;
      }

      // Quantize toàn bộ features và chạy inference
      if (input_tensor->type == kTfLiteInt8) {
        int8_t* dst = input_tensor->data.int8;
        for (int i = 0; i < FALL_MODEL_INPUT_LEN; i++) {
          dst[i] = quantizeFeature(features[i], i % NUM_FEATURES);
        }
      } else {
        memcpy(input_tensor->data.f, features, sizeof(features));
      }

      if (interpreter->Invoke() == kTfLiteOk) {
        float fall_score;
        if (output_tensor->type == kTfLiteInt8) {
          float scale = output_tensor->params.scale;
          int zero_point = output_tensor->params.zero_point;
          if (output_tensor->bytes == 2) {
            float v1 = (output_tensor->data.int8[1] - zero_point) * scale;
            fall_score = v1;
          } else {
            fall_score = (output_tensor->data.int8[0] - zero_point) * scale;
          }
        } else {
          int out_size = output_tensor->bytes / sizeof(float);
          fall_score = (out_size >= 2) ? output_tensor->data.f[1] : output_tensor->data.f[0];
        }
        Serial.printf("Fall score: %.3f\n", fall_score);
        if (fall_score > FALL_THRESHOLD) {
          fallDetected = true;
          sosActive = true;
          lastFallScore = fall_score;
          showSosScreen();
          Serial.println("!!! FALL DETECTED - SOS TRIGGERED");
        }
      } else {
        Serial.println("Invoke failed!");
      }
    }
  }

  if (fallCooldown && (now - sosDismissTime > FALL_COOLDOWN_MS))
    fallCooldown = false;
}

// ------------------- WiFi & Backend Config --------------------
void saveBackendConfig(const String &host, int port) {
  preferences.begin("backend", false);
  preferences.putString("host", host); preferences.putInt("port", port);
  preferences.end();
  apiHost = host; apiPort = port;
  backendUrl = "http://" + host + ":" + String(port);
}
void loadBackendConfig() {
  preferences.begin("backend", true);
  apiHost = preferences.getString("host", "");
  apiPort = preferences.getInt("port", 5000);
  preferences.end();
  if (apiHost.length() > 0) {
    backendUrl = "http://" + apiHost + ":" + String(apiPort);
    Serial.println("Loaded backend: " + backendUrl);
  }
}
const char* configHtml PROGMEM = R"rawliteral(<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Backend Config</title><style>body{background:#0A0D15;color:#e0e8f0;margin:0;padding:20px;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif}.container{background:#101826;padding:30px;border-radius:24px;max-width:400px;margin:auto;border:1px solid #1F2A41}h2{text-align:center;color:#66D9A0}label{display:block;margin:10px 0 4px;color:#8A9BB0}input{width:100%;padding:12px;border-radius:12px;border:none;background:#1A243A;color:#fff;font-size:16px;box-sizing:border-box}button{width:100%;padding:14px;margin-top:20px;border:none;border-radius:30px;background:#66D9A0;color:#0A0D15;font-size:18px;font-weight:bold;cursor:pointer}</style></head><body><div class="container"><h2>⚙️ BACKEND CONFIG</h2><form action="/saveconfig" method="POST"><label>Server IP Address (e.g. 192.168.1.10)</label><input type="text" name="host" required placeholder="192.168.1.10"><label>Port (default 5000)</label><input type="number" name="port" value="5000"><button type="submit">💾 SAVE</button></form><div style="text-align:center;margin-top:12px;color:#6d85a5;font-size:14px">After saving, ESP32 will restart</div></div></body></html>)rawliteral";
const char* htmlForm PROGMEM = R"rawliteral(<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Watch Config</title><style>body{background:#0A0D15;color:#e0e8f0;margin:0;padding:20px;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif}.container{background:#101826;padding:30px;border-radius:24px;width:100%;max-width:380px;border:1px solid #1F2A41}h2{text-align:center;color:#66D9A0;font-size:26px;margin-top:0}label{display:block;margin:14px 0 6px;font-size:16px;color:#8A9BB0}input{width:100%;padding:16px;border-radius:16px;border:none;background:#1A243A;color:#fff;font-size:18px;box-sizing:border-box;outline:2px solid transparent}input:focus{outline:2px solid #66D9A0}button{width:100%;padding:18px;margin-top:20px;border:none;border-radius:40px;background:#66D9A0;color:#0A0D15;font-size:20px;font-weight:bold;cursor:pointer}</style></head><body><div class="container"><h2>⚙️ WIFI CONFIG</h2><form action="/save" method="POST"><label>WiFi Name (SSID)</label><input type="text" name="ssid" required><label>Password</label><input type="password" name="pass" required><button type="submit">💾 SAVE & RESTART</button></form><div style="text-align:center;margin-top:12px;color:#6d85a5;font-size:14px">Device will restart after saving</div></div></body></html>)rawliteral";

void handleRoot() { server.send(200, "text/html", String(htmlForm)); }
void handleSave() {
  if (server.method() == HTTP_POST) {
    String ssid = server.arg("ssid"); String pass = server.arg("pass");
    saveWiFiCredentials(ssid, pass);
    server.send(200, "text/html", "✅ Saved! Restarting..."); delay(2000); ESP.restart();
  }
}
void handleConfig() { server.send(200, "text/html", String(configHtml)); }
void handleSaveConfig() {
  if (server.method() == HTTP_POST) {
    String host = server.arg("host"); int port = server.arg("port").toInt();
    if (port <= 0) port = 5000;
    saveBackendConfig(host, port);
    server.send(200, "text/html", "✅ Saved! Restarting..."); delay(2000); ESP.restart();
  }
}
void saveWiFiCredentials(const String &ssid, const String &pass) {
  preferences.begin("wifi", false);
  preferences.putString("ssid", ssid); preferences.putString("pass", pass);
  preferences.end();
}
bool loadWiFiCredentials(String &ssid, String &pass) {
  preferences.begin("wifi", true);
  ssid = preferences.getString("ssid", ""); pass = preferences.getString("pass", "");
  preferences.end();
  return (ssid.length() > 0);
}
bool connectToWiFi() {
  String ssid, pass;
  if (!loadWiFiCredentials(ssid, pass)) return false;
  WiFi.mode(WIFI_STA); WiFi.begin(ssid.c_str(), pass.c_str());
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) delay(200);
  return WiFi.status() == WL_CONNECTED;
}
void setupWebServer() {
  server.on("/", handleRoot);
  server.on("/save", handleSave);
  server.on("/config", handleConfig);
  server.on("/saveconfig", handleSaveConfig);
  server.begin();
}

// ================== SETUP ==================
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_BATTERY, ADC_11db);

  Wire.begin(6, 7); delay(100);
  Wire.beginTransmission(0x15); Wire.write(0xEC); Wire.write(0x00); Wire.endTransmission();
  delay(50);
  Wire.beginTransmission(0x15); Wire.write(0xED); Wire.write(0x00); Wire.endTransmission();
  delay(50);

  lv_init();
  pinMode(PIN_BACKLIGHT, OUTPUT); digitalWrite(PIN_BACKLIGHT, HIGH);
  tft.begin(); tft.setRotation(0);
  touch.begin();

  imu_init();
  init_max30102();

  if (!init_fall_model()) {
    Serial.println("Failed to init fall model! Halted.");
    while (1) delay(1000);
  }

  size_t bufSize = SCREEN_WIDTH * LVGL_BUF_ROWS * sizeof(lv_color_t);
  if (psramFound()) {
    lvBuffer = (lv_color_t *)heap_caps_malloc(bufSize, MALLOC_CAP_SPIRAM);
    Serial.println("Using PSRAM for LVGL buffer");
  }
  if (!lvBuffer) {
    lvBuffer = (lv_color_t *)malloc(bufSize);
    Serial.println("Using internal RAM for LVGL buffer");
  }
  lv_disp_draw_buf_init(&drawBuffer, lvBuffer, NULL, SCREEN_WIDTH * LVGL_BUF_ROWS);

  static lv_disp_drv_t disp_drv; lv_disp_drv_init(&disp_drv);
  disp_drv.hor_res = SCREEN_WIDTH; disp_drv.ver_res = SCREEN_HEIGHT;
  disp_drv.flush_cb = displayFlush; disp_drv.draw_buf = &drawBuffer;
  lv_disp_drv_register(&disp_drv);

  static lv_indev_drv_t indev_drv; lv_indev_drv_init(&indev_drv);
  indev_drv.type = LV_INDEV_TYPE_POINTER;
  indev_drv.read_cb = my_touchpad_read;
  lv_indev_drv_register(&indev_drv);

  parseCompileTime();  // lấy thời gian biên dịch (UTC)

  loadBackendConfig();
  if (connectToWiFi()) {
    Serial.println("Watch mode - WiFi connected.");
    timeClient.begin();
    if (timeClient.update()) {
      ntpAvailable = true;
      Serial.println("NTP time synchronized.");
    }
  } else {
    WiFi.mode(WIFI_AP); WiFi.softAP("ESP32-Watch");
    Serial.println("AP Mode started. Using local time.");
    ntpAvailable = false;
  }
  setupWebServer();

  createWatchUi();
  updateBatteryUi();
  updateClockUi();
  updateHeartRateUi();
  updateStatusUi();
}

void loop() {
  static uint32_t lastLvglTickMs = millis();
  static uint32_t lastImuMs = 0, lastUiMs = 0, lastClockMs = 0, lastBatteryMs = 0;
  uint32_t now = millis();

  server.handleClient();
  if (ntpAvailable) timeClient.update(); // chỉ cập nhật NTP khi có WiFi

  uint32_t elapsed = now - lastLvglTickMs;
  if (elapsed > 0) { lv_tick_inc(elapsed); lastLvglTickMs = now; }

  if (now - lastImuMs >= 20) { lastImuMs = now; imu_update(); }

  handleFallDetection();
  update_max30102();

  if (now - lastUiMs >= 250) {
    lastUiMs = now;
    updateHeartRateUi();
    updateStatusUi();
  }

  if (now - lastClockMs >= 1000) { lastClockMs = now; updateClockUi(); }
  if (now - lastBatteryMs >= 3000) { lastBatteryMs = now; updateBatteryUi(); }

  lv_timer_handler();
  // Cập nhật RSSI mỗi 5 giây
static unsigned long lastRSSIUpdate = 0;
if (ntpAvailable && now - lastRSSIUpdate > 5000) {
  lastRSSIUpdate = now;
  currentWiFiRSSI = WiFi.RSSI();
}
currentWiFiRSSI = ntpAvailable ? WiFi.RSSI() : -100;
  delay(5);
}