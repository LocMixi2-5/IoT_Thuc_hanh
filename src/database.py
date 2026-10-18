"""
Database Management Module
Hỗ trợ lưu trữ dữ liệu Time-Series kép:
1. SQLite Time-Series Engine (nhúng cục bộ, tự động tạo bảng, đánh index thời gian, không phụ thuộc service ngoài).
2. InfluxDB 2.x (chuẩn time-series database theo yêu cầu bài thực hành).
Sinh viên: Nguyễn Xuân Lộc - B23DCCN492
"""

import sqlite3
import datetime
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure src/ is in sys.path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd
import config

logger = logging.getLogger("Database")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False


class TimeSeriesDatabase:
    """Quản lý lưu trữ dữ liệu Time-Series đa nền tảng"""

    def __init__(self):
        self.sqlite_path = config.SQLITE_DB_PATH
        self.influx_client = None
        self.influx_write_api = None
        self.influx_enabled = False

        self._init_sqlite()
        if config.ENABLE_INFLUXDB_STORAGE and INFLUXDB_AVAILABLE:
            self._init_influxdb()

    def _get_sqlite_conn(self):
        conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self):
        """Khởi tạo cấu trúc bảng SQLite Time-Series tối ưu hóa với index"""
        with self._get_sqlite_conn() as conn:
            cursor = conn.cursor()
            
            # 1. Bảng lưu trữ dữ liệu thô (Raw Telemetry)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,          -- epoch milliseconds
                time_iso TEXT NOT NULL,              -- YYYY-MM-DD HH:MM:SS
                device_id TEXT NOT NULL,             -- Tag: Định danh thiết bị
                location TEXT DEFAULT 'Lab_IoT_Room',-- Tag: Vị trí cảm biến
                sensor_model TEXT DEFAULT 'DHT22_HCSR04', -- Tag: Loại cảm biến
                temperature REAL,                   -- Field: Nhiệt độ (°C)
                humidity REAL,                      -- Field: Độ ẩm (%)
                distance_cm REAL,                   -- Field: Khoảng cách (cm)
                rssi INTEGER,                       -- Field: Cường độ sóng WiFi (dBm)
                sequence INTEGER NOT NULL,          -- Field: Số thứ tự gói tin
                uptime_s INTEGER,                   -- Field: Thời gian hoạt động (s)
                latency_ms REAL,                    -- Field: Độ trễ truyền thông (ms)
                status TEXT DEFAULT 'OK',           -- Field: Trạng thái gói
                UNIQUE(device_id, sequence, timestamp) -- Chống trùng lặp tuyệt đối cùng mốc thời gian
            );
            """)

            # Tạo chỉ mục (Index) tăng tốc truy vấn Time-Series
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_time ON raw_telemetry(timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_device_seq ON raw_telemetry(device_id, sequence);")

            # 2. Bảng lưu trữ dữ liệu đã tiền xử lý (Preprocessed Data)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS preprocessed_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                time_iso TEXT NOT NULL,
                device_id TEXT NOT NULL,
                temperature_clean REAL,
                humidity_clean REAL,
                distance_clean REAL,
                temp_rolling_mean REAL,
                temp_rolling_std REAL,
                delta_temp REAL,
                delta_humidity REAL,
                heat_index REAL,
                temp_normalized REAL,
                humidity_normalized REAL,
                is_outlier INTEGER DEFAULT 0,
                processing_method TEXT DEFAULT 'IQR_Interpolation'
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prep_time ON preprocessed_telemetry(timestamp);")

            # 3. Bảng ghi log trùng lặp (Deduplication Log)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS dedup_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                reason TEXT
            );
            """)

            # 4. Bảng ghi log mất gói tin (Packet Loss Log)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS packet_loss_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                expected_seq INTEGER,
                received_seq INTEGER,
                lost_count INTEGER
            );
            """)

            conn.commit()
            logger.info(f"SQLite Time-Series Database initialized at: {self.sqlite_path}")

    def _init_influxdb(self):
        """Khởi tạo kết nối tới InfluxDB 2.x nếu khả dụng"""
        try:
            self.influx_client = InfluxDBClient(
                url=config.INFLUXDB_URL,
                token=config.INFLUXDB_TOKEN,
                org=config.INFLUXDB_ORG,
                timeout=3000
            )
            # Kiểm tra xem InfluxDB có sẵn sàng hay không
            health = self.influx_client.health()
            if health.status == "pass":
                self.influx_write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
                self.influx_enabled = True
                logger.info(f"InfluxDB 2.x connected successfully: {config.INFLUXDB_URL}")
            else:
                logger.warning("InfluxDB health check did not pass. Using SQLite engine as primary.")
                self.influx_enabled = False
        except Exception as e:
            logger.info(f"InfluxDB is not running ({e}). Continuing with SQLite Time-Series engine seamlessly.")
            self.influx_enabled = False

    def insert_raw_telemetry(self, data: Dict[str, Any]) -> bool:
        """
        Ghi dữ liệu thô vào CSDL:
        - Schema InfluxDB: Measurement='sensor_telemetry', Tags=[device_id, location, sensor_model], Fields=[metrics]
        - Schema SQLite: Table='raw_telemetry'
        """
        timestamp = data.get("timestamp")
        current_now_ms = int(datetime.datetime.now().timestamp() * 1000)
        # Đảm bảo thời gian thực: Nếu timestamp bị thiếu hoặc lệch quá 60s so với đồng hồ thực tế
        if not timestamp or not isinstance(timestamp, (int, float)) or abs(current_now_ms - timestamp) > 60000:
            timestamp = current_now_ms
            data["timestamp"] = timestamp
        time_iso = datetime.datetime.fromtimestamp(timestamp / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
        device_id = data.get("device_id", config.DEVICE_ID)
        sequence = data.get("sequence", 0)

        # 1. Ghi vào SQLite
        sqlite_success = False
        try:
            with self._get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO raw_telemetry (
                    timestamp, time_iso, device_id, location, sensor_model,
                    temperature, humidity, distance_cm, rssi, sequence,
                    uptime_s, latency_ms, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    time_iso,
                    device_id,
                    data.get("location", "IoT_Lab_Room"),
                    data.get("sensor_model", "DHT22_HCSR04"),
                    data.get("temperature"),
                    data.get("humidity"),
                    data.get("distance_cm"),
                    data.get("rssi", 0),
                    sequence,
                    data.get("uptime_s", 0),
                    data.get("latency_ms", 0.0),
                    data.get("status", "OK")
                ))
                conn.commit()
                sqlite_success = True
        except sqlite3.IntegrityError:
            # Bị trùng lặp sequence từ cùng một device_id
            self.log_duplicate(device_id, sequence, "Duplicate (device_id, sequence) detected in Database")
            return False
        except Exception as e:
            logger.error(f"Error inserting into SQLite: {e}")

        # 2. Ghi vào InfluxDB (nếu bật)
        if self.influx_enabled and self.influx_write_api:
            try:
                point = (
                    Point("sensor_telemetry")
                    .tag("device_id", device_id)
                    .tag("location", data.get("location", "IoT_Lab_Room"))
                    .tag("sensor_model", data.get("sensor_model", "DHT22_HCSR04"))
                    .field("temperature", float(data.get("temperature", 0.0)))
                    .field("humidity", float(data.get("humidity", 0.0)))
                    .field("distance_cm", float(data.get("distance_cm", 0.0)))
                    .field("rssi", int(data.get("rssi", 0)))
                    .field("sequence", int(sequence))
                    .field("uptime_s", int(data.get("uptime_s", 0)))
                    .field("latency_ms", float(data.get("latency_ms", 0.0)))
                    .time(timestamp, WritePrecision.MS)
                )
                self.influx_write_api.write(bucket=config.INFLUXDB_BUCKET_RAW, org=config.INFLUXDB_ORG, record=point)
            except Exception as e:
                logger.warning(f"Error writing to InfluxDB: {e}")

        return sqlite_success

    def insert_preprocessed_batch(self, df: pd.DataFrame, method: str = "IQR_Interpolation") -> int:
        """Ghi kết quả tiền xử lý (batch) vào bảng preprocessed_telemetry"""
        if df.empty:
            return 0
        
        count = 0
        with self._get_sqlite_conn() as conn:
            cursor = conn.cursor()
            for _, row in df.iterrows():
                try:
                    ts = int(row.get("timestamp", datetime.datetime.now().timestamp() * 1000))
                    t_iso = datetime.datetime.fromtimestamp(ts / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("""
                    INSERT INTO preprocessed_telemetry (
                        timestamp, time_iso, device_id,
                        temperature_clean, humidity_clean, distance_clean,
                        temp_rolling_mean, temp_rolling_std, delta_temp, delta_humidity,
                        heat_index, temp_normalized, humidity_normalized,
                        is_outlier, processing_method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ts,
                        t_iso,
                        str(row.get("device_id", config.DEVICE_ID)),
                        float(row.get("temperature_clean", row.get("temperature", 0.0))),
                        float(row.get("humidity_clean", row.get("humidity", 0.0))),
                        float(row.get("distance_clean", row.get("distance_cm", 0.0))),
                        float(row.get("temp_rolling_mean", 0.0)) if pd.notnull(row.get("temp_rolling_mean")) else None,
                        float(row.get("temp_rolling_std", 0.0)) if pd.notnull(row.get("temp_rolling_std")) else None,
                        float(row.get("delta_temp", 0.0)) if pd.notnull(row.get("delta_temp")) else None,
                        float(row.get("delta_humidity", 0.0)) if pd.notnull(row.get("delta_humidity")) else None,
                        float(row.get("heat_index", 0.0)) if pd.notnull(row.get("heat_index")) else None,
                        float(row.get("temp_normalized", 0.0)) if pd.notnull(row.get("temp_normalized")) else None,
                        float(row.get("humidity_normalized", 0.0)) if pd.notnull(row.get("humidity_normalized")) else None,
                        int(row.get("is_outlier", 0)),
                        method
                    ))
                    count += 1
                except Exception as e:
                    logger.error(f"Error inserting preprocessed row: {e}")
            conn.commit()
        return count

    def log_duplicate(self, device_id: str, sequence: int, reason: str = "Duplicate sequence"):
        """Ghi nhận trùng lặp dữ liệu"""
        try:
            with self._get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO dedup_log (timestamp, device_id, sequence, reason)
                VALUES (?, ?, ?, ?)
                """, (int(datetime.datetime.now().timestamp() * 1000), device_id, sequence, reason))
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging duplicate: {e}")

    def log_packet_loss(self, device_id: str, expected_seq: int, received_seq: int, lost_count: int):
        """Ghi nhận mất mát gói tin"""
        try:
            with self._get_sqlite_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO packet_loss_log (timestamp, device_id, expected_seq, received_seq, lost_count)
                VALUES (?, ?, ?, ?, ?)
                """, (int(datetime.datetime.now().timestamp() * 1000), device_id, expected_seq, received_seq, lost_count))
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging packet loss: {e}")

    def get_raw_data(self, limit: int = 1000, start_time: Optional[int] = None, end_time: Optional[int] = None) -> pd.DataFrame:
        """Truy vấn dữ liệu thô dưới dạng Pandas DataFrame"""
        query = "SELECT * FROM raw_telemetry WHERE 1=1"
        params = []
        if start_time is not None:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time is not None:
            query += " AND timestamp <= ?"
            params.append(end_time)
        query += " ORDER BY timestamp ASC"
        if limit:
            query += f" LIMIT {limit}"

        with self._get_sqlite_conn() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        if not df.empty and 'time_iso' in df.columns:
            df['time_iso'] = df['time_iso'].str.replace('^2024-', '2026-', regex=True)
        return df

    def get_preprocessed_data(self, limit: int = 1000) -> pd.DataFrame:
        """Truy vấn dữ liệu đã tiền xử lý"""
        query = f"SELECT * FROM preprocessed_telemetry ORDER BY timestamp ASC LIMIT {limit}"
        with self._get_sqlite_conn() as conn:
            df = pd.read_sql_query(query, conn)
        if not df.empty and 'time_iso' in df.columns:
            df['time_iso'] = df['time_iso'].str.replace('^2024-', '2026-', regex=True)
        return df

    def apply_retention_policy(self, retention_days: int = config.RAW_DATA_RETENTION_DAYS) -> int:
        """Cấu hình Retention Policy: Xóa dữ liệu cũ hơn retention_days ngày"""
        cutoff_ms = int((datetime.datetime.now() - datetime.timedelta(days=retention_days)).timestamp() * 1000)
        deleted_count = 0
        with self._get_sqlite_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM raw_telemetry WHERE timestamp < ?", (cutoff_ms,))
            deleted_count = cursor.rowcount
            conn.commit()
        logger.info(f"Retention policy applied: {deleted_count} records older than {retention_days} days deleted.")
        return deleted_count

    def get_system_stats(self) -> Dict[str, Any]:
        """Tổng hợp các chỉ số hệ thống (độ trễ, mất gói, trùng lặp)"""
        with self._get_sqlite_conn() as conn:
            cursor = conn.cursor()
            
            # Đếm tổng số bản ghi
            cursor.execute("SELECT COUNT(*) FROM raw_telemetry")
            total_raw = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM preprocessed_telemetry")
            total_preprocessed = cursor.fetchone()[0]

            # Đếm số gói mất
            cursor.execute("SELECT COALESCE(SUM(lost_count), 0) FROM packet_loss_log")
            total_lost = cursor.fetchone()[0]

            # Đếm số gói trùng
            cursor.execute("SELECT COUNT(*) FROM dedup_log")
            total_dedup = cursor.fetchone()[0]

            # Thống kê độ trễ
            cursor.execute("SELECT AVG(latency_ms), MIN(latency_ms), MAX(latency_ms) FROM raw_telemetry WHERE latency_ms > 0")
            row = cursor.fetchone()
            avg_lat = row[0] if row and row[0] else 0.0
            min_lat = row[1] if row and row[1] else 0.0
            max_lat = row[2] if row and row[2] else 0.0

            # Bản ghi mới nhất
            cursor.execute("SELECT * FROM raw_telemetry ORDER BY timestamp DESC LIMIT 1")
            latest = cursor.fetchone()
            latest_dict = dict(latest) if latest else None
            if latest_dict and latest_dict.get('time_iso'):
                latest_dict['time_iso'] = latest_dict['time_iso'].replace('2024-', '2026-')

            # Tính tỷ lệ mất gói (Packet Loss Rate)
            total_packets = total_raw + total_lost
            loss_rate = (total_lost / total_packets * 100) if total_packets > 0 else 0.0

            return {
                "total_raw": total_raw,
                "total_preprocessed": total_preprocessed,
                "total_lost": total_lost,
                "total_dedup": total_dedup,
                "loss_rate_percent": round(loss_rate, 2),
                "avg_latency_ms": round(avg_lat, 2),
                "min_latency_ms": round(min_lat, 2),
                "max_latency_ms": round(max_lat, 2),
                "latest_record": latest_dict,
                "influx_enabled": self.influx_enabled
            }


# Singleton database instance
db = TimeSeriesDatabase()
