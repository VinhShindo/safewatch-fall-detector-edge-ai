"""Gửi dữ liệu mẫu cho một thiết bị SafeWatch.

Mặc định gửi telemetry rồi gửi cảnh báo té ngã cho cùng một thiết bị.
Cảnh báo sẽ được lưu thật vào hệ thống và có thể gửi Telegram.

Ví dụ:
    python scripts/send_sample_data.py SW-0003
    python scripts/send_sample_data.py SW-0003 5248
    python scripts/send_sample_data.py SW-0003 http://192.168.1.10:5248 --telemetry-only
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = body
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error
    except OSError as error:
        raise RuntimeError(f"Không kết nối được tới {url}: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Gửi telemetry và cảnh báo mẫu cho một thiết bị SafeWatch")
    parser.add_argument("device_id", help="Device ID đã tồn tại, ví dụ SW-0003")
    parser.add_argument("server", nargs="?", default="5248", help="Cổng, URL gốc hoặc mặc định 5248")
    parser.add_argument("--telemetry-only", action="store_true", help="Chỉ gửi telemetry, không tạo cảnh báo")
    args = parser.parse_args()

    server = args.server.rstrip("/")
    if not server.startswith("http://") and not server.startswith("https://"):
        server = f"http://localhost:{server}"

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    device_id = args.device_id.strip()
    common = {
        "heartRate": 82,
        "battery": 86,
        "rssi": -60,
        "accelX": 0.12,
        "accelY": 0.08,
        "accelZ": 9.72,
        "gyroX": 0.01,
        "gyroY": 0.02,
        "gyroZ": 0.01,
    }
    telemetry = {
        "deviceId": device_id,
        **common,
        "fallStatus": "NoFall",
        "fallProbability": 0.02,
        "alertLevel": "Low",
        "eventTime": timestamp,
        "connectionStatus": "Good",
    }

    try:
        status, result = post_json(f"{server}/api/telemetry", telemetry)
        print(f"Telemetry: HTTP {status} - {json.dumps(result, ensure_ascii=False)}")

        if args.telemetry_only:
            return 0

        alert = {
            "timestamp": timestamp,
            "type": "fall",
            "confidence": 0.996,
            "heart_rate": common["heartRate"],
            "battery": common["battery"],
            "rssi": common["rssi"],
            "accel": {"ax": common["accelX"], "ay": common["accelY"], "az": common["accelZ"]},
            "gyro": {"gx": common["gyroX"], "gy": common["gyroY"], "gz": common["gyroZ"]},
        }
        status, result = post_json(f"{server}/alert", alert, {"X-Device-Id": device_id})
        print(f"Alert: HTTP {status} - {json.dumps(result, ensure_ascii=False)}")
        return 0
    except RuntimeError as error:
        print(f"Gửi dữ liệu thất bại: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
