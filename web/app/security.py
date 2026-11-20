"""Bảo mật: đăng nhập quản trị, CSRF, xác thực thiết bị, giới hạn tần suất."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import HTTPException, Request

from .config import Settings
from .models import utcnow


# --------------------------------------------------------------------------- mật khẩu
def hash_password(password: str, iterations: int = 210_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
    return f"pbkdf2-sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Kiểm tra mật khẩu với chuỗi băm ``pbkdf2-sha256$lần$salt$hash`` (cùng định dạng bản cũ)."""
    if not password or not encoded_hash:
        return False
    parts = [p for p in encoded_hash.split("$") if p]
    if len(parts) != 4 or parts[0] != "pbkdf2-sha256":
        return False
    try:
        iterations = int(parts[1])
        if iterations < 100_000:
            return False
        salt = base64.b64decode(parts[2], validate=True)
        expected = base64.b64decode(parts[3], validate=True)
    except (ValueError, binascii.Error):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected))
    return hmac.compare_digest(actual, expected)


# --------------------------------------------------------------------------- khóa đăng nhập sai
@dataclass
class _Attempt:
    failures: int
    first_at: datetime
    locked_until: datetime | None


class LoginAttemptLimiter:
    def __init__(self, settings: Settings) -> None:
        self._max = max(3, settings.max_failed_attempts)
        self._lockout = max(1, settings.lockout_minutes)
        self._attempts: dict[str, _Attempt] = {}
        self._lock = threading.Lock()

    def is_locked(self, key: str, now: datetime) -> timedelta | None:
        """Trả về thời gian còn bị khóa, hoặc None nếu không bị khóa."""
        with self._lock:
            state = self._attempts.get(key.lower())
            if not state or state.locked_until is None:
                return None
            if state.locked_until <= now:
                self._attempts.pop(key.lower(), None)
                return None
            return state.locked_until - now

    def register_failure(self, key: str, now: datetime) -> None:
        with self._lock:
            k = key.lower()
            current = self._attempts.get(k)
            if current is None:
                self._attempts[k] = _Attempt(1, now, None)
                return
            reset = current.first_at < now - timedelta(minutes=self._lockout)
            count = 1 if reset else current.failures + 1
            first = now if reset else current.first_at
            locked = now + timedelta(minutes=self._lockout) if count >= self._max else None
            self._attempts[k] = _Attempt(count, first, locked)

    def register_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key.lower(), None)


# --------------------------------------------------------------------------- xác thực telemetry từ thiết bị
class TelemetryAuthenticator:
    """Kiểm tra header X-Device-Key / X-Device-Timestamp / X-Device-Nonce (chỉ khi được bật)."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._used_nonces: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def authenticate(self, request: Request, device_id: str) -> str | None:
        """Trả về None nếu hợp lệ, ngược lại trả về thông báo lỗi."""
        s = self._s
        if not s.telemetry_security_enabled:
            return None
        if not device_id.strip():
            return "Thiếu DeviceId."

        supplied = request.headers.get("X-Device-Key", "").strip()
        timestamp_text = request.headers.get("X-Device-Timestamp", "").strip()
        nonce = request.headers.get("X-Device-Nonce", "").strip()
        if not supplied or not timestamp_text or not nonce:
            return "Thiếu X-Device-Key, X-Device-Timestamp hoặc X-Device-Nonce."
        if not 8 <= len(nonce) <= 128:
            return "Nonce không hợp lệ."
        try:
            request_time = datetime.fromtimestamp(int(timestamp_text), tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return "Timestamp không hợp lệ."

        now = utcnow()
        skew = timedelta(seconds=max(30, s.telemetry_max_clock_skew_seconds))
        if abs(now - request_time) > skew:
            return "Timestamp đã hết hạn."

        expected = s.telemetry_device_keys.get(device_id.strip().upper()) or s.telemetry_shared_key
        if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
            return "Khóa thiết bị không hợp lệ."

        with self._lock:
            for key, seen in list(self._used_nonces.items()):
                if seen < now - skew - skew:
                    del self._used_nonces[key]
            nonce_key = f"{device_id.strip().upper()}:{nonce}"
            if nonce_key in self._used_nonces:
                return "Yêu cầu telemetry đã được gửi trước đó."
            self._used_nonces[nonce_key] = now
        return None


# --------------------------------------------------------------------------- giới hạn tần suất (cửa sổ cố định)
class FixedWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self._limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            start, count = self._hits.get(key, (now, 0))
            if now - start >= self._window:
                start, count = now, 0
            if count >= self._limit:
                self._hits[key] = (start, count)
                return False
            self._hits[key] = (start, count + 1)
            if len(self._hits) > 1000:  # dọn các khóa cũ
                self._hits = {k: v for k, v in self._hits.items() if now - v[0] < self._window}
            return True


# --------------------------------------------------------------------------- phiên đăng nhập + CSRF
class LoginRequired(Exception):
    """Chưa đăng nhập: trang -> chuyển về /account/login, API -> 401."""


def is_local_url(url: str | None) -> bool:
    return bool(url) and url.startswith("/") and not url.startswith("//") and not url.startswith("/\\")


def login_redirect_target(request: Request) -> str:
    path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return f"/account/login?returnUrl={quote(path, safe='')}"


def current_user(request: Request) -> dict:
    """Dependency: bắt buộc đã đăng nhập (dùng cho cả trang và API)."""
    session = request.session
    if not session.get("user"):
        raise LoginRequired()
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session


def admin_user(request: Request) -> dict:
    session = current_user(request)
    if session.get("role", "admin") != "admin":
        raise HTTPException(status_code=403, detail="Chức năng này chỉ dành cho quản trị viên.")
    return session


def portal_user(request: Request, role: str | None = None) -> dict:
    session = current_user(request)
    actual_role = session.get("role", "admin")
    if actual_role not in {"family", "facility"} or (role and actual_role != role):
        raise HTTPException(status_code=403, detail="Tài khoản không có quyền truy cập portal này.")
    account = request.app.state.service.authenticate_portal_account(session.get("user", ""))
    if (
        account is None
        or account.id != session.get("portal_account_id")
        or account.role != actual_role
        or account.resident_id != session.get("resident_id")
        or account.facility_id != session.get("facility_id")
    ):
        session.clear()
        raise LoginRequired()
    return session


def verify_csrf(request: Request) -> None:
    """Dependency cho API thay đổi dữ liệu: header X-CSRF-Token phải khớp token trong phiên."""
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return
    expected = request.session.get("csrf", "")
    supplied = request.headers.get("X-CSRF-Token", "")
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="CSRF token không hợp lệ. Hãy tải lại trang.")
