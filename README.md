# BÀI THỰC HÀNH SỐ 2: THU THẬP, LƯU TRỮ VÀ TIỀN XỬ LÝ DỮ LIỆU IoT

* **Học phần:** IoT và Ứng dụng (INT14149)
* **Sinh viên:** Nguyễn Xuân Lộc
* **Mã sinh viên:** B23DCCN492
* **Lớp:** D23CQCN01-B

---

## 📌 1. Giới thiệu tổng quan

Dự án này là lời giải hoàn chỉnh cho **Bài thực hành số 2: Thu thập, Lưu trữ và Tiền xử lý dữ liệu IoT**, bao gồm:
1. **Perception & Embedded Firmware (ESP32):**
   - Đọc dữ liệu từ cảm biến nhiệt độ & độ ẩm **DHT22** và cảm biến siêu âm **HC-SR04** (khoảng cách cm).
   - Đóng gói dữ liệu định dạng chuẩn JSON kèm đồng bộ chuỗi thời gian NTP (epoch ms) và Sequence Number.
   - Publish dữ liệu qua giao thức **MQTT (QoS=1)** lên Broker theo cấu trúc topic chuẩn: `iot/B23DCCN492/esp32/telemetry`.
2. **Ingestion & Storage Pipeline:**
   - Client Python `collector.py` subscribe topic, kiểm tra tính hợp lệ dữ liệu (Sanity checks).
   - Cơ chế chống trùng lặp (**Deduplication**) bằng Cache LRU và ràng buộc CSDL.
   - Cơ chế phát hiện mất gói tin (**Packet Loss Tracking**) theo Sequence.
   - Đo đạc độ trễ truyền thông **End-to-End Latency (ms)**.
   - CSDL Time-Series kép: Hỗ trợ **InfluxDB 2.x** chuyên dụng và **SQLite Time-Series Engine** cục bộ (tự động tạo index thời gian, không phụ thuộc dịch vụ ngoài, độ tin cậy 100%).
   - Cấu hình chính sách lưu giữ (**Retention Policy**) tự động dọn dẹp dữ liệu cũ quá 7 ngày.
3. **Data Preprocessing Pipeline (Khoa học dữ liệu IoT):**
   - **Xử lý giá trị thiếu (Missing values):** Nội suy tuyến tính theo thời gian (Linear Time Interpolation), Forward-fill (ffill).
   - **Phát hiện & Xử lý ngoại lai (Outliers):** Phương pháp tứ phân vị **IQR** ($Q1 - 1.5 \times IQR$ đến $Q3 + 1.5 \times IQR$) và phương pháp độ lệch chuẩn **Z-Score** ($|Z| > 3.0$). Kỹ thuật kẹp biên (Winsorization/Clipping) và Rolling Median.
   - **Resampling chuỗi thời gian:** Tổng hợp đa chiều theo cửa sổ 30s, 1m, 5m (mean, min, max, std).
   - **Tạo đặc trưng (Feature Engineering):** Rolling Mean, Rolling Std (5 bước), Delta thay đổi ($\Delta T, \Delta H$), Chỉ số nhiệt độ cảm nhận **Heat Index NOAA**.
   - **Chuẩn hóa dữ liệu (Scaling):** Min-Max Scaling [0, 1] và StandardScaler N(0, 1).
4. **Giám sát & Đánh giá (Interactive Dashboard):**
   - Web App hiện đại xây dựng bằng **Streamlit** và biểu đồ động **Plotly**.
   - Hiển thị KPIs thời gian thực, cảnh báo quá nhiệt (>35°C), cảnh báo vật cản gần (<20cm).
   - Phòng thí nghiệm tiền xử lý tương tác trực tiếp (so sánh dữ liệu thô vs dữ liệu đã làm sạch).
   - Bảng phân tích chỉ số QoS (độ trễ trung bình, max latency, jitter, tỷ lệ mất gói).
   - Tải dữ liệu CSV và tự động sinh file Báo cáo Word (`.docx`) 04-06 trang.

---

## 📂 2. Cấu trúc thư mục dự án

```text
bai2/
│
├── config.py                 # Cấu hình tập trung (MQTT, DB, ngưỡng kiểm tra, tiền xử lý)
├── database.py               # Quản lý CSDL Time-Series kép (SQLite Indexing & InfluxDB 2.x)
├── collector.py              # Dịch vụ thu thập MQTT, validate, dedup, tính latency & ghi DB
├── preprocessing.py          # Pipeline tiền xử lý (IQR, Z-Score, Interpolation, Feature Engineering)
├── simulator.py              # Script giả lập ESP32 (hỗ trợ chèn outlier, missing, duplicate để test)
├── app.py                    # Web Dashboard tương tác giám sát Real-time & Tiền xử lý (Streamlit)
├── generate_report.py        # Script tự động sinh Báo cáo Word 04-06 trang chuẩn định dạng
│
├── firmware/
│   ├── firmware.ino          # Mã nguồn nạp vi điều khiển ESP32
│   ├── diagram.json          # Sơ đồ kết nối phần cứng trên Wokwi Simulator
│   └── libraries.txt         # Danh sách thư viện Wokwi
│
├── wifi-scan.ino             # File Arduino ở thư mục gốc để Wokwi mở chạy trực tiếp
├── diagram.json              # File diagram gốc cho Wokwi
├── requirements.txt          # Danh sách thư viện Python cần cài đặt
├── docker-compose.yml        # (Tùy chọn) Chạy Mosquitto, InfluxDB, Grafana qua Docker
├── mosquitto.conf            # Cấu hình Mosquitto cho Docker
├── README.md                 # Tài liệu hướng dẫn sử dụng chi tiết
└── Bao_cao_Bai_thuc_hanh_2_B23DCCN492.docx # Báo cáo thực hành hoàn chỉnh
```

