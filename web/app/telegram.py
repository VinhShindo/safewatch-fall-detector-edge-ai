"""Gửi cảnh báo qua Telegram Bot API."""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

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


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.telegram_enabled
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id
        self._client = httpx.AsyncClient(timeout=10)
        self._last_test_at: datetime | None = None
        self._last_status: str | None = None
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
        }

    # ---- gửi tin --------------------------------------------------------------
    async def notify_alert(self, n: AlertNotification) -> dict:
        text = (
            f"🚨 SafeWatch {n.severity.upper()}\n"
            f"{n.message}\n"
            f"Người dùng: {n.resident_name}\n"
            f"Vị trí: {n.location}\n"
            f"Thời gian UTC: {n.event_at_utc:%H:%M %d/%m/%Y}"
        )
        return await self._send(text, is_test=False)

    async def test(self) -> dict:
        return await self._send("✅ SafeWatch Admin đã kết nối Telegram thành công.", is_test=True)

    async def _send(self, text: str, is_test: bool) -> dict:
        at = utcnow()
        if not self._configured_for_send:
            message = "Telegram chưa được cấu hình. Thêm TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID vào file .env."
            log.info("Bỏ qua gửi Telegram: enabled=%s, token=%s, chat_id=%s", self._enabled, bool(self._token), bool(self._chat_id))
            self._remember(is_test, at, message)
            return {"success": False, "configured": False, "message": message, "atUtc": iso(at)}

        try:
            response = await self._client.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={"chat_id": self._chat_id, "text": text},
            )
            success = response.is_success
            message = "Đã gửi Telegram." if success else f"Telegram trả về HTTP {response.status_code}."
            log.info("Telegram %s: status=%s, is_test=%s", "thành công" if success else "thất bại", response.status_code, is_test)
        except httpx.HTTPError as exc:
            # Không log exc vì URL của httpx chứa bot token.
            success, message = False, "Không thể kết nối Telegram Bot API."
            log.warning("Telegram lỗi kết nối: %s", type(exc).__name__)
        self._remember(is_test, at, message)
        return {"success": success, "configured": True, "message": message, "atUtc": iso(at)}

    def _remember(self, is_test: bool, at: datetime, message: str) -> None:
        if is_test:
            self._last_test_at = at
            self._last_status = message

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
