"""
ESP32 Telemetry Simulator
Giả lập luồng dữ liệu cảm biến từ thiết bị nhúng ESP32 gửi lên MQTT Broker.
Cho phép tạo dữ liệu thực tế kèm theo các trường hợp ngoại lệ (outlier, missing, duplicate)
để kiểm thử toàn diện pipeline thu thập và tiền xử lý dữ liệu.

Sinh viên: Nguyễn Xuân Lộc - B23DCCN492
"""

import json
import time
import math
import random
import argparse
import logging
import sys
from pathlib import Path

# Ensure src/ is in sys.path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Ensure UTF-8 output on Windows terminals
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import paho.mqtt.client as mqtt

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIMULATOR] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Simulator")


class ESP32Simulator:
    def __init__(self, broker: str = config.MQTT_BROKER, port: int = config.MQTT_PORT, interval: float = 3.0):
        self.broker = broker
        self.port = port
        self.interval = interval
        self.topic = config.MQTT_TOPIC_TELEMETRY
        self.device_id = config.DEVICE_ID
        
        self.client = mqtt.Client(client_id=config.MQTT_SIMULATOR_CLIENT_ID)
        self.sequence = 0
        self.base_temp = 28.5
        self.base_humidity = 65.0
        self.base_distance = 50.0

    def connect(self):
        logger.info(f"Connecting to MQTT Broker: {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()
        time.sleep(1)
        logger.info(f"Connected! Publishing to topic: {self.topic}")

    def generate_packet(self, inject_anomaly: bool = False, inject_duplicate: bool = False):
        """Sinh một gói tin cảm biến chân thực"""
        self.sequence += 1
        uptime_s = int(time.time() - self.start_time)
        timestamp_ms = int(time.time() * 1000)

        # Mô phỏng quy luật tự nhiên (nhiệt độ dao động hình sin + nhiễu ngẫu nhiên)
        t = uptime_s / 60.0
        temp = self.base_temp + 3.0 * math.sin(t) + random.gauss(0, 0.4)
        hum = self.base_humidity - 4.0 * math.sin(t) + random.gauss(0, 0.8)
        dist = self.base_distance + 15.0 * math.cos(t * 1.5) + random.gauss(0, 1.2)
        rssi = random.randint(-75, -55)

        status = "OK"

        # Chèn bất thường (Outlier) để kiểm thử thuật toán IQR & Z-score
        if inject_anomaly:
            anomaly_type = random.choice(["temp_spike", "hum_spike", "dist_drop"])
            if anomaly_type == "temp_spike":
                temp = round(temp + random.uniform(25.0, 45.0), 2) # vọt lên 55-75°C
                status = "OUTLIER_TEMP_HIGH"
            elif anomaly_type == "hum_spike":
                hum = round(hum + random.uniform(40.0, 60.0), 2)   # vọt lên > 100%
                status = "OUTLIER_HUM_HIGH"
            else:
                dist = round(random.uniform(0.1, 1.5), 2)           # quá gần < 2cm
                status = "OUTLIER_DIST_LOW"
            logger.warning(f"-> [INJECTED ANOMALY] Type={anomaly_type} | Temp={temp}°C | Hum={hum}% | Dist={dist}cm")

        # Giới hạn làm tròn số thực 2 chữ số thập phân
        temp = round(temp, 2)
        hum = round(hum, 2)
        dist = round(max(0.5, dist), 2)

        packet = {
            "device_id": self.device_id,
            "timestamp": timestamp_ms,
            "sequence": self.sequence,
            "temperature": temp,
            "humidity": hum,
            "distance_cm": dist,
            "rssi": rssi,
            "uptime_s": uptime_s,
            "status": status
        }
        return packet

    def run(self, count: int = 0, anomaly_rate: float = 0.1, loss_rate: float = 0.05, dup_rate: float = 0.05):
        """
        Khởi chạy vòng lặp phát dữ liệu:
        - count: số gói tin cần phát (0 = vô hạn)
        - anomaly_rate: tỷ lệ phát sinh outlier
        - loss_rate: tỷ lệ giả lập mất gói tin
        - dup_rate: tỷ lệ giả lập trùng lặp gói tin
        """
        self.connect()
        self.start_time = time.time()
        logger.info(f"Simulator started (interval={self.interval}s, anomaly_rate={anomaly_rate*100}%)...")
        
        sent = 0
        try:
            while count == 0 or sent < count:
                time.sleep(self.interval)

                # 1. Giả lập Packet Loss (bỏ qua không gửi sequence này)
                if random.random() < loss_rate:
                    self.sequence += 1
                    logger.warning(f"-> [SIMULATING PACKET LOSS] Skipping Seq #{self.sequence}")
                    continue

                # 2. Sinh gói tin bình thường hoặc có bất thường
                has_anomaly = (random.random() < anomaly_rate)
                packet = self.generate_packet(inject_anomaly=has_anomaly)
                payload_str = json.dumps(packet)

                # Gửi gói tin
                self.client.publish(self.topic, payload_str, qos=1)
                sent += 1
                logger.info(f"[PUBLISHED #{packet['sequence']:03d}] T={packet['temperature']}°C | H={packet['humidity']}% | D={packet['distance_cm']}cm")

                # 3. Giả lập trùng lặp gói tin (Duplicate)
                if random.random() < dup_rate:
                    time.sleep(0.2)
                    logger.warning(f"-> [SIMULATING DUPLICATE] Re-sending Seq #{packet['sequence']}")
                    self.client.publish(self.topic, payload_str, qos=1)

        except KeyboardInterrupt:
            logger.info("Simulator stopped by user.")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ESP32 IoT Sensor Simulator")
    parser.add_argument("--count", type=int, default=0, help="Number of packets to send (0 = infinite)")
    parser.add_argument("--interval", type=float, default=3.0, help="Publish interval in seconds")
    parser.add_argument("--anomaly", type=float, default=0.10, help="Anomaly injection rate (0.0 - 1.0)")
    parser.add_argument("--loss", type=float, default=0.05, help="Packet loss injection rate (0.0 - 1.0)")
    parser.add_argument("--dup", type=float, default=0.05, help="Duplicate packet injection rate (0.0 - 1.0)")
    args = parser.parse_args()

    sim = ESP32Simulator(interval=args.interval)
    sim.run(count=args.count, anomaly_rate=args.anomaly, loss_rate=args.loss, dup_rate=args.dup)
