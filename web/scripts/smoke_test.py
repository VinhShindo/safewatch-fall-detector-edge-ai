#!/usr/bin/env python3
"""Kiểm tra nhanh SafeWatch đang chạy: trang, API, đăng nhập, CSRF và endpoint ESP32.

Cách dùng:
    python scripts/smoke_test.py [http://localhost:5248] [tai_khoan] [mat_khau]
Mặc định tài khoản admin / ChangeMe!123.
Lưu ý: script tạo 1 thiết bị thử (SW-SMOKE-xxxx) và gửi 1 cảnh báo té ngã tới thiết bị đó.
"""
from __future__ import annotations

import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5248").rstrip("/")
USER = sys.argv[2] if len(sys.argv) > 2 else "admin"
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else "ChangeMe!123"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
failures = 0


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401
        return None


raw_opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(jar))


def call(method: str, path: str, body=None, headers=None, form=None, follow=True, client=None):
    data = None
    hdrs = dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=hdrs)
    try:
        with (client or (opener if follow else raw_opener)).open(request, timeout=15) as response:
            return response.status, response.read().decode("utf-8"), response
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8"), error


def check(name: str, condition: bool, detail: str = "") -> None:
    global failures
    print(f"  [{'OK ' if condition else 'LỖI'}] {name}" + (f" - {detail}" if detail and not condition else ""))
    failures += 0 if condition else 1


def as_json(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return None


print(f"Kiểm tra {BASE}")

# --- công khai ----------------------------------------------------------------------
status, body, _ = call("GET", "/health")
check("GET /health", status == 200 and as_json(body).get("status") == "healthy")

status, _, _ = call("GET", "/api/dashboard/overview", client=urllib.request.build_opener())
check("API chưa đăng nhập bị chặn (401)", status == 401)

status, body, response = call("GET", "/devices", follow=False)
check("Trang chưa đăng nhập chuyển về /account/login", status == 303 and "/account/login" in response.headers.get("Location", ""))

# --- đăng nhập -------------------------------------------------------------------------
status, body, _ = call("POST", "/account/login", form={"username": USER, "password": PASSWORD + "-sai"})
check("Đăng nhập sai mật khẩu bị từ chối", status == 200 and "không đúng" in body)

status, body, response = call("POST", "/account/login", form={"username": USER, "password": PASSWORD}, follow=False)
check("Đăng nhập đúng -> chuyển hướng", status == 303, f"status={status}")

status, body, _ = call("GET", "/")
match = re.search(r'name="csrf-token" content="([^"]+)"', body)
check("Trang Tổng quan tải được, có CSRF token", status == 200 and bool(match))
csrf = {"X-CSRF-Token": match.group(1)} if match else {}

for page in ("/devices", "/devices/create", "/users", "/alerts", "/reports", "/settings"):
    status, body, _ = call("GET", page)
    check(f"Trang {page}", status == 200 and "SafeWatch" in body)

# --- API đọc ---------------------------------------------------------------------------------
for path in ("/api/dashboard/overview", "/api/devices?pageSize=5", "/api/devices/summary", "/api/users?pageSize=5",
             "/api/users/staff", "/api/alerts?pageSize=5", "/api/alerts/summary", "/api/facilities",
             "/api/telegram/status"):
    status, body, _ = call("GET", path)
    check(f"GET {path}", status == 200 and as_json(body) is not None, f"status={status}")

status, body, _ = call("GET", "/api/users/khong-ton-tai")
check("GET /api/users/{không tồn tại} -> 404", status == 404)

# --- ghi dữ liệu -----------------------------------------------------------------------------------
device_id = f"SW-SMOKE-{int(time.time()) % 100000}"
facilities = as_json(call("GET", "/api/facilities")[1]) or []
if not facilities:
    check("Bỏ qua kiểm tra ghi dữ liệu khi chưa có cơ sở", True)
    print()
    print("Không có dữ liệu cơ sở để chạy các kiểm tra ghi dữ liệu.")
    sys.exit(0)
facility = facilities[0]
payload = {
    "id": device_id, "patientName": "Người Thử Nghiệm", "birthYear": 1950, "facilityId": facility["id"],
    "roomId": "room-test", "battery": 90, "contactName": "Người Thân",
    "contactRelation": "Con", "contactPhone": "0900000000", "doctorName": "BS. Thử Nghiệm", "doctorPhone": "0900000001",
}
status, body, _ = call("POST", "/api/devices", body=payload)
check("POST /api/devices không có CSRF bị chặn (403)", status == 403, f"status={status}")
status, body, _ = call("POST", "/api/devices", body=payload, headers=csrf)
check("POST /api/devices tạo thiết bị", status == 201, f"status={status} {body[:150]}")

# --- ESP32 ------------------------------------------------------------------------------------------------
# timestamp của ESP32 chỉ chính xác đến giây; chờ để nó không cũ hơn trạng thái thiết bị vừa tạo.
time.sleep(1.1)
esp32 = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "type": "fall", "confidence": 0.996,
    "heart_rate": 72, "accel": {"ax": -5.338, "ay": 0.928, "az": 8.614}, "gyro": {"gx": -0.009, "gy": 0.0, "gz": -0.003},
}
status, body, _ = call("POST", "/alert", body=esp32, headers={"X-Device-Id": device_id}, client=urllib.request.build_opener())
result = as_json(body) or {}
check("POST /alert (ESP32) tạo cảnh báo té ngã", status == 200 and result.get("alertCreated") is True, f"status={status} {body[:150]}")

status, _, _ = call("POST", "/alert", body={**esp32, "type": "khac"}, headers={"X-Device-Id": device_id}, client=urllib.request.build_opener())
check("POST /alert type sai -> 400", status == 400)

status, _, _ = call("POST", "/alert", body=esp32, headers={"X-Device-Id": "SW-KHONG-CO"}, client=urllib.request.build_opener())
check("POST /alert thiết bị không tồn tại -> 404", status == 404)

status, body, _ = call("POST", "/api/telemetry", body={"deviceId": device_id, "heartRate": 80, "battery": 88},
                       client=urllib.request.build_opener())
check("POST /api/telemetry", status == 200, f"status={status} {body[:150]}")

# --- xử lý cảnh báo -----------------------------------------------------------------------------------------
alerts = as_json(call("GET", "/api/alerts?search=" + urllib.parse.quote(device_id))[1]) or {"items": []}
mine = [a for a in as_json(call("GET", "/api/alerts?pageSize=100")[1])["items"] if a["deviceId"] == device_id]
check("Cảnh báo té ngã xuất hiện trong danh sách", bool(mine))
if mine:
    status, body, _ = call("POST", f"/api/alerts/{mine[0]['id']}/acknowledge", body={"note": "smoke test"}, headers=csrf)
    check("Xác nhận cảnh báo", status == 200 and as_json(body)["status"] == "acknowledged", f"status={status}")
    status, body, _ = call("GET", f"/api/alerts/{mine[0]['id']}")
    check("Chi tiết cảnh báo có nhật ký xử lý", status == 200 and len(as_json(body)["actions"]) >= 2)

# --- thời gian thực (SSE) -----------------------------------------------------------------------------------------
try:
    request = urllib.request.Request(BASE + "/api/events", headers={"Accept": "text/event-stream"})
    with opener.open(request, timeout=5) as stream:
        check("SSE /api/events mở được", "text/event-stream" in stream.headers.get("Content-Type", ""))
except OSError as error:
    check("SSE /api/events mở được", False, str(error))

print()
print("TẤT CẢ ĐẠT" if failures == 0 else f"{failures} kiểm tra thất bại")
sys.exit(1 if failures else 0)
