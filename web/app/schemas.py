"""Dữ liệu đầu vào của API (request body)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from .models import UtcDateTime


class ApiInput(BaseModel):
    """Body JSON dạng camelCase; tên trường không phân biệt hoa/thường (giống bản .NET cũ)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _case_insensitive_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        lookup: dict[str, str] = {}
        for name, field in cls.model_fields.items():
            alias = field.alias or name
            lookup[alias.lower()] = alias
            lookup[name.lower()] = alias
        return {lookup.get(key.lower(), key) if isinstance(key, str) else key: value for key, value in data.items()}


class DeviceInput(ApiInput):
    id: str | None = None
    user_id: str | None = None
    facility_id: str | None = None
    room_id: str | None = None
    battery: int | None = None
    heart_rate: int | None = None
    status: str | None = None
    firmware_version: str | None = None
    patient_name: str | None = None
    birth_year: int = 0
    contact_name: str | None = None
    contact_relation: str | None = None
    contact_phone: str | None = None
    doctor_name: str | None = None
    doctor_phone: str | None = None


class UserInput(ApiInput):
    full_name: str = ""
    gender: str = ""
    birth_year: int = 0
    facility_id: str = ""
    room_id: str = ""
    device_id: str | None = None
    contact_name: str | None = None
    contact_relation: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    staff_id: str | None = None


class FacilityInput(ApiInput):
    name: str = ""
    address: str = ""
    phone: str = ""


class StaffInput(ApiInput):
    full_name: str = ""
    role: str = ""
    facility_id: str = ""
    phone: str = ""
    email: str = ""
    shift_start: str = "07:00"
    shift_end: str = "19:00"


class TelegramConfigInput(ApiInput):
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


class TelemetryInput(ApiInput):
    device_id: str = ""
    heart_rate: int | None = None
    battery: int | None = None
    fall_status: str | None = None
    fall_probability: float | None = None
    alert_level: str | None = None
    event_time: UtcDateTime | None = None
    connection_status: str | None = None
    rssi: int | None = None
    accel_x: float | None = None
    accel_y: float | None = None
    accel_z: float | None = None
    gyro_x: float | None = None
    gyro_y: float | None = None
    gyro_z: float | None = None


class AlertActionInput(ApiInput):
    note: str | None = None


# ---- Payload ESP32 gửi tới POST /alert (giữ đúng hợp đồng snake_case của firmware) ----
class Esp32Accel(BaseModel):
    ax: float | None = None
    ay: float | None = None
    az: float | None = None


class Esp32Gyro(BaseModel):
    gx: float | None = None
    gy: float | None = None
    gz: float | None = None


class Esp32AlertInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: UtcDateTime | None = None
    type: str = ""
    confidence: float | None = None
    heart_rate: int | None = Field(default=None)
    battery: int | None = None
    rssi: int | None = None
    accel: Esp32Accel | None = None
    gyro: Esp32Gyro | None = None
