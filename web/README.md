# SafeWatch Admin

SafeWatch Admin là hệ thống quản trị đồng hồ AIoT cho người cao tuổi.
Backend dùng **Python + FastAPI**, giao diện dùng **HTML/CSS/JavaScript**, dữ liệu production lưu qua **Supabase Python client + PostgREST**.

## Tính năng

- Dashboard tổng quan thiết bị, người dùng, cảnh báo và cơ sở.
- Quản lý thiết bị và trạng thái online/offline.
- Quản lý người dùng/người được chăm sóc.
- Quản lý cơ sở tại `/facilities`.
- Quản lý đội ngũ nhân viên y tế theo từng cơ sở.
- Trung tâm cảnh báo: té ngã, nhịp tim bất thường, pin yếu, mất kết nối.
- Nhận telemetry và cảnh báo từ ESP32.
- Cập nhật realtime bằng Server-Sent Events.
- Gửi và đọc tin nhắn Telegram.
- Cache snapshot dữ liệu trong suốt vòng đời ứng dụng để giảm số lần truy xuất Supabase.

## Yêu cầu

- Python 3.11 trở lên.
- Một project Supabase đã tạo.
- Các bảng SafeWatch đã được khởi tạo bằng `scripts/supabase_schema.sql`.

## Cài đặt và chạy

Tại thư mục dự án:

```powershell
python -m pip install -r requirements.txt
python run.py
```

Mở trình duyệt tại:

```text
http://localhost:5248
```

Tài khoản mặc định nằm trong `.env`. Hãy đổi mật khẩu trước khi dùng thật.

Tạo password hash mới:

```powershell
python scripts/generate_password_hash.py "MatKhauMoiToiThieu12KyTu"
```

Sau đó cập nhật biến `ADMIN_PASSWORD_HASH` trong `.env` và khởi động lại server.

## Cấu hình `.env`

Không commit `.env` lên git và không đưa secret/token vào tài liệu hoặc chat.

### Máy chủ

```env
HOST=0.0.0.0
PORT=5248
ENABLE_DOCS=false
SECRET_KEY=
```

### Supabase

SafeWatch dùng thư viện `supabase`, không dùng `psycopg` và không cần `DATABASE_URL`.

```env
STORAGE_BACKEND=postgres
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_SECRET_KEY=sb_secret_...
SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
```

- `SUPABASE_URL`: URL project.
- `SUPABASE_PUBLISHABLE_KEY`: dùng cho các tích hợp public nếu cần.
- `SUPABASE_SECRET_KEY`: dùng phía server để đọc/ghi dữ liệu; không được đưa ra frontend.
- `SUPABASE_JWKS_URL`: endpoint JWKS của Supabase.
- `STORAGE_BACKEND=postgres`: dùng Supabase.
- `STORAGE_BACKEND=json`: chỉ dùng cho phát triển cục bộ với thư mục `data/`.

### Tài khoản quản trị

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<pbkdf2-hash>
ADMIN_STAFF_ID=STAFF-001
MAX_FAILED_ATTEMPTS=5
LOCKOUT_MINUTES=15
```

### ESP32 và telemetry

```env
ESP32_DEFAULT_DEVICE_ID=SW-ESP32-TEST-001
ESP32_REQUIRE_AUTH=false
ESP32_MIN_FALL_CONFIDENCE=0.5
ESP32_RATE_LIMIT_PER_MINUTE=60

TELEMETRY_SECURITY_ENABLED=false
TELEMETRY_SHARED_KEY=
TELEMETRY_DEVICE_KEYS=
TELEMETRY_MAX_CLOCK_SKEW_SECONDS=300
TELEMETRY_MAX_PAST_HOURS=24
OFFLINE_AFTER_SECONDS=180
OFFLINE_CHECK_INTERVAL_SECONDS=30
```

Khi triển khai thật, nên bật xác thực thiết bị:

```env
TELEMETRY_SECURITY_ENABLED=true
ESP32_REQUIRE_AUTH=true
TELEMETRY_SHARED_KEY=<shared-key>
```

### Telegram

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=<bot-token>
TELEGRAM_CHAT_ID=<chat-id>
```

