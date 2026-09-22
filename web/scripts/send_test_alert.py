#!/usr/bin/env python3
"""Giả lập ESP32 gửi cảnh báo té ngã tới POST /alert.

Cách dùng:
    python scripts/send_test_alert.py [cổng | URL đầy đủ] [device_id]
Ví dụ:
    python scripts/send_test_alert.py                       # http://localhost:5248/alert
    python scripts/send_test_alert.py 5299 SW-0001
    python scripts/send_test_alert.py http://192.168.1.10:5248/alert
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

target = sys.argv[1] if len(sys.argv) > 1 else "5248"
url = target if target.startswith("http") else f"http://localhost:{target}/alert"
headers = {"Content-Type": "application/json"}
if len(sys.argv) > 2:
    headers["X-Device-Id"] = sys.argv[2]

payload = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "type": "fall",
    "confidence": 0.996,
    "heart_rate": 72,
    "accel": {"ax": -5.338, "ay": 0.928, "az": 8.614},
    "gyro": {"gx": -0.009, "gy": 0.0, "gz": -0.003},
}

print(f"Gửi cảnh báo thử tới {url}")
request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        print(response.status, response.read().decode("utf-8"))
except urllib.error.HTTPError as error:
    print(error.code, error.read().decode("utf-8"))
    sys.exit(1)
except OSError as error:
    print("Không kết nối được:", error)
    sys.exit(1)
