"""Cấu hình ứng dụng: đọc từ biến môi trường và file .env (nếu có)."""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Nạp file .env đơn giản (KEY=VALUE). Biến môi trường có sẵn luôn được ưu tiên."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _device_keys(raw: str) -> dict[str, str]:
    """TELEMETRY_DEVICE_KEYS: JSON {"SW-0001":"key"} hoặc "SW-0001=key,SW-0002=key2"."""
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        data = json.loads(raw)
        return {str(k).strip().upper(): str(v) for k, v in data.items()}
    result: dict[str, str] = {}
    for part in raw.split(","):
        if "=" in part:
            key, _, value = part.partition("=")
            result[key.strip().upper()] = value.strip()
    return result


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 5248
    data_dir: Path = BASE_DIR / "data"
    require_https: bool = False
    enable_docs: bool = False
    secret_key: str = ""
    storage_backend: str = "json"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwks_url: str = ""
    support_name: str = ""
    support_phone: str = ""
    support_email: str = ""
    support_hours: str = ""

    # Tài khoản quản trị
    admin_username: str = ""
    admin_password_hash: str = ""
    admin_staff_id: str = "STAFF-001"
    max_failed_attempts: int = 5
    lockout_minutes: int = 15

    # Quy tắc giám sát
    min_heart_rate: int = 50
    max_heart_rate: int = 100
    heart_rate_samples_required: int = 3
    heart_rate_window_minutes: int = 5
    telemetry_max_past_hours: int = 24
    offline_after_seconds: int = 180
    offline_check_interval_seconds: int = 30

    # Bảo mật telemetry
    telemetry_security_enabled: bool = False
    telemetry_shared_key: str = ""
    telemetry_max_clock_skew_seconds: int = 300
    telemetry_device_keys: dict[str, str] = field(default_factory=dict)

    # ESP32 POST /alert
    esp32_default_device_id: str = "SW-ESP32-TEST-001"
    esp32_require_auth: bool = False
    esp32_min_fall_confidence: float = 0.5
    esp32_rate_limit_per_minute: int = 60

    # Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @staticmethod
    def from_env() -> "Settings":
        load_dotenv(BASE_DIR / ".env")

        data_dir = Path(_str("DATA_DIR", "data"))
        if not data_dir.is_absolute():
            data_dir = BASE_DIR / data_dir

        settings = Settings(
            host=_str("HOST", "0.0.0.0"),
            port=_int("PORT", 5248),
            data_dir=data_dir,
            require_https=_bool("REQUIRE_HTTPS", False),
            enable_docs=_bool("ENABLE_DOCS", False),
            secret_key=_str("SECRET_KEY"),
            storage_backend=_str("STORAGE_BACKEND", "json").lower(),
            supabase_url=_str("SUPABASE_URL"),
            supabase_publishable_key=_str("SUPABASE_PUBLISHABLE_KEY"),
            supabase_secret_key=_str("SUPABASE_SECRET_KEY"),
            supabase_jwks_url=_str("SUPABASE_JWKS_URL"),
            support_name=_str("SUPPORT_NAME"),
            support_phone=_str("SUPPORT_PHONE"),
            support_email=_str("SUPPORT_EMAIL"),
            support_hours=_str("SUPPORT_HOURS"),
            admin_username=_str("ADMIN_USERNAME"),
            admin_password_hash=_str("ADMIN_PASSWORD_HASH"),
            admin_staff_id=_str("ADMIN_STAFF_ID", "STAFF-001"),
            max_failed_attempts=_int("MAX_FAILED_ATTEMPTS", 5),
            lockout_minutes=_int("LOCKOUT_MINUTES", 15),
            min_heart_rate=_int("MIN_HEART_RATE", 50),
            max_heart_rate=_int("MAX_HEART_RATE", 100),
            heart_rate_samples_required=_int("HEART_RATE_SAMPLES_REQUIRED", 3),
            heart_rate_window_minutes=_int("HEART_RATE_WINDOW_MINUTES", 5),
            telemetry_max_past_hours=_int("TELEMETRY_MAX_PAST_HOURS", 24),
            offline_after_seconds=_int("OFFLINE_AFTER_SECONDS", 180),
            offline_check_interval_seconds=_int("OFFLINE_CHECK_INTERVAL_SECONDS", 30),
            telemetry_security_enabled=_bool("TELEMETRY_SECURITY_ENABLED", False),
            telemetry_shared_key=_str("TELEMETRY_SHARED_KEY"),
            telemetry_max_clock_skew_seconds=_int("TELEMETRY_MAX_CLOCK_SKEW_SECONDS", 300),
            telemetry_device_keys=_device_keys(_str("TELEMETRY_DEVICE_KEYS")),
            esp32_default_device_id=_str("ESP32_DEFAULT_DEVICE_ID", "SW-ESP32-TEST-001"),
            esp32_require_auth=_bool("ESP32_REQUIRE_AUTH", False),
            esp32_min_fall_confidence=_float("ESP32_MIN_FALL_CONFIDENCE", 0.5),
            esp32_rate_limit_per_minute=_int("ESP32_RATE_LIMIT_PER_MINUTE", 60),
            telegram_enabled=_bool("TELEGRAM_ENABLED", False),
            telegram_bot_token=_str("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_str("TELEGRAM_CHAT_ID"),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.admin_username or not self.admin_password_hash:
            raise RuntimeError(
                "Chưa cấu hình ADMIN_USERNAME và ADMIN_PASSWORD_HASH trong file .env. "
                "Xem README.md để tạo mật khẩu quản trị."
            )
        if self.storage_backend not in {"json", "postgres"}:
            raise RuntimeError("STORAGE_BACKEND phải là 'json' hoặc 'postgres'.")
        if self.storage_backend == "postgres" and (not self.supabase_url or not self.supabase_secret_key):
            raise RuntimeError("STORAGE_BACKEND=postgres cần SUPABASE_URL và SUPABASE_SECRET_KEY.")
        if self.telemetry_security_enabled and not self.telemetry_shared_key and not self.telemetry_device_keys:
            raise RuntimeError(
                "TELEMETRY_SECURITY_ENABLED đang bật nhưng chưa có TELEMETRY_SHARED_KEY hoặc TELEMETRY_DEVICE_KEYS."
            )
        if not self.esp32_default_device_id:
            raise RuntimeError("Chưa cấu hình ESP32_DEFAULT_DEVICE_ID.")

    def resolve_secret_key(self) -> str:
        """Khóa ký cookie phiên. Nếu không cấu hình thì tự sinh và lưu vào data/.secret_key."""
        if self.secret_key:
            return self.secret_key
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / ".secret_key"
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        value = secrets.token_urlsafe(48)
        path.write_text(value, encoding="utf-8")
        return value