Có thể cập nhật cấu hình Telegram tại trang **Cài đặt**. Token không được hiển thị lại trên giao diện.

## Khởi tạo Supabase

### 1. Cài thư viện

```powershell
python -m pip install -r requirements.txt
```

### 2. Tạo bảng

Mở **Supabase Dashboard → SQL Editor**, chạy toàn bộ file:

```text
scripts/supabase_schema.sql
```

Schema hiện tại tạo các bảng:

- `facilities`
- `rooms`
- `staff`
- `residents`
- `devices`
- `assignments`
- `alerts`
- `telemetry_records`

Các bảng nghiệp vụ lưu payload chính trong cột `data jsonb`. Lịch sử telemetry lưu thời điểm trong `event_at` và payload trong `data`.

### 3. Kiểm tra cấu hình

```powershell
python -c "from app.config import Settings; s=Settings.from_env(); print(s.storage_backend, bool(s.supabase_url), bool(s.supabase_secret_key))"
```

### 4. Kiểm tra quyền đọc Supabase

Ứng dụng cần dùng `SUPABASE_SECRET_KEY` phía server. Nếu key không hợp lệ hoặc bảng chưa tạo, API sẽ trả lỗi từ PostgREST.

## Dữ liệu cần nhập

Thứ tự dữ liệu nên là:

```text
facilities -> rooms -> staff -> residents -> devices -> assignments
```

Dữ liệu lịch sử `telemetry_records` và `alerts` có thể được thêm sau khi thiết bị bắt đầu gửi dữ liệu.

### Cơ sở

Được quản lý tại tab **Cơ sở**:

- Tên cơ sở.
- Địa chỉ.
- Số điện thoại.
- Thống kê người dùng, thiết bị, cảnh báo.
- Danh sách đội ngũ y tế.

### Phòng

- Mã phòng.
- Cơ sở thuộc về.
- Tên phòng.
- Tầng.

### Nhân viên y tế

- Họ tên.
- Vai trò.
- Cơ sở công tác.
- Số điện thoại/email.
- Ca bắt đầu và ca kết thúc.

### Người dùng

- Họ tên, giới tính, năm sinh.
- Cơ sở và phòng.
- Nhân viên phụ trách.
- Device ID.
- Thông tin người thân.

### Thiết bị

- Device ID phải trùng firmware ESP32.
- Người dùng, cơ sở, phòng.
- Pin và trạng thái ban đầu.
- Phiên bản firmware.

## ESP32 gửi dữ liệu

### Cảnh báo té ngã: `POST /alert`

Endpoint này công khai cho thiết bị, không yêu cầu cookie đăng nhập.

```http
POST http://<server-ip>:5248/alert
Content-Type: application/json
X-Device-Id: SW-0003
```

Payload đầy đủ:

```json
{
  "timestamp": "2026-09-22T08:35:00Z",
  "type": "fall",
  "confidence": 0.996,
  "heart_rate": 82,
  "battery": 86,
  "rssi": -60,
  "accel": {
    "ax": 0.12,
    "ay": 0.08,
    "az": 9.72
  },
  "gyro": {
    "gx": 0.01,
    "gy": 0.02,
    "gz": 0.01
  }
}
```

`timestamp`, `type` và `confidence` là các trường cần có. `confidence` nằm trong khoảng `0..1`.

Khi nhận `/alert`, server sẽ:

1. Xác định thiết bị qua `X-Device-Id` hoặc `ESP32_DEFAULT_DEVICE_ID`.
2. Chuyển payload thành telemetry nội bộ.
3. Lưu lịch sử telemetry.
4. Cập nhật nhịp tim, pin, RSSI, gia tốc, gyro và trạng thái thiết bị.
5. Tạo cảnh báo té ngã nếu confidence vượt `ESP32_MIN_FALL_CONFIDENCE`.
6. Gửi Telegram nếu được bật.

### Telemetry định kỳ: `POST /api/telemetry`

```http
POST http://<server-ip>:5248/api/telemetry
Content-Type: application/json
```

