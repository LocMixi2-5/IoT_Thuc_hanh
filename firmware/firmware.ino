/*
 * BÀI THỰC HÀNH SỐ 2: THU THẬP, LƯU TRỮ VÀ TIỀN XỬ LÝ DỮ LIỆU IoT
 * Firmware ESP32 kết nối Cảm biến DHT22 & HC-SR04, gửi MQTT JSON
 * Sinh viên: Nguyễn Xuân Lộc
 * Mã sinh viên: B23DCCN492
 * Học phần: IoT và Ứng dụng (INT14149)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHTesp.h>
#include <time.h>

// ==========================================
// CẤU HÌNH HỆ THỐNG
// ==========================================
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

// MQTT Broker (EMQX Public Broker - tương thích Wokwi & ESP32 thực tế)
const char* MQTT_SERVER = "broker.emqx.io";
const int MQTT_PORT = 1883;

// Định danh sinh viên & Thiết bị
const char* STUDENT_ID = "B23DCCN492";
const char* DEVICE_ID = "ESP32_B23DCCN492";

// Cấu trúc Topic chuẩn theo đề bài: iot/{student_id}/esp32/telemetry
const char* MQTT_TOPIC_TELEMETRY = "iot/B23DCCN492/esp32/telemetry";

// Cấu hình chân phần cứng
const int DHT_PIN = 15;      // DHT22 Data pin
const int TRIG_PIN = 5;      // HC-SR04 Trigger pin
const int ECHO_PIN = 18;     // HC-SR04 Echo pin
const int LED_PIN = 2;       // LED báo trạng thái gửi

// Chu kỳ gửi dữ liệu (milliseconds)
const unsigned long SEND_INTERVAL_MS = 4000;

// Các đối tượng quản lý
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
DHTesp dht;

unsigned long lastSendTime = 0;
unsigned long sequenceNo = 0;
bool ntpConfigured = false;

// ==========================================
// HÀM ĐỒNG BỘ THỜI GIAN NTP
// ==========================================
void initTime() {
  configTime(7 * 3600, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("Dang dong bo thoi gian NTP");
  time_t now = time(nullptr);
  int retry = 0;
  while (now < 100000 && retry < 20) {
    delay(200);
    Serial.print(".");
    now = time(nullptr);
    retry++;
  }
  if (now > 100000) {
    Serial.println("\nDong bo NTP thanh cong!");
    ntpConfigured = true;
  } else {
    Serial.println("\nNTP chua dong bo kip, se su dung epoch uoc tinh.");
  }
}

uint64_t getEpochTimestampMs() {
  timeval tv;
  gettimeofday(&tv, NULL);
  if (tv.tv_sec > 100000) {
    return ((uint64_t)tv.tv_sec * 1000ULL) + (tv.tv_usec / 1000ULL);
  }
  return 1729238400000ULL + millis();
}

// ==========================================
// KẾT NỐI MẠNG WIFI & MQTT
// ==========================================
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Dang ket noi WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected! IP: " + WiFi.localIP().toString());
  initTime();
}

void connectMQTT() {
  while (!mqttClient.connected()) {
    String clientId = String(DEVICE_ID) + "_" + String((uint32_t)ESP.getEfuseMac(), HEX);
    Serial.print("Dang ket noi MQTT Broker: " + String(MQTT_SERVER) + "...");
    
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(" Thanh cong!");
      Serial.println("Topic Publish: " + String(MQTT_TOPIC_TELEMETRY));
    } else {
      Serial.printf(" That bai, rc=%d. Thu lai sau 2 giay...\n", mqttClient.state());
      delay(2000);
    }
  }
}

// ==========================================
// ĐỌC CẢM BIẾN
// ==========================================
float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000); // Timeout 30ms (~5m)
  if (duration == 0) return NAN;
  return duration * 0.0343f / 2.0f;
}

// ==========================================
// SETUP & LOOP
// ==========================================
void setup() {
  Serial.begin(115200);
  Serial.println("==================================================");
  Serial.println("   IOT LAB 2: ESP32 TELEMETRY PUBLISHER");
  Serial.println("   Sinh vien: Nguyen Xuan Loc - B23DCCN492");
  Serial.println("==================================================");

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  dht.setup(DHT_PIN, DHTesp::DHT22);

  connectWiFi();
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setBufferSize(512);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();

  unsigned long currentMillis = millis();
  if (currentMillis - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = currentMillis;

    TempAndHumidity dhtData = dht.getTempAndHumidity();
    float distance = readDistanceCm();

    if (!isfinite(dhtData.temperature) || !isfinite(dhtData.humidity) || !isfinite(distance)) {
      Serial.println("[Canh bao] Du lieu cam bien khong hop le (NAN), bo qua chu ky nay.");
      return;
    }

    sequenceNo++;
    uint64_t timestampMs = getEpochTimestampMs();

    char payload[350];
    snprintf(payload, sizeof(payload),
      "{\"device_id\":\"%s\",\"timestamp\":%llu,\"sequence\":%lu,"
      "\"temperature\":%.2f,\"humidity\":%.2f,\"distance_cm\":%.2f,"
      "\"rssi\":%d,\"uptime_s\":%lu,\"status\":\"OK\"}",
      DEVICE_ID, timestampMs, sequenceNo,
      dhtData.temperature, dhtData.humidity, distance,
      WiFi.RSSI(), currentMillis / 1000
    );

    bool published = mqttClient.publish(MQTT_TOPIC_TELEMETRY, payload);
    
    if (published) {
      Serial.printf("[PUBLISH OK] Seq: #%lu | T: %.1f C | H: %.1f %% | D: %.1f cm\n",
                    sequenceNo, dhtData.temperature, dhtData.humidity, distance);
      digitalWrite(LED_PIN, HIGH);
      delay(70);
      digitalWrite(LED_PIN, LOW);
    } else {
      Serial.printf("[PUBLISH FAILED] Seq: #%lu\n", sequenceNo);
    }
  }
}
