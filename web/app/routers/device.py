"""Endpoint công khai cho thiết bị ESP32 và kiểm tra sức khỏe (không dùng đăng nhập quản trị)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..deps import get_service, get_settings
from ..config import Settings
from ..models import DomainError, NotFoundError, iso, utcnow
from ..schemas import Esp32AlertInput, TelemetryInput
from ..service import MonitoringService, validate_motion

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "healthy", "timestampUtc": iso(utcnow())}


@router.post("/api/telemetry")
async def ingest_telemetry(request: Request, payload: TelemetryInput, svc: MonitoringService = Depends(get_service)):
    error = request.app.state.telemetry_auth.authenticate(request, payload.device_id)
    if error:
        return JSONResponse({"error": error}, status_code=401)
    try:
        return await svc.ingest_telemetry(payload)
    except NotFoundError:
        return JSONResponse({"error": "Không tìm thấy thiết bị."}, status_code=404)


@router.post("/alert")
async def esp32_alert(
    request: Request,
    payload: Esp32AlertInput,
    svc: MonitoringService = Depends(get_service),
    settings: Settings = Depends(get_settings),
):
    """ESP32 gửi nguyên payload cảnh báo: {timestamp, type, confidence, heart_rate, accel, gyro}."""
    client = request.client.host if request.client else "unknown"
    if not request.app.state.alert_limiter.allow(client):
        return JSONResponse({"error": "Gửi quá nhiều yêu cầu, thử lại sau."}, status_code=429)

    device_id = (request.headers.get("X-Device-Id", "").strip() or settings.esp32_default_device_id).strip()

    if settings.esp32_require_auth:
        error = request.app.state.telemetry_auth.authenticate(request, device_id)
        if error:
            return JSONResponse({"error": error}, status_code=401)

    try:
        _validate(payload)
        event_type = payload.type.strip().lower()
        if event_type not in ("fall", "fall_detected", "fallen"):
            raise DomainError("Trường type hiện chỉ hỗ trợ giá trị 'fall'.")

        confidence = payload.confidence  # đã được _validate đảm bảo khác None
        threshold = min(max(settings.esp32_min_fall_confidence, 0.0), 1.0)
        accel, gyro = payload.accel, payload.gyro
        telemetry = TelemetryInput(
            device_id=device_id,
            event_time=payload.timestamp,
            heart_rate=payload.heart_rate if payload.heart_rate is not None and payload.heart_rate > 0 else None,
            battery=payload.battery,
            rssi=payload.rssi,
            fall_status="FALL" if confidence >= threshold else "NO_FALL",
            fall_probability=confidence,
            alert_level="high" if confidence >= 0.9 else "medium" if confidence >= 0.75 else "low",
            connection_status="good",
            accel_x=accel.ax if accel else None,
            accel_y=accel.ay if accel else None,
            accel_z=accel.az if accel else None,
            gyro_x=gyro.gx if gyro else None,
            gyro_y=gyro.gy if gyro else None,
            gyro_z=gyro.gz if gyro else None,
        )
        result = await svc.ingest_telemetry(telemetry)
    except NotFoundError:
        return JSONResponse(
            {"error": f"Không tìm thấy thiết bị '{device_id}'. Hãy tạo thiết bị hoặc đổi ESP32_DEFAULT_DEVICE_ID."},
            status_code=404,
        )

    return {
        "success": True,
        "deviceId": device_id,
        "type": event_type,
        "alertCreated": len(result["createdAlerts"]) > 0,
        "receivedAtUtc": iso(utcnow()),
        "result": result,
    }


def _validate(payload: Esp32AlertInput) -> None:
    if payload.timestamp is None:
        raise DomainError("Thiếu trường timestamp.")
    if not payload.type.strip():
        raise DomainError("Thiếu trường type.")
    confidence = payload.confidence
    if confidence is None or confidence != confidence or not 0 <= confidence <= 1:  # != để loại NaN
        raise DomainError("Confidence phải là số trong khoảng 0–1.")
    if payload.accel:
        validate_motion(payload.accel.ax, payload.accel.ay, payload.accel.az, 1_000, "accel")
    if payload.gyro:
        validate_motion(payload.gyro.gx, payload.gyro.gy, payload.gyro.gz, 10_000, "gyro")
