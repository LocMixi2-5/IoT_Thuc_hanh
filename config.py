"""
Configuration Module for IoT Lab 2
BÀI THỰC HÀNH SỐ 2: THU THẬP, LƯU TRỮ VÀ TIỀN XỬ LÝ DỮ LIỆU IoT
Học phần: IoT và Ứng dụng (INT14149)
Sinh viên: Nguyễn Xuân Lộc - B23DCCN492
"""

import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# ==========================================
# 1. MQTT Configuration
# ==========================================
# Sử dụng public broker ổn định cho cả Wokwi và máy tính
# Có thể đổi sang 'localhost' nếu dùng Mosquitto cục bộ
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_KEEPALIVE = 60

# Topic chuẩn phân cấp IoT: iot/{student_id}/{device_id}/{data_type}
STUDENT_ID = "B23DCCN492"
DEVICE_ID = "ESP32_B23DCCN492"
MQTT_TOPIC_TELEMETRY = f"iot/{STUDENT_ID}/esp32/telemetry"
MQTT_TOPIC_COMMANDS = f"iot/{STUDENT_ID}/esp32/commands"

# Client IDs
MQTT_COLLECTOR_CLIENT_ID = f"Collector_{STUDENT_ID}"
MQTT_SIMULATOR_CLIENT_ID = f"Simulator_{STUDENT_ID}"

# ==========================================
# 2. Database Configuration
# ==========================================
# SQLite Time-Series Database (Lưu cục bộ nhẹ, cực kỳ ổn định, không lo lỗi kết nối)
SQLITE_DB_PATH = BASE_DIR / "iot_timeseries.db"

# InfluxDB 2.x Configuration (Hỗ trợ khi bật Docker hoặc InfluxDB server)
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "iot-lab2-token-b23dccn492-super-secret-key")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "ptit")
INFLUXDB_BUCKET_RAW = os.getenv("INFLUXDB_BUCKET_RAW", "sensor_telemetry_raw")
INFLUXDB_BUCKET_PROCESSED = os.getenv("INFLUXDB_BUCKET_PROCESSED", "sensor_telemetry_processed")

# Tự động lưu song song cả SQLite để đảm bảo dữ liệu luôn sẵn sàng
ENABLE_SQLITE_STORAGE = True
ENABLE_INFLUXDB_STORAGE = True

# Retention Policy (Thời gian lưu trữ dữ liệu thô)
RAW_DATA_RETENTION_DAYS = 7
PROCESSED_DATA_RETENTION_DAYS = 30

# ==========================================
# 3. Data Validation Thresholds (Sanity Checks)
# ==========================================
VALIDATION_RULES = {
    "temperature": {"min": -40.0, "max": 80.0, "unit": "°C"},     # Giới hạn cảm biến DHT22
    "humidity": {"min": 0.0, "max": 100.0, "unit": "%"},           # Giới hạn độ ẩm không khí
    "distance_cm": {"min": 2.0, "max": 400.0, "unit": "cm"},       # Giới hạn cảm biến HC-SR04
    "rssi": {"min": -100, "max": 0, "unit": "dBm"}                 # Tín hiệu WiFi ESP32
}

# ==========================================
# 4. Preprocessing Parameters
# ==========================================
# Ngưỡng phát hiện bất thường (Outliers)
OUTLIER_IQR_FACTOR = 1.5      # Q1 - 1.5*IQR đến Q3 + 1.5*IQR
OUTLIER_ZSCORE_THRESHOLD = 3.0 # Độ lệch chuẩn |Z| > 3.0

# Resampling time windows
DEFAULT_RESAMPLE_INTERVAL = "30s" # 30 giây hoặc 1 phút
FEATURE_ROLLING_WINDOW = 5        # Kích thước cửa sổ trượt (5 mẫu)
