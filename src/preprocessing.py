"""
Data Preprocessing Pipeline Module
BÀI THỰC HÀNH SỐ 2: THU THẬP, LƯU TRỮ VÀ TIỀN XỬ LÝ DỮ LIỆU IoT
Sinh viên: Nguyễn Xuân Lộc - B23DCCN492

Nhiệm vụ:
1. Đọc dữ liệu từ database theo khoảng thời gian.
2. Xử lý giá trị thiếu (Missing values: Interpolation, FFill, BFill).
3. Phát hiện và xử lý bất thường (Outliers: IQR, Z-Score, Clipping, Rolling Median).
4. Resampling theo cửa sổ thời gian (10s, 30s, 1m, 5m).
5. Tạo đặc trưng (Feature Engineering: Rolling Mean, Delta, Heat Index).
6. Chuẩn hóa dữ liệu (Min-Max Scaling, StandardScaler).
7. Lưu kết quả tiền xử lý vào database (bảng preprocessed_telemetry).
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Ensure src/ is in sys.path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Ensure UTF-8 output on Windows terminals
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler

import config
from database import db

logger = logging.getLogger("Preprocessing")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class IoTDataPreprocessor:
    """Pipeline tiền xử lý dữ liệu cảm biến thời gian thực"""

    def __init__(self):
        pass

    def load_raw_data(self, limit: int = 2000, start_time: Optional[int] = None, end_time: Optional[int] = None) -> pd.DataFrame:
        """Đọc dữ liệu thô từ database"""
        df = db.get_raw_data(limit=limit, start_time=start_time, end_time=end_time)
        if df.empty:
            logger.warning("Không có dữ liệu thô trong Database để xử lý.")
            return df
        
        # Chuyển đổi timestamp thành DatetimeIndex
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def handle_missing_values(self, df: pd.DataFrame, strategy: str = "linear") -> Tuple[pd.DataFrame, int]:
        """
        Xử lý giá trị thiếu (Missing Values):
        - linear: Nội suy tuyến tính theo thời gian (khuyên dùng cho time-series)
        - ffill: Forward-fill (lấy giá trị trước đó)
        - bfill: Backward-fill (lấy giá trị sau đó)
        - median: Điền giá trị trung vị
        """
        df_clean = df.copy()
        numeric_cols = ["temperature", "humidity", "distance_cm", "rssi"]
        total_missing = int(df_clean[numeric_cols].isnull().sum().sum())

        if total_missing > 0:
            logger.info(f"Phát hiện {total_missing} giá trị thiếu. Đang xử lý theo chiến lược '{strategy}'...")
            if strategy == "linear":
                df_clean[numeric_cols] = df_clean[numeric_cols].interpolate(method="linear").bfill().ffill()
            elif strategy == "ffill":
                df_clean[numeric_cols] = df_clean[numeric_cols].ffill().bfill()
            elif strategy == "bfill":
                df_clean[numeric_cols] = df_clean[numeric_cols].bfill().ffill()
            elif strategy == "median":
                for col in numeric_cols:
                    median_val = df_clean[col].median()
                    df_clean[col] = df_clean[col].fillna(median_val)
        return df_clean, total_missing

    def detect_and_handle_outliers(
        self,
        df: pd.DataFrame,
        method: str = "IQR",
        iqr_factor: float = config.OUTLIER_IQR_FACTOR,
        z_threshold: float = config.OUTLIER_ZSCORE_THRESHOLD,
        treatment: str = "clip"
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Phát hiện và xử lý Outlier:
        - Phương pháp: IQR (Interquartile Range) hoặc Z-Score
        - Phương án xử lý:
            - 'clip': Kẹp giá trị trong ngưỡng min/max hợp lệ (Winsorization)
            - 'median': Thay thế giá trị ngoại lai bằng Rolling Median (cửa sổ 5)
            - 'flag': Chỉ gắn nhãn is_outlier, giữ nguyên giá trị
        """
        df_out = df.copy()
        target_cols = ["temperature", "humidity", "distance_cm"]
        outlier_flags = pd.Series(0, index=df_out.index)
        outlier_counts = {}

        for col in target_cols:
            if col not in df_out.columns or df_out[col].dropna().empty:
                continue

            clean_col = f"{col}_clean"
            df_out[clean_col] = df_out[col].copy()

            if method.upper() == "IQR":
                q1 = df_out[col].quantile(0.25)
                q3 = df_out[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - iqr_factor * iqr
                upper_bound = q3 + iqr_factor * iqr
                
                # Tôn trọng giới hạn vật lý của cảm biến
                if col == "temperature":
                    lower_bound = max(lower_bound, config.VALIDATION_RULES["temperature"]["min"])
                    upper_bound = min(upper_bound, config.VALIDATION_RULES["temperature"]["max"])
                elif col == "humidity":
                    lower_bound = max(0.0, lower_bound)
                    upper_bound = min(100.0, upper_bound)
                elif col == "distance_cm":
                    lower_bound = max(2.0, lower_bound)
                    upper_bound = min(400.0, upper_bound)

                is_col_outlier = (df_out[col] < lower_bound) | (df_out[col] > upper_bound)

            else: # Phương pháp Z-score
                mean_val = df_out[col].mean()
                std_val = df_out[col].std()
                if std_val == 0 or np.isnan(std_val):
                    is_col_outlier = pd.Series(False, index=df_out.index)
                    lower_bound, upper_bound = mean_val, mean_val
                else:
                    z_scores = np.abs((df_out[col] - mean_val) / std_val)
                    is_col_outlier = z_scores > z_threshold
                    lower_bound = mean_val - z_threshold * std_val
                    upper_bound = mean_val + z_threshold * std_val

            count = int(is_col_outlier.sum())
            outlier_counts[col] = count
            outlier_flags = outlier_flags | is_col_outlier.astype(int)

            # Xử lý giá trị Outlier
            if treatment == "clip":
                df_out[clean_col] = df_out[col].clip(lower=lower_bound, upper=upper_bound)
            elif treatment == "median":
                rolling_med = df_out[col].rolling(window=5, min_periods=1, center=True).median()
                df_out.loc[is_col_outlier, clean_col] = rolling_med[is_col_outlier]
            elif treatment == "flag":
                df_out[clean_col] = df_out[col]

        df_out["is_outlier"] = outlier_flags
        total_outliers = int(outlier_flags.sum())

        stats = {
            "method": method,
            "treatment": treatment,
            "total_outliers": total_outliers,
            "detail": outlier_counts
        }
        return df_out, stats

    def calculate_heat_index(self, temp_c: pd.Series, humidity: pd.Series) -> pd.Series:
        """
        Tính chỉ số nhiệt độ cảm nhận Heat Index (NOAA / Rothfusz formula)
        Đầu vào: Nhiệt độ (°C), Độ ẩm (%)
        Đầu ra: Heat Index (°C)
        """
        # Chuyển độ C sang độ F
        tf = temp_c * 9.0 / 5.0 + 32.0
        rh = humidity

        # Công thức hồi quy Heat Index NOAA
        hi_f = (
            -42.379
            + 2.04901523 * tf
            + 10.14333127 * rh
            - 0.22475541 * tf * rh
            - 6.83783e-3 * (tf ** 2)
            - 5.481717e-2 * (rh ** 2)
            + 1.22874e-3 * (tf ** 2) * rh
            + 8.5282e-4 * tf * (rh ** 2)
            - 1.99e-6 * (tf ** 2) * (rh ** 2)
        )
        # Chuyển lại sang độ C
        hi_c = (hi_f - 32.0) * 5.0 / 9.0
        # Nếu nhiệt độ thấp (<26.7°C), Heat Index xấp xỉ bằng nhiệt độ thực tế
        hi_c = np.where(temp_c < 26.7, temp_c, hi_c)
        return pd.Series(hi_c, index=temp_c.index).round(2)

    def engineer_features(self, df: pd.DataFrame, window: int = config.FEATURE_ROLLING_WINDOW) -> pd.DataFrame:
        """
        Tạo đặc trưng mới (Feature Engineering):
        - Rolling Mean & Rolling Std: Xu hướng và độ biến động cục bộ
        - Delta: Biến thiên giữa hai chu kỳ đo (đạo hàm bậc 1)
        - Heat Index: Chỉ số oi bức kết hợp nhiệt ẩm
        """
        df_feat = df.copy()

        temp_col = "temperature_clean" if "temperature_clean" in df_feat.columns else "temperature"
        hum_col = "humidity_clean" if "humidity_clean" in df_feat.columns else "humidity"

        # 1. Rolling statistics (Cửa sổ trượt)
        df_feat["temp_rolling_mean"] = df_feat[temp_col].rolling(window=window, min_periods=1).mean().round(2)
        df_feat["temp_rolling_std"] = df_feat[temp_col].rolling(window=window, min_periods=1).std().fillna(0.0).round(3)

        # 2. Delta (Biến thiên qua từng bước đo)
        df_feat["delta_temp"] = df_feat[temp_col].diff().fillna(0.0).round(2)
        df_feat["delta_humidity"] = df_feat[hum_col].diff().fillna(0.0).round(2)

        # 3. Heat Index (Chỉ số nhiệt cảm nhận)
        df_feat["heat_index"] = self.calculate_heat_index(df_feat[temp_col], df_feat[hum_col])

        return df_feat

    def normalize_features(self, df: pd.DataFrame, method: str = "minmax") -> pd.DataFrame:
        """
        Chuẩn hóa dữ liệu (Scaling):
        - minmax: Đưa các thuộc tính về đoạn [0, 1]
        - standard: Đưa về phân phối chuẩn N(0, 1) với StandardScaler
        """
        df_norm = df.copy()
        cols_to_scale = []
        for col in ["temperature_clean", "humidity_clean", "distance_clean"]:
            if col in df_norm.columns:
                cols_to_scale.append(col)

        if not cols_to_scale or df_norm.empty:
            return df_norm

        if method == "minmax":
            scaler = MinMaxScaler()
            scaled_vals = scaler.fit_transform(df_norm[cols_to_scale])
            df_norm["temp_normalized"] = scaled_vals[:, 0].round(4)
            if len(cols_to_scale) > 1:
                df_norm["humidity_normalized"] = scaled_vals[:, 1].round(4)
        else:
            scaler = StandardScaler()
            scaled_vals = scaler.fit_transform(df_norm[cols_to_scale])
            df_norm["temp_normalized"] = scaled_vals[:, 0].round(4)
            if len(cols_to_scale) > 1:
                df_norm["humidity_normalized"] = scaled_vals[:, 1].round(4)

        return df_norm

    def resample_data(self, df: pd.DataFrame, interval: str = "30s") -> pd.DataFrame:
        """
        Resampling dữ liệu theo cửa sổ thời gian (10s, 30s, 1min, 5min):
        Áp dụng các hàm tổng hợp mean, min, max, std
        """
        if df.empty or 'datetime' not in df.columns:
            return df

        df_resample = df.set_index('datetime').resample(interval).agg({
            'temperature': ['mean', 'min', 'max'],
            'humidity': ['mean', 'min', 'max'],
            'distance_cm': ['mean', 'min', 'max'],
            'rssi': 'mean',
            'sequence': 'count'
        })
        # Làm phẳng multi-index cột
        df_resample.columns = [f"{col}_{stat}" for col, stat in df_resample.columns]
        df_resample = df_resample.rename(columns={'sequence_count': 'sample_count'}).dropna(how='all')
        return df_resample.reset_index()

    def run_full_pipeline(
        self,
        limit: int = 1000,
        missing_strategy: str = "linear",
        outlier_method: str = "IQR",
        outlier_treatment: str = "clip",
        save_to_db: bool = True
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Thực thi toàn bộ chu trình tiền xử lý và lưu kết quả vào CSDL"""
        logger.info("=== BẮT ĐẦU CHU TRÌNH TIỀN XỬ LÝ DỮ LIỆU IOT ===")
        
        # 1. Đọc dữ liệu
        df_raw = self.load_raw_data(limit=limit)
        if df_raw.empty:
            logger.warning("Không có dữ liệu đầu vào.")
            return pd.DataFrame(), {"status": "No data"}

        # 2. Xử lý Missing Values
        df_imputed, missing_count = self.handle_missing_values(df_raw, strategy=missing_strategy)

        # 3. Phát hiện & Xử lý Outlier
        df_clean, outlier_stats = self.detect_and_handle_outliers(
            df_imputed,
            method=outlier_method,
            treatment=outlier_treatment
        )

        # 4. Feature Engineering
        df_featured = self.engineer_features(df_clean)

        # 5. Normalization
        df_final = self.normalize_features(df_featured, method="minmax")

        # 6. Lưu vào Database
        saved_count = 0
        if save_to_db and not df_final.empty:
            method_label = f"{outlier_method}_{outlier_treatment}_{missing_strategy}"
            saved_count = db.insert_preprocessed_batch(df_final, method=method_label)
            logger.info(f"Đã lưu thành công {saved_count} bản ghi tiền xử lý vào database.")

        summary = {
            "total_input_records": len(df_raw),
            "missing_values_filled": missing_count,
            "outliers_detected": outlier_stats["total_outliers"],
            "outlier_detail": outlier_stats["detail"],
            "saved_records": saved_count
        }
        logger.info(f"Hoàn thành tiền xử lý: {summary}")
        return df_final, summary


# Singleton preprocessor
preprocessor = IoTDataPreprocessor()

if __name__ == "__main__":
    df, result = preprocessor.run_full_pipeline(limit=500, outlier_method="IQR", outlier_treatment="clip")
    print("\n--- KẾT QUẢ TIỀN XỬ LÝ DỮ LIỆU ---")
    print(f"Tổng bản ghi đầu vào: {result.get('total_input_records')}")
    print(f"Số giá trị thiếu đã bù: {result.get('missing_values_filled')}")
    print(f"Số ngoại lai phát hiện: {result.get('outliers_detected')}")
    if not df.empty:
        print("\n5 dòng dữ liệu đầu tiên sau tiền xử lý:")
        cols_to_show = ["time_iso", "temperature", "temperature_clean", "humidity_clean", "temp_rolling_mean", "heat_index", "is_outlier"]
        print(df[[c for c in cols_to_show if c in df.columns]].head())
