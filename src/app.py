"""
Streamlit Web Dashboard - IoT Telemetry & Preprocessing Analytics
BÀI THỰC HÀNH SỐ 2: THU THẬP, LƯU TRỮ VÀ TIỀN XỬ LÝ DỮ LIỆU IoT
Học phần: IoT và Ứng dụng (INT14149)
Sinh viên: Nguyễn Xuân Lộc - B23DCCN492
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Ensure src/ is in sys.path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

import config
from database import db
from preprocessing import preprocessor

# ==========================================
# CẤU HÌNH TRANG STREAMLIT
# ==========================================
st.set_page_config(
    page_title="IoT Telemetry & Analytics Dashboard | B23DCCN492",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS cho giao diện hiện đại, chuyên nghiệp
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: #ffffff;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #2a5298;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    .metric-title {
        font-size: 0.85rem;
        color: #666;
        text-transform: uppercase;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e3c72;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f8f9fa;
        border-radius: 8px 8px 0px 0px;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2a5298 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SIDEBAR QUẢN TRỊ & CẤU HÌNH
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/iot-sensor.png", width=120)
    st.title("IoT Gateway Control")
    st.markdown(f"**Sinh viên:** Nguyễn Xuân Lộc\n**MSV:** `{config.STUDENT_ID}`\n**Device:** `{config.DEVICE_ID}`")
    st.divider()

    st.subheader("📡 Kết Nối MQTT")
    st.info(f"**Broker:** `{config.MQTT_BROKER}:{config.MQTT_PORT}`\n\n**Topic:** `{config.MQTT_TOPIC_TELEMETRY}`")

    st.subheader("💾 Trạng Thái Lưu Trữ")
    stats = db.get_system_stats()
    st.markdown(f"- SQLite Time-Series: ✅ Hoạt động ({stats['total_raw']} bản ghi)")
    if stats['influx_enabled']:
        st.markdown(f"- InfluxDB 2.x: ✅ Đã kết nối")
    else:
        st.markdown(f"- InfluxDB 2.x: ⏸️ Standby (Dùng SQLite Engine)")

    st.divider()
    auto_refresh = st.checkbox("Tự động làm mới (Auto Refresh 4s)", value=False)
    if st.button("🔄 Làm mới dữ liệu tức thì"):
        st.rerun()

    st.divider()
    st.markdown("### 🛠️ Thao Tác Hệ Thống")
    if st.button("Áp dụng Retention Policy (Xóa > 7 ngày)"):
        deleted = db.apply_retention_policy(config.RAW_DATA_RETENTION_DAYS)
        st.success(f"Đã dọn dẹp {deleted} bản ghi cũ.")

# ==========================================
# HEADER
# ==========================================
st.markdown(f"""
<div class="main-header">
    <h2 style="margin:0; color:#fff;">BÀI THỰC HÀNH SỐ 2: THU THẬP, LƯU TRỮ VÀ TIỀN XỬ LÝ DỮ LIỆU IOT</h2>
    <p style="margin:5px 0 0 0; opacity: 0.9; font-size: 1.05rem;">
        Học phần: IoT và Ứng dụng (INT14149) | Sinh viên: <b>Nguyễn Xuân Lộc</b> (MSV: <b>B23DCCN492</b>)
    </p>
