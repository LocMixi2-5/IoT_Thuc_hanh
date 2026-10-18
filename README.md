# BÀI THỰC HÀNH SỐ 2: THU THẬP, LƯU TRỮ VÀ TIỀN XỬ LÝ DỮ LIỆU IoT

* **Học phần:** IoT và Ứng dụng (INT14149)
* **Sinh viên thực hiện:** Nguyễn Xuân Lộc
* **Mã sinh viên:** B23DCCN492
* **Khoa:** Công nghệ Thông tin - Học viện Công nghệ Bưu chính Viễn thông (PTIT)

---

## 📌 1. Giới thiệu tổng quan hệ thống

Dự án này là giải pháp toàn diện cho **Bài thực hành số 2: Thu thập, Lưu trữ và Tiền xử lý dữ liệu IoT**, được thiết kế theo kiến trúc phân tầng chuẩn công nghiệp:

1. **Perception & Embedded Firmware (ESP32):**
   - Đọc dữ liệu môi trường thực tế từ cảm biến nhiệt độ & độ ẩm **DHT22** và cảm biến siêu âm **HC-SR04** (đo khoảng cách vật cản cm).
   - Tích hợp giao thức **NTP (Network Time Protocol)** đồng bộ mốc thời gian thực tế (Unix epoch ms, GMT+7) kết hợp số thứ tự gói tin (**Sequence Number** tự tăng).
   - Đóng gói dữ liệu chuẩn JSON gọn nhẹ và Publish qua giao thức **MQTT (QoS=1)** lên Broker: `iot/B23DCCN492/esp32/telemetry`.

2. **Ingestion & Time-Series Storage Pipeline:**
   - Dịch vụ Gateway Python (`collector.py`) tự động lắng nghe topic MQTT, kiểm tra tính hợp lệ dữ liệu theo giới hạn vật lý (**Sanity Validation**).
   - Cơ chế chống trùng lặp (**Deduplication**) bằng bộ đệm trượt (Sliding Window LRU Cache) kết hợp ràng buộc `UNIQUE` tại CSDL.
   - Cơ chế phát hiện mất gói tin (**Packet Loss Tracking**) tức thời dựa trên bước nhảy của Sequence Number.
   - Tính toán và theo dõi độ trễ truyền thông **End-to-End Latency (ms)**.
   - Hệ thống CSDL Time-Series kép: Hỗ trợ **InfluxDB 2.x** chuyên dụng và **SQLite Time-Series Engine** cục bộ (được tối ưu hóa chỉ mục theo timestamp và device_id, hoạt động độc lập, tin cậy 100%).
   - Cấu hình chính sách lưu giữ (**Retention Policy**) tự động dọn dẹp các bản ghi cũ quá 07 ngày.

3. **Data Preprocessing Pipeline (Khoa học dữ liệu IoT):**
   - **Xử lý giá trị thiếu (Missing values):** Nội suy tuyến tính theo thời gian (Linear Time Interpolation), kết hợp Forward-fill (ffill) và Backward-fill (bfill).
   - **Phát hiện & Xử lý ngoại lai (Outliers):** Phương pháp tứ phân vị **IQR** ($Q1 - 1.5 \times IQR$ đến $Q3 + 1.5 \times IQR$) và phương pháp độ lệch chuẩn **Z-Score** ($|Z| > 3.0$). Kỹ thuật kẹp biên (Winsorization/Clipping) và Rolling Median.
   - **Resampling chuỗi thời gian:** Tổng hợp đa chiều theo các cửa sổ 30s, 1m, 5m (mean, min, max, std) giảm tải băng thông.
   - **Tạo đặc trưng (Feature Engineering):** Rolling Mean, Rolling Std (cửa sổ 5 bước), Delta thay đổi ($\Delta T$), Chỉ số nhiệt cảm nhận **Heat Index NOAA**.
   - **Chuẩn hóa dữ liệu (Scaling):** Min-Max Scaling về đoạn $[0, 1]$ phục vụ đào tạo các mô hình AI/ML.