Payload:

```json
{
  "deviceId": "SW-0003",
  "heartRate": 82,
  "battery": 86,
  "fallStatus": "NoFall",
  "fallProbability": 0.02,
  "alertLevel": "Low",
  "eventTime": "2026-09-22T08:35:00Z",
  "connectionStatus": "Good",
  "rssi": -60,
  "accelX": 0.12,
  "accelY": 0.08,
  "accelZ": 9.72,
  "gyroX": 0.01,
  "gyroY": 0.02,
  "gyroZ": 0.01
}
```

Các giá trị enum hợp lệ:

```text
fallStatus: NoFall | Fall
alertLevel: Low | Medium | High
connectionStatus: Good | Weak | Offline
```

Telemetry quá cũ hơn `TELEMETRY_MAX_PAST_HOURS` sẽ bị từ chối. Nếu timestamp cũ hơn trạng thái thiết bị hiện tại, bản ghi vẫn vào lịch sử nhưng không ghi đè trạng thái mới nhất.

## Gửi dữ liệu thử

### Script gửi cảnh báo cũ

```powershell
python scripts/send_test_alert.py 5248 SW-0003
```

### Script gửi đầy đủ telemetry và alert

```powershell
python scripts/send_sample_data.py SW-0003
```

Chỉ gửi telemetry, không tạo cảnh báo:

```powershell
python scripts/send_sample_data.py SW-0003 --telemetry-only
```

Gửi tới server khác:

```powershell
python scripts/send_sample_data.py SW-0003 http://192.168.1.10:5248
```

Lưu ý: lệnh không có `--telemetry-only` sẽ tạo cảnh báo thật và có thể gửi Telegram.

## Luồng lưu dữ liệu

```text
ESP32
  -> POST /alert hoặc POST /api/telemetry
  -> kiểm tra payload và xác thực thiết bị
  -> lưu telemetry_records
  -> cập nhật devices
  -> tạo alerts nếu phát hiện bất thường
  -> gửi Telegram nền
  -> phát sự kiện SSE cho giao diện
```

### Nơi lưu dữ liệu

| Dữ liệu | Bảng Supabase |
|---|---|
| Cơ sở | `facilities` |
| Phòng | `rooms` |
| Nhân viên | `staff` |
| Người dùng | `residents` |
| Trạng thái thiết bị mới nhất | `devices` |
| Lịch sử gán thiết bị | `assignments` |
| Cảnh báo | `alerts` |
| Lịch sử cảm biến | `telemetry_records` |

## API quản trị chính

Các API `/api/*` yêu cầu đăng nhập và CSRF token cho request thay đổi dữ liệu. Frontend tự gửi cookie và CSRF token.

| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/health` | Kiểm tra server |
| `POST` | `/alert` | ESP32 gửi cảnh báo |
| `POST` | `/api/telemetry` | ESP32 gửi telemetry |
| `GET` | `/api/dashboard/overview` | Dashboard tổng quan |
| `GET/POST` | `/api/devices` | Danh sách/thêm thiết bị |
| `GET` | `/api/devices/{id}` | Chi tiết thiết bị |
| `POST` | `/api/devices/{id}/check` | Gửi yêu cầu kiểm tra thiết bị |
| `GET/POST` | `/api/users` | Danh sách/thêm người dùng |
| `GET` | `/api/users/{id}` | Hồ sơ người dùng |
| `GET/POST` | `/api/users/staff` | Danh sách/thêm nhân viên |
| `GET/POST` | `/api/facilities` | Danh sách/thêm cơ sở |
| `GET` | `/api/alerts` | Danh sách cảnh báo |
| `GET` | `/api/alerts/{id}` | Chi tiết cảnh báo |
| `POST` | `/api/alerts/{id}/{operation}` | `acknowledge`, `urgent`, `close` |
| `GET` | `/api/telegram/status` | Trạng thái Telegram |
| `POST` | `/api/telegram/config` | Cập nhật cấu hình Telegram |
| `POST` | `/api/telegram/test` | Gửi tin kiểm tra Telegram |
| `GET` | `/api/telegram/messages` | Tối đa 5 tin nhắn gần nhất |
| `GET` | `/api/events` | SSE realtime |

Bật tài liệu API bằng:

```env
ENABLE_DOCS=true
```

Sau đó mở `/docs`.

## Script quản trị dữ liệu

| Script | Mục đích |
|---|---|
| `scripts/generate_password_hash.py` | Tạo hash mật khẩu quản trị |
| `scripts/send_test_alert.py` | Gửi nhanh một cảnh báo thử |
| `scripts/send_sample_data.py` | Gửi telemetry và alert mẫu |
| `scripts/smoke_test.py` | Kiểm tra các trang và API |
| `scripts/migrate_json_to_supabase.py` | Chuyển dữ liệu JSON/JSONL cũ sang Supabase |
| `scripts/reset_and_seed_supabase.py` | Xóa toàn bộ bảng và nạp JSON mới sau khi validate |
| `scripts/supabase_schema.sql` | Tạo các bảng SafeWatch |
| `scripts/seed_data.sql` | Seed SQL theo schema `id + data jsonb` |

### Migrate dữ liệu JSON cũ

Kiểm tra trước:

```powershell
python scripts/migrate_json_to_supabase.py --dry-run
```

Thực hiện migrate:

```powershell
python scripts/migrate_json_to_supabase.py
```

### Reset và nạp file JSON mới

File input có dạng:

```json
{
  "facilities": [],
  "rooms": [],
  "staff": [],
  "residents": [],
  "devices": [],
  "assignments": [],
  "alerts": [],
  "telemetry": []
}
```

Luôn dry-run trước:

```powershell
python scripts/reset_and_seed_supabase.py data/real_data.json --dry-run
```

Chỉ khi dữ liệu đúng mới xóa và nạp:

```powershell
python scripts/reset_and_seed_supabase.py data/real_data.json --yes
```

Script không tự sinh dữ liệu người dùng thật. Nếu file sai format, script dừng trước khi xóa.

## Cache và kết nối Supabase

- Ứng dụng tạo một Supabase client dùng chung trong `store.conn` khi khởi động.
- Các lần tải/lọc/tìm kiếm dùng snapshot cache trong `Repository`.
- Cache bị invalidate sau thao tác ghi.
- HTTP session được đóng khi ứng dụng dừng.
- Chỉ chạy một process server; không dùng nhiều worker với dữ liệu file JSON hoặc cache tiến trình.

## Bảo mật và vận hành

- Không commit `.env`, Supabase secret key, Telegram bot token hoặc password.
- Secret key Supabase chỉ dùng server-side, không đưa vào JavaScript/frontend.
- Nếu token Telegram hoặc secret key từng bị chia sẻ, hãy rotate ngay trong Supabase/BotFather.
- Bật xác thực telemetry khi đưa ESP32 vào mạng thật.
- Không dùng `--workers` nếu vẫn chạy mô hình dữ liệu JSON hoặc cần cache trong một process.
- Sao lưu dữ liệu Supabase bằng công cụ backup của Supabase; không chỉ sao lưu thư mục `data/` khi `STORAGE_BACKEND=postgres`.

## Cấu trúc chính

```text
run.py
requirements.txt
.env.example
app/
  main.py              FastAPI app, lifecycle, middleware, background monitor
  config.py            Cấu hình môi trường
  database.py          Supabase client storage
  storage.py           Repository, context cache, JSON fallback
  models.py            Model và enum nghiệp vụ
  schemas.py           Payload API
  service.py           Logic thiết bị, người dùng, cảnh báo, telemetry
  security.py          Login, CSRF, rate limit, telemetry auth
  telegram.py          Telegram notifier
  realtime.py          SSE hub
  routers/
    pages.py           HTML pages
    api.py             API quản trị
    device.py          /health, /alert, /api/telemetry
templates/              Jinja2 templates
static/                 CSS và JavaScript
scripts/                Schema, seed, migration, smoke test, sample sender
data/                   Chỉ dùng khi STORAGE_BACKEND=json
```