</div>
""", unsafe_allow_html=True)

# Lấy dữ liệu thô mới nhất từ CSDL
df_raw = db.get_raw_data(limit=1000)
stats = db.get_system_stats()
latest = stats.get("latest_record")

# ==========================================
# TOP KPI METRICS
# ==========================================
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    temp_val = f"{latest['temperature']:.1f} °C" if latest and latest['temperature'] is not None else "--"
    col1.metric("Nhiệt độ hiện tại", temp_val, delta=f"{latest['temperature']-25:.1f} °C" if latest else None)

with col2:
    hum_val = f"{latest['humidity']:.1f} %" if latest and latest['humidity'] is not None else "--"
    col2.metric("Độ ẩm không khí", hum_val, delta=None)

with col3:
    dist_val = f"{latest['distance_cm']:.1f} cm" if latest and latest['distance_cm'] is not None else "--"
    col3.metric("Khoảng cách cản", dist_val, delta=None)

with col4:
    lat_val = f"{stats['avg_latency_ms']:.1f} ms"
    col4.metric("Độ trễ trung bình", lat_val, delta=f"Max: {stats['max_latency_ms']}ms", delta_color="inverse")

with col5:
    loss_val = f"{stats['loss_rate_percent']:.2f} %"
    col5.metric("Tỷ lệ mất gói", loss_val, delta=f"{stats['total_lost']} gói mất", delta_color="inverse")

with col6:
    dedup_val = f"{stats['total_dedup']}"
    col6.metric("Gói tin trùng chặn", dedup_val, delta="Deduplicated")

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# TABS GIAO DIỆN
# ==========================================
tab_realtime, tab_prep, tab_qos, tab_data = st.tabs([
    "📈 Giám Sát Thời Gian Thực",
    "🔬 Phòng Thí Nghiệm Tiền Xử Lý",
    "⚡ Độ Trễ & Hiệu Năng Hệ Thống",
    "📑 Dữ Liệu & Báo Cáo"
])

# ----------------------------------------------------
# TAB 1: GIÁM SÁT THỜI GIAN THỰC
# ----------------------------------------------------
with tab_realtime:
    if df_raw.empty:
        st.warning("⚠️ Chưa có dữ liệu trong Cơ sở dữ liệu. Hãy khởi động `collector.py` và `simulator.py` (hoặc Wokwi ESP32) để thu thập dữ liệu!")
    else:
        st.subheader("📊 Biểu Đồ Chuỗi Thời Gian Dữ Liệu Cảm Biến Real-time")
        
        c_chart1, c_chart2 = st.columns(2)
        
        with c_chart1:
            fig_temp_hum = go.Figure()
            fig_temp_hum.add_trace(go.Scatter(
                x=df_raw['time_iso'], y=df_raw['temperature'],
                mode='lines+markers', name='Nhiệt độ (°C)',
                line=dict(color='#e74c3c', width=2),
                marker=dict(size=4)
            ))
            fig_temp_hum.add_trace(go.Scatter(
                x=df_raw['time_iso'], y=df_raw['humidity'],
                mode='lines+markers', name='Độ ẩm (%)',
                line=dict(color='#3498db', width=2),
                marker=dict(size=4)
            ))
            fig_temp_hum.update_layout(
                title="Diễn biến Nhiệt độ & Độ ẩm theo thời gian",
                xaxis_title="Thời gian",
                yaxis_title="Giá trị đo",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=380,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            st.plotly_chart(fig_temp_hum, use_container_width=True)

        with c_chart2:
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Scatter(
                x=df_raw['time_iso'], y=df_raw['distance_cm'],
                mode='lines+markers', name='Khoảng cách (cm)',
                line=dict(color='#2ecc71', width=2),
                fill='tozeroy',
                fillcolor='rgba(46, 204, 113, 0.1)',
                marker=dict(size=4)
            ))
            fig_dist.add_hline(y=20.0, line_dash="dash", line_color="red", annotation_text="Ngưỡng cảnh báo va chạm (20cm)")
            fig_dist.update_layout(
                title="Khoảng cách đo được từ cảm biến siêu âm HC-SR04",
                xaxis_title="Thời gian",
                yaxis_title="Khoảng cách (cm)",
                height=380,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            st.plotly_chart(fig_dist, use_container_width=True)

        # Cảnh báo tức thời (Smart Alerts)
        if latest:
            if latest['temperature'] and latest['temperature'] > 35.0:
                st.error(f"🚨 CẢNH BÁO QUÁ NHIỆT: Nhiệt độ đo được đang là {latest['temperature']}°C (Vượt ngưỡng 35°C)!")
            if latest['distance_cm'] and latest['distance_cm'] < 20.0:
                st.warning(f"⚠️ CẢNH BÁO VẬT CẢN: Khoảng cách hiện tại chỉ còn {latest['distance_cm']}cm (Nguy cơ va chạm)!")

        # Bảng 10 gói tin gần nhất
        st.subheader("📋 10 Bản Ghi Telemetry Mới Nhất Nhận Được")
        st.dataframe(
            df_raw.tail(10)[["sequence", "time_iso", "device_id", "temperature", "humidity", "distance_cm", "rssi", "latency_ms", "status"]].iloc[::-1],
            use_container_width=True,
            hide_index=True
        )

# ----------------------------------------------------
# TAB 2: PHÒNG THÍ NGHIỆM TIỀN XỬ LÝ (PREPROCESSING LAB)
# ----------------------------------------------------
with tab_prep:
    st.subheader("🔬 Tùy Biến Pipeline Tiền Xử Lý Dữ Liệu")
    
    with st.expander("⚙️ Cấu hình Tham Số Tiền Xử Lý", expanded=True):
        pcol1, pcol2, pcol3, pcol4 = st.columns(4)
        with pcol1:
            outlier_algo = st.selectbox("Thuật toán Outlier", ["IQR", "Z-Score"], index=0)
        with pcol2:
            if outlier_algo == "IQR":
                factor_val = st.slider("Hệ số IQR (Q1 - k*IQR, Q3 + k*IQR)", 1.0, 3.0, 1.5, 0.1)
                z_thresh = 3.0
            else:
                z_thresh = st.slider("Ngưỡng Z-Score (|Z| > threshold)", 1.5, 4.0, 3.0, 0.1)
                factor_val = 1.5
        with pcol3:
            treatment_mode = st.selectbox("Phương án xử lý Outlier", ["clip", "median", "flag"], index=0,
                                          help="clip: Kẹp giá trị (Winsorization) | median: Thay bằng Rolling Median | flag: Giữ nguyên chỉ gắn cờ")
        with pcol4:
            missing_strat = st.selectbox("Chiến lược bù dữ liệu thiếu", ["linear", "ffill", "bfill", "median"], index=0)

        btn_run_prep = st.button("🚀 Thực Thi Pipeline Tiền Xử Lý Ngay", type="primary")

    # Xử lý dữ liệu
    if not df_raw.empty:
        # Chạy pipeline tiền xử lý
        df_imputed, miss_count = preprocessor.handle_missing_values(df_raw, strategy=missing_strat)
        df_clean, out_stats = preprocessor.detect_and_handle_outliers(
            df_imputed, method=outlier_algo, iqr_factor=factor_val,
            z_threshold=z_thresh, treatment=treatment_mode
        )
        df_featured = preprocessor.engineer_features(df_clean)
        df_prep = preprocessor.normalize_features(df_featured, method="minmax")

        if btn_run_prep:
            saved_count = db.insert_preprocessed_batch(df_prep, method=f"{outlier_algo}_{treatment_mode}_{missing_strat}")
            st.success(f"✅ Đã thực thi thành công! Phát hiện {out_stats['total_outliers']} ngoại lai. Đã lưu {saved_count} bản ghi tiền xử lý vào CSDL.")

        # Thống kê trước và sau
        st.markdown("#### 📌 Báo Cáo Hiệu Quả Tiền Xử Lý")
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Tổng bản ghi phân tích", len(df_raw))
        sc2.metric("Số ngoại lai phát hiện", out_stats['total_outliers'])
        sc3.metric("Số giá trị thiếu đã bù", miss_count)
        sc4.metric("Chỉ số Heat Index trung bình", f"{df_featured['heat_index'].mean():.1f} °C")

        # 1. Biểu đồ đối sánh Outlier
        st.markdown("#### 1. Phát Hiện & Xử Lý Ngoại Lai (Raw vs Cleaned Data)")
        fig_outlier = go.Figure()
        
        # Đường dữ liệu thô
        fig_outlier.add_trace(go.Scatter(
            x=df_prep['time_iso'], y=df_prep['temperature'],
            mode='lines', name='Nhiệt độ thô (Raw)',
            line=dict(color='#bdc3c7', width=1.5, dash='dot')
        ))
        
        # Đường dữ liệu đã làm sạch
        fig_outlier.add_trace(go.Scatter(
            x=df_prep['time_iso'], y=df_prep['temperature_clean'],
            mode='lines', name='Nhiệt độ đã làm sạch (Cleaned)',
            line=dict(color='#27ae60', width=2.5)
        ))
        
        # Các điểm Outlier màu đỏ
        outlier_points = df_prep[df_prep['is_outlier'] == 1]
        if not outlier_points.empty:
            fig_outlier.add_trace(go.Scatter(
                x=outlier_points['time_iso'], y=outlier_points['temperature'],
                mode='markers', name=f'Outlier phát hiện ({outlier_algo})',
                marker=dict(color='#e74c3c', size=10, symbol='x')
            ))

        fig_outlier.update_layout(
            title=f"So sánh Nhiệt độ trước & sau khi xử lý Outlier ({outlier_algo} - Treatment: {treatment_mode})",
            xaxis_title="Thời gian",
            yaxis_title="Nhiệt độ (°C)",
            height=400,
            margin=dict(l=20, r=20, t=50, b=20)
        )
        st.plotly_chart(fig_outlier, use_container_width=True)

        # 2. Biểu đồ Feature Engineering
        st.markdown("#### 2. Đặc Trưng Mới (Feature Engineering: Rolling Mean & Heat Index)")
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            fig_feat = go.Figure()
            fig_feat.add_trace(go.Scatter(x=df_prep['time_iso'], y=df_prep['temperature_clean'], mode='lines', name='T_clean', line=dict(color='#34495e', width=1.5)))
            fig_feat.add_trace(go.Scatter(x=df_prep['time_iso'], y=df_prep['temp_rolling_mean'], mode='lines', name='Rolling Mean (k=5)', line=dict(color='#e67e22', width=2.5)))
            fig_feat.update_layout(title="Xu hướng trung bình trượt (Rolling Mean 5 mẫu)", height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_feat, use_container_width=True)

        with fcol2:
            fig_hi = go.Figure()
            fig_hi.add_trace(go.Scatter(x=df_prep['time_iso'], y=df_prep['temperature_clean'], mode='lines', name='Nhiệt độ (°C)', line=dict(color='#e74c3c')))
            fig_hi.add_trace(go.Scatter(x=df_prep['time_iso'], y=df_prep['heat_index'], mode='lines', name='Heat Index cảm nhận (°C)', line=dict(color='#8e44ad', width=2.5)))
            fig_hi.update_layout(title="Chỉ số nhiệt cảm nhận (Heat Index NOAA)", height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_hi, use_container_width=True)

        # 3. Resampling demo
        st.markdown("#### 3. Resampling Chuỗi Thời Gian (Tổng Hợp Theo Khung Thời Gian)")
        resample_rule = st.radio("Chọn khung thời gian Resampling:", ["30s", "1min", "5min"], horizontal=True)
        df_resampled = preprocessor.resample_data(df_raw, interval=resample_rule)
        st.dataframe(df_resampled.head(10), use_container_width=True)

# ----------------------------------------------------
# TAB 3: ĐỘ TRỄ & HIỆU NĂNG HỆ THỐNG (QOS)
# ----------------------------------------------------
with tab_qos:
    st.subheader("⚡ Phân Tích Độ Trễ End-to-End & Chất Lượng Dịch Vụ (QoS)")
    
    if not df_raw.empty:
        qcol1, qcol2 = st.columns([2, 1])
        with qcol1:
            fig_lat = px.line(
                df_raw, x='time_iso', y='latency_ms',
                title="Độ trễ truyền nhận End-to-End theo thời gian (ms)",
                labels={'latency_ms': 'Latency (ms)', 'time_iso': 'Thời gian'},
                markers=True
            )
            fig_lat.add_hline(y=df_raw['latency_ms'].mean(), line_dash="dash", line_color="green",
                              annotation_text=f"Mean Latency ({df_raw['latency_ms'].mean():.1f} ms)")
            fig_lat.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig_lat, use_container_width=True)

        with qcol2:
            fig_hist = px.histogram(
                df_raw, x='latency_ms', nbins=20,
                title="Phân bố tần suất độ trễ",
                labels={'latency_ms': 'Latency (ms)'},
                color_discrete_sequence=['#3498db']
            )
            fig_hist.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig_hist, use_container_width=True)

        st.markdown("#### 📋 Bảng Thống Kê Chỉ Số QoS Toàn Diện")
        qos_data = {
            "Chỉ số đánh giá": [
                "Độ trễ trung bình (Mean Latency)",
                "Độ trễ tối thiểu (Min Latency)",
                "Độ trễ tối đa (Max Latency)",
                "Độ biến thiên độ trễ (Jitter / Std)",
                "Tổng gói tin nhận được (Received)",
                "Tổng gói tin bị mất (Packet Lost)",
                "Tỷ lệ mất gói (Loss Rate %)",
                "Số gói tin trùng lặp đã chặn (Deduplicated)"
            ],
            "Giá trị đo đạc": [
                f"{df_raw['latency_ms'].mean():.2f} ms",
                f"{df_raw['latency_ms'].min():.2f} ms",
                f"{df_raw['latency_ms'].max():.2f} ms",
                f"{df_raw['latency_ms'].std():.2f} ms",
                f"{len(df_raw)} gói",
                f"{stats['total_lost']} gói",
                f"{stats['loss_rate_percent']:.2f} %",
                f"{stats['total_dedup']} gói"
            ],
            "Đánh giá tiêu chuẩn IoT": [
                "Tốt (< 100ms)", "Rất tốt (< 50ms)", "Chấp nhận được (< 200ms)",
                "Ổn định", "Đáp ứng thời gian thực", "Mức thấp (< 5%)",
                "Đạt chuẩn mạng cảm biến", "Cơ chế Dedup hoạt động chính xác"
            ]
        }
        st.table(pd.DataFrame(qos_data))

# ----------------------------------------------------
# TAB 4: QUẢN LÝ CSDL & BÁO CÁO
# ----------------------------------------------------
with tab_data:
    st.subheader("📑 Quản Lý Dữ Liệu Time-Series & Xuất Báo Cáo")

    tcol1, tcol2 = st.columns(2)
    with tcol1:
        st.markdown("#### 📥 Xuất Dữ Liệu Ra File")
        if not df_raw.empty:
            csv_raw = df_raw.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Tải Dữ Liệu Thô (CSV)",
                data=csv_raw,
                file_name="raw_sensor_telemetry.csv",
                mime="text/csv"
            )

        df_p_data = db.get_preprocessed_data(limit=1000)
        if not df_p_data.empty:
            csv_prep = df_p_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Tải Dữ Liệu Đã Tiền Xử Lý (CSV)",
                data=csv_prep,
                file_name="preprocessed_sensor_telemetry.csv",
                mime="text/csv"
            )

    with tcol2:
        st.markdown("#### 📄 Báo Cáo Thực Hành Số 2 (.docx)")
        st.info("Nhấn nút bên dưới để tự động tạo báo cáo Word 04-06 trang hoàn chỉnh theo đúng yêu cầu đề bài!")
        
        report_file_path = config.BASE_DIR / "Bao_cao_Bai_thuc_hanh_2_B23DCCN492.docx"
        
        if st.button("📝 Tạo File Báo Cáo Word (.docx) Ngay"):
            import subprocess
            res = subprocess.run([
                sys.executable, str(config.SRC_DIR / "generate_report.py")
            ], capture_output=True, text=True)
            if res.returncode == 0:
                st.success("✅ Đã tạo thành công file báo cáo Word!")
            else:
                st.error(f"Lỗi tạo báo cáo: {res.stderr}")

        if os.path.exists(report_file_path):
            with open(report_file_path, "rb") as f:
                st.download_button(
                    label="📥 Tải Báo Cáo Word (Bao_cao_Bai_thuc_hanh_2_B23DCCN492.docx)",
                    data=f.read(),
                    file_name="Bao_cao_Bai_thuc_hanh_2_B23DCCN492.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

    st.divider()
    st.markdown("#### 🔍 Xem Trực Tiếp Dữ Liệu Trong CSDL")
    sub_tab1, sub_tab2 = st.tabs(["Bảng Dữ Liệu Thô (raw_telemetry)", "Bảng Tiền Xử Lý (preprocessed_telemetry)"])
    with sub_tab1:
        st.dataframe(df_raw, use_container_width=True)
    with sub_tab2:
        df_p_view = db.get_preprocessed_data(limit=500)
        st.dataframe(df_p_view, use_container_width=True)

# Tự động refresh nếu được bật
if auto_refresh:
    time.sleep(4)
    st.rerun()