4. **Giám sát & Đánh giá (Interactive Web Dashboard):**
   - Ứng dụng Web hiện đại xây dựng bằng **Streamlit** kết hợp đồ thị tương tác **Plotly** (hỗ trợ hoàn hảo cả Dark Mode và Light Mode).
   - Giám sát chuỗi thời gian Real-time với cảnh báo thông minh (quá nhiệt >35°C, vật cản gần <20cm).
   - Phòng thí nghiệm tiền xử lý tương tác trực quan: tùy biến tham số, xem biểu đồ đối sánh dữ liệu thô vs dữ liệu đã làm sạch.
   - Bảng phân tích và thống kê toàn diện các chỉ số chất lượng dịch vụ QoS (Mean Latency, Jitter, Packet Loss Rate, Deduplication count).
   - Quản trị CSDL và hỗ trợ tải dữ liệu trực tiếp dưới định dạng CSV (Raw Data & Preprocessed Data).

---

## 📂 2. Cấu trúc thư mục dự án

```text
IoT_Thuc_hanh/
│
├── src/                      # [MÃ NGUỒN XỬ LÝ DỮ LIỆU VÀ GIAO DIỆN IOT]
│   ├── config.py             # Cấu hình tập trung (MQTT, DB, ngưỡng kiểm tra, tiền xử lý)
│   ├── database.py           # Quản lý CSDL Time-Series (SQLite Indexing Engine & InfluxDB 2.x)
│   ├── collector.py          # Dịch vụ thu thập MQTT, validate, dedup, tính latency & ghi CSDL
│   ├── preprocessing.py      # Pipeline tiền xử lý (IQR, Z-Score, Interpolation, Feature Engineering)
│   ├── simulator.py          # Script giả lập ESP32 (hỗ trợ chèn outlier, missing, duplicate để kiểm thử)
│   └── app.py                # Web Dashboard tương tác giám sát Real-time & Tiền xử lý (Streamlit)
│
├── firmware/                 # [MÃ NGUỒN THIẾT BỊ NHÚNG ESP32]
│   ├── firmware.ino          # Firmware ESP32 nạp chip phần cứng hoặc mô phỏng Wokwi
│   ├── diagram.json          # Sơ đồ đấu nối linh kiện Wokwi Simulator
│   └── libraries.txt         # Danh sách thư viện nhúng Arduino/Wokwi
│
├── iot_timeseries.db         # Cơ sở dữ liệu Time-Series SQLite cục bộ
├── requirements.txt          # Danh sách thư viện Python cần thiết
└── README.md                 # Tài liệu hướng dẫn cài đặt và vận hành hệ thống
```

---

## 🚀 3. Hướng dẫn cài đặt và khởi chạy

### Bước 1: Cài đặt môi trường Python
Mở terminal tại thư mục gốc của dự án và chạy lệnh:
```bash
pip install -r requirements.txt
```

### Bước 2: Phát dữ liệu cảm biến từ ESP32 (Chọn 1 trong 2 cách)

