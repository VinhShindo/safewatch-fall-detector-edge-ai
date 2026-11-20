"""Gửi cảnh báo qua Telegram Bot API."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from .config import Settings
from .models import iso, utcnow

log = logging.getLogger("safewatch.telegram")

# httpx ghi cả URL ở mức INFO, mà URL Telegram chứa bot token -> không để lộ token trong log.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@dataclass
class AlertNotification:
    alert_id: str
    message: str
    severity: str
    resident_name: str
    location: str
    event_at_utc: datetime
    device_id: str = ""
    latitude: float | None = None
    longitude: float | None = None
    location_updated_at_utc: datetime | None = None
    heart_rate: int | None = None
    spo2: int | None = None
    battery: int | None = None
    fall_probability: float | None = None
    rssi: int | None = None
    accel_x: float | None = None
    accel_y: float | None = None
    accel_z: float | None = None
    gyro_x: float | None = None
    gyro_y: float | None = None
    gyro_z: float | None = None


_VIETNAM_TZ = timezone(timedelta(hours=7), name="UTC+07:00")


def _vietnam_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_VIETNAM_TZ).strftime("%H:%M:%S %d/%m/%Y")


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.telegram_enabled
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id
        self._client = httpx.AsyncClient(timeout=10)
        self._last_test_at: datetime | None = None
        self._last_status: str | None = None
        self._last_notification_at: datetime | None = None
        self._last_notification_status: str | None = None
        self._last_update_id = 0
        self._messages: deque[dict] = deque(maxlen=100)

    async def close(self) -> None:
        await self._client.aclose()

    def configure(self, enabled: bool, token: str, chat_id: str) -> None:
        self._enabled = enabled
        self._token = token.strip()
        self._chat_id = chat_id.strip()
        self._last_update_id = 0

    # ---- trạng thái ---------------------------------------------------------
    @property
    def _configured_for_read(self) -> bool:
        return self._enabled and bool(self._token)

    @property
    def _configured_for_send(self) -> bool:
        return self._configured_for_read and bool(self._chat_id)

    def status(self) -> dict:
        return {
            "enabled": self._enabled,
            "isConfigured": self._configured_for_send,
            "hasChatId": bool(self._chat_id),
            "lastStatus": self._last_status,
            "lastTestAtUtc": iso(self._last_test_at),
            "lastNotificationStatus": self._last_notification_status,
            "lastNotificationAtUtc": iso(self._last_notification_at),
        }

    # ---- gửi tin --------------------------------------------------------------
    async def notify_alert(self, n: AlertNotification) -> dict:
        severity = {
            "high": "Cao",
            "medium": "Trung bình",
            "low": "Thấp",
        }.get(n.severity.lower(), n.severity)
        text = (
            "🚨 SeSide cảnh báo té ngã\n"
            f"Phát hiện người nhà {n.resident_name} bị té ngã, mức độ {severity}\n"
            f"Nhịp tim: {n.heart_rate if n.heart_rate is not None else '—'} bpm · "
            f"SpO₂: {f'{n.spo2}%' if n.spo2 is not None else '—'} · "
            f"Pin: {f'{n.battery}%' if n.battery is not None else '—'}\n"
            f"Phát hiện lúc: {_vietnam_time(n.event_at_utc)}"
        )
        location = n.location.strip() or "Chưa xác định được địa chỉ"
        if n.latitude is not None and n.longitude is not None:
            text += (
                f"\nVị trí phát hiện: Trường Đại Học Đại Nam, Phú Lương, Hà Nội, Việt Nam"
                f"\nBản đồ: https://maps.google.com/?q={n.latitude:.6f},{n.longitude:.6f}"
            )
        else:
            text += f"\nVị trí phát hiện: Trường Đại Học Đại Nam, Phú Lương, Hà Nội, Việt Nam"
        return await self._send(text, is_test=False)

    async def test(self) -> dict:
        return await self._send("✅ SeSide Admin đã kết nối Telegram thành công.", is_test=True)

    async def _send(self, text: str, is_test: bool) -> dict:
        at = utcnow()
        if not self._configured_for_send:
            message = "Telegram chưa được cấu hình. Thêm TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID vào file .env."
            log.info("Bỏ qua gửi Telegram: enabled=%s, token=%s, chat_id=%s", self._enabled, bool(self._token), bool(self._chat_id))
            self._remember(is_test, at, message)
            return {"success": False, "configured": False, "message": message, "atUtc": iso(at)}

        for attempt in range(1, 4):
            try:
                response = await self._client.post(
                    f"https://api.telegram.org/bot{self._token}/sendMessage",
                    json={"chat_id": self._chat_id, "text": text},
                )
            except httpx.ConnectTimeout:
                if attempt < 3:
                    log.warning(
                        "Telegram ConnectTimeout khi kết nối Bot API (lần %d/3); sẽ thử lại.",
                        attempt,
                    )
                    await asyncio.sleep(0.5 * attempt)
                    continue
                success = False
                message = (
                    "Hết thời gian kết nối Telegram Bot API sau 3 lần thử. "
                    "Kiểm tra mạng ra Internet, DNS hoặc tường lửa của máy chủ."
                )
                log.warning("Telegram ConnectTimeout sau 3 lần thử; chưa kết nối được Bot API.")
                break
            except httpx.HTTPError as exc:
                # Không log exc vì URL của httpx chứa bot token.
                success = False
                message = "Không thể kết nối Telegram Bot API."
                log.warning("Telegram lỗi kết nối: %s", type(exc).__name__)
                break

            try:
                result = response.json()
            except ValueError:
                result = {}
            success = response.is_success and isinstance(result, dict) and result.get("ok") is True
            if success:
                message = "Đã gửi Telegram."
            elif response.is_success:
                message = "Telegram API không xác nhận đã gửi tin nhắn."
            else:
                message = f"Telegram trả về HTTP {response.status_code}."
            log.info("Telegram %s: status=%s, is_test=%s", "thành công" if success else "thất bại", response.status_code, is_test)
            break
        self._remember(is_test, at, message)
        return {"success": success, "configured": True, "message": message, "atUtc": iso(at)}

    def _remember(self, is_test: bool, at: datetime, message: str) -> None:
        if is_test:
            self._last_test_at = at
            self._last_status = message
        else:
            self._last_notification_at = at
            self._last_notification_status = message

    # ---- đọc tin nhắn bot nhận được ---------------------------------------------
    async def get_messages(self) -> list[dict]:
        if self._configured_for_read:
            try:
                params: dict = {"limit": 50, "timeout": 0, "allowed_updates": '["message"]'}
                if self._last_update_id > 0:
                    params["offset"] = self._last_update_id + 1
                response = await self._client.get(f"https://api.telegram.org/bot{self._token}/getUpdates", params=params)
                response.raise_for_status()
                for update in response.json().get("result") or []:
                    update_id = int(update.get("update_id", 0))
                    self._last_update_id = max(self._last_update_id, update_id)
                    message = update.get("message") or {}
                    chat, text = message.get("chat"), message.get("text")
                    if not chat or not text or not str(text).strip():
                        continue
                    sender = message.get("from") or {}
                    sent = message.get("date") or 0
                    self._messages.append({
                        "updateId": update_id,
                        "chatId": chat.get("id"),
                        "from": sender.get("username") or sender.get("first_name"),
                        "text": text,
                        "sentAt": iso(datetime.fromtimestamp(sent, tz=timezone.utc)) if sent > 0 else None,
                    })
            except (httpx.HTTPError, ValueError) as exc:
                self._last_status = "Không thể đọc tin nhắn từ Telegram Bot API."
                log.warning("Telegram getUpdates lỗi: %s", type(exc).__name__)
        return sorted(self._messages, key=lambda m: m["updateId"], reverse=True)[:5]