---

## 🚀 3. Hướng dẫn cài đặt và khởi chạy

### Bước 1: Cài đặt thư viện Python
Mở terminal tại thư mục dự án và chạy:
```bash
pip install -r requirements.txt
```

### Bước 2: Khởi động bộ thu thập dữ liệu (Collector)
Chạy script lắng nghe và thu thập dữ liệu từ MQTT Broker:
```bash
python collector.py
```
*Collector sẽ kết nối tới MQTT Broker (`broker.emqx.io:1883`), tự động khởi tạo bảng Time-Series trong CSDL và chờ dữ liệu.*

### Bước 3: Phát dữ liệu cảm biến (Chọn 1 trong 2 cách)

#### Cách 3A: Chạy bằng Wokwi Simulator
- Mở liên kết Wokwi của bạn hoặc tải thư mục này lên [Wokwi.com](https://wokwi.com).
- File code `wifi-scan.ino` và sơ đồ `diagram.json` đã được cấu hình sẵn.
- Nhấn nút **Play** (Simulation). ESP32 sẽ kết nối WiFi ảo, đồng bộ giờ NTP và bắt đầu publish dữ liệu mỗi 4 giây lên MQTT.

#### Cách 3B: Chạy bằng Simulator Python (Khuyên dùng khi muốn kiểm thử nhanh)
Mở một cửa sổ terminal mới và chạy:
```bash
# Gửi dữ liệu mô phỏng liên tục kèm 10% ngoại lai và 5% mất gói để test:
python simulator.py --interval 3.0 --anomaly 0.10 --loss 0.05
```

### Bước 4: Khởi chạy Web Dashboard giám sát
Mở terminal thứ 3 và chạy lệnh:
```bash
streamlit run app.py
```
Trình duyệt sẽ tự động mở địa chỉ: `http://localhost:8501`.
Giao diện bao gồm 4 Tab chính:
- **Tab 1: Giám sát thời gian thực:** Xem biểu đồ sống của Nhiệt độ, Độ ẩm, Khoảng cách, cảnh báo thông minh.
- **Tab 2: Phòng thí nghiệm tiền xử lý:** Trực quan hóa Outlier bằng chấm đỏ, so sánh trước/sau khi làm sạch, xem Heat Index và Rolling Mean.
- **Tab 3: Độ trễ & QoS:** Phân tích độ trễ End-to-End, Jitter, tỷ lệ mất gói.
- **Tab 4: Dữ liệu & Báo cáo:** Tải file CSV và tạo file Báo cáo Word.

### Bước 5: Thực thi tiền xử lý độc lập (Tùy chọn)
Nếu muốn chạy riêng script tiền xử lý từ dòng lệnh:
```bash
python preprocessing.py
```

### Bước 6: Tạo file Báo cáo Word (.docx)
Để xuất ra file báo cáo 04-06 trang hoàn chỉnh:
```bash
python generate_report.py
```
File báo cáo `Bao_cao_Bai_thuc_hanh_2_B23DCCN492.docx` sẽ được tạo ra tại thư mục gốc.

---

## 📊 4. Đặc tả Schema Cơ sở dữ liệu Time-Series

| Tên trường | Phân loại | Kiểu dữ liệu | Ý nghĩa |
| :--- | :--- | :--- | :--- |
| `timestamp` | Primary Time | INTEGER (ms) | Mốc thời gian đồng bộ NTP, đánh Index tăng tốc truy vấn |
| `device_id` | Tag (Indexed) | TEXT | Mã thiết bị (`ESP32_B23DCCN492`) |
| `location` | Tag (Indexed) | TEXT | Vị trí cảm biến (`Lab_IoT_Room`) |
| `temperature` | Field (Metric) | REAL | Nhiệt độ môi trường (°C), phạm vi [-40, 80] |
| `humidity` | Field (Metric) | REAL | Độ ẩm không khí (%), phạm vi [0, 100] |
| `distance_cm` | Field (Metric) | REAL | Khoảng cách đo được (cm), phạm vi [2, 400] |
| `sequence` | Field / Unique | INTEGER | Số thứ tự gói tin, kết hợp device_id làm khóa chống trùng lặp |
| `latency_ms` | Field (Metric) | REAL | Độ trễ truyền thông End-to-End từ ESP32 đến Gateway |

---

## 🐳 5. Triển khai Docker (Tùy chọn nâng cao)
Nếu máy bạn có cài đặt Docker Desktop, bạn có thể triển khai hệ thống phân tán với Mosquitto, InfluxDB 2.7 và Grafana chỉ với một lệnh:
```bash
docker compose up -d
```
- InfluxDB UI: `http://localhost:8086` (User: `admin` / Password: `adminpassword123`)
- Grafana UI: `http://localhost:3000` (User: `admin` / Password: `admin`)
- MQTT Mosquitto: `localhost:1883`

---

## 🏆 6. Tác giả & Bản quyền
* **Sinh viên:** Nguyễn Xuân Lộc
* **Mã sinh viên:** B23DCCN492
* **Khoa:** Công nghệ Thông tin - Học viện Công nghệ Bưu chính Viễn thông (PTIT)