#### Cách A: Chạy mô phỏng trên Wokwi Simulator
1. Mở dự án Wokwi hoặc tải thư mục `firmware/` lên [Wokwi.com](https://wokwi.com).
2. File mã nguồn `firmware.ino` và sơ đồ đấu nối `diagram.json` đã cấu hình sẵn cảm biến DHT22 (chân D15) và HC-SR04 (Trig D5, Echo D18).
3. Bấm nút **Start Simulation**. ESP32 sẽ kết nối mạng WiFi ảo, đồng bộ thời gian thực qua máy chủ NTP (`pool.ntp.org`) và gửi dữ liệu lên MQTT Broker định kỳ 3 giây/lần.

#### Cách B: Chạy bộ giả lập dữ liệu bằng Python (Khuyên dùng khi kiểm thử nhanh)
Mở một cửa sổ terminal và chạy:
```bash
# Giả lập phát dữ liệu liên tục kèm 10% ngoại lai và 5% mất gói để kiểm thử thuật toán:
python src/simulator.py --interval 3.0 --anomaly 0.10 --loss 0.05
```

### Bước 3: Khởi động bộ thu thập dữ liệu Gateway (Collector)
Mở terminal và chạy lệnh:
```bash
python src/collector.py
```
*Collector sẽ kết nối tới MQTT Broker (`broker.hivemq.com:1883`), tự động khởi tạo bảng Time-Series trong CSDL SQLite và tiếp nhận, chuẩn hóa mốc thời gian thực cũng như đo độ trễ End-to-End.*

### Bước 4: Khởi chạy Web Dashboard giám sát
Mở terminal và thực thi lệnh:
```bash
streamlit run src/app.py
```
Trình duyệt sẽ tự động mở giao diện tại: `http://localhost:8501`.

Giao diện Web gồm 4 Tab chính:
* **Tab 1: 📈 Giám Sát Thời Gian Thực:** Quan sát các thẻ KPI Metrics, biểu đồ chuỗi thời gian Nhiệt độ, Độ ẩm, Khoảng cách và bảng 10 bản ghi mới nhất.
* **Tab 2: 🔬 Phòng Thí Nghiệm Tiền Xử Lý:** Tùy biến thuật toán IQR / Z-Score, xem trực quan các điểm ngoại lai đỏ (x), theo dõi xu hướng Rolling Mean và Heat Index cảm nhận.
* **Tab 3: ⚡ Độ Trễ & Hiệu Năng Hệ Thống:** Phân tích độ trễ End-to-End theo thời gian (ms), biểu đồ Histogram tần suất độ trễ và bảng đánh giá chuẩn QoS.
* **Tab 4: 📑 Dữ Liệu CSDL:** Tải về tập dữ liệu thô (raw CSV) và tiền xử lý (preprocessed CSV), xem trực tiếp các bảng dữ liệu trong CSDL SQLite.

### Bước 5: Chạy quy trình tiền xử lý độc lập (Tùy chọn)
Nếu muốn chạy riêng pipeline tiền xử lý trực tiếp từ terminal:
```bash
python src/preprocessing.py
```

---

## 📊 4. Đặc tả Schema Cơ sở dữ liệu Time-Series

| Tên trường | Phân loại | Kiểu dữ liệu | Ý nghĩa & Ràng buộc toàn vẹn |
| :--- | :--- | :--- | :--- |
| `timestamp` | Primary Time | INTEGER (ms) | Mốc thời gian Unix epoch milliseconds đồng bộ NTP, đánh Index tăng tốc truy vấn |
| `time_iso` | Time String | TEXT | Thời gian đọc chuẩn định dạng ISO `YYYY-MM-DD HH:MM:SS` |
| `device_id` | Tag (Indexed) | TEXT | Mã định danh thiết bị nguồn (`ESP32_B23DCCN492`) |
| `location` | Tag (Indexed) | TEXT | Vị trí trạm quan trắc (`IoT_Lab_Room`) |
| `temperature` | Field (Metric) | REAL | Nhiệt độ môi trường (°C), phạm vi vật lý [-40.0, 80.0] |
| `humidity` | Field (Metric) | REAL | Độ ẩm tương đối không khí (%), phạm vi vật lý [0.0, 100.0] |
| `distance_cm` | Field (Metric) | REAL | Khoảng cách đo được từ HC-SR04 (cm), phạm vi [2.0, 400.0] |
| `sequence` | Field / Unique | INTEGER | Số thứ tự gói tin tự tăng, kết hợp `device_id` kiểm soát chống trùng lặp |
| `rssi` | Field (Metric) | INTEGER | Cường độ tín hiệu sóng WiFi (dBm) |
| `latency_ms` | Field (Metric) | REAL | Độ trễ truyền nhận End-to-End từ ESP32 đến Gateway Collector (ms) |
| `status` | Field | TEXT | Trạng thái gói tin (`OK`, `OUTLIER_TEMP_HIGH`, ...) |

---


* **Sinh viên:** Nguyễn Xuân Lộc
* **Mã sinh viên:** B23DCCN492
* **Khoa:** Công nghệ Thông tin - Học viện Công nghệ Bưu chính Viễn thông (PTIT)
* **GitHub Repository:** [https://github.com/LocMixi2-5/IoT_Thuc_hanh.git](https://github.com/LocMixi2-5/IoT_Thuc_hanh.git)
