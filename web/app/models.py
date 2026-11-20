"""Thực thể (entities) lưu trong các file JSON.

Định dạng file JSON giữ nguyên như bản cũ (camelCase, enum dạng chữ như "LowBattery",
thời gian UTC kết thúc bằng "Z") nên dữ liệu trong thư mục data/ dùng được ngay.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, field_validator
from pydantic.alias_generators import to_camel


class DomainError(Exception):
    """Lỗi nghiệp vụ -> trả về HTTP 400 kèm thông báo."""


class NotFoundError(Exception):
    """Không tìm thấy đối tượng -> HTTP 404."""


# --------------------------------------------------------------------------- thời gian
_FRACTION = re.compile(r"(\.\d{6})\d+")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: Any) -> datetime | None:
    """Chuẩn hóa mọi dạng ngày giờ về datetime UTC có tzinfo.

    Chuỗi không có múi giờ được coi là UTC (giống bản cũ). Phần thập phân quá 6 chữ số
    (định dạng 7 chữ số của .NET) sẽ được cắt bớt.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("Thời gian rỗng")
        text = _FRACTION.sub(r"\1", text)
        if text[-1] in "Zz":
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    else:
        raise ValueError("Thời gian không hợp lệ")
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def iso(value: datetime | None) -> str | None:
    """datetime -> chuỗi ISO 8601 UTC kết thúc bằng 'Z' (độ rộng cố định nên so sánh chuỗi = so sánh thời gian)."""
    if value is None:
        return None
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


UtcDateTime = Annotated[datetime, BeforeValidator(parse_utc), PlainSerializer(iso, return_type=str)]


def _none_to_empty(value: Any) -> Any:
    return "" if value is None else value


Text = Annotated[str, BeforeValidator(_none_to_empty)]


# --------------------------------------------------------------------------- enums
class _Enum(str, Enum):
    @classmethod
    def _missing_(cls, value: object):  # đọc không phân biệt hoa/thường, "low_battery" == "LowBattery"
        if isinstance(value, str):
            key = value.strip().lower().replace("_", "")
            for member in cls:
                if member.value.lower() == key:
                    return member
        return None


class DeviceStatus(_Enum):
    ACTIVE = "Active"
    LOW_BATTERY = "LowBattery"
    OFFLINE = "Offline"
    ERROR = "Error"


class ConnectionStatus(_Enum):
    GOOD = "Good"
    WEAK = "Weak"
    OFFLINE = "Offline"


class FallStatus(_Enum):
    NO_FALL = "NoFall"
    FALL = "Fall"


class AlertType(_Enum):
    FALL = "Fall"
    HEART_RATE = "HeartRate"
    CONNECTION = "Connection"
    LOW_BATTERY = "LowBattery"


class AlertSeverity(_Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class AlertStatus(_Enum):
    OPEN = "Open"
    ACKNOWLEDGED = "Acknowledged"
    CLOSED = "Closed"


def snake_value(member: Enum) -> str:
    """Enum -> chuỗi API: LowBattery -> 'low_battery', Good -> 'good'."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", member.value).lower()


# --------------------------------------------------------------------------- base
class Entity(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    def to_json(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")


class Contact(Entity):
    name: Text = ""
    relation: Text = ""
    phone: Text = ""
    email: Text = ""


class Facility(Entity):
    id: Text = ""
    name: Text = ""
    address: Text = ""
    manager_staff_id: str | None = None
    phone: Text = ""
    latitude: float | None = None
    longitude: float | None = None


class Room(Entity):
    id: Text = ""
    facility_id: Text = ""
    name: Text = ""
    floor: int = 0


class Staff(Entity):
    id: Text = ""
    full_name: Text = ""
    role: Text = ""
    facility_id: Text = ""
    phone: Text = ""
    email: Text = ""
    shift_start: Text = "07:00"
    shift_end: Text = "19:00"


class PortalAccount(Entity):
    id: Text = ""
    username: Text = ""
    password_hash: Text = ""
    role: Text = "family"
    resident_id: str | None = None
    facility_id: str | None = None
    staff_id: str | None = None
    active: bool = True
    created_at_utc: UtcDateTime = Field(default_factory=utcnow)


class Resident(Entity):
    id: Text = ""
    full_name: Text = ""
    gender: Text = ""
    birth_year: int = 0
    facility_id: Text = ""
    room_id: Text = ""
    staff_id: str | None = None
    device_id: str | None = None
    is_monitored: bool = True
    contact: Contact = Field(default_factory=Contact)

    @field_validator("contact", mode="before")
    @classmethod
    def _contact_default(cls, value: Any) -> Any:
        return {} if value is None else value


class Assignment(Entity):
    id: Text = ""
    device_id: Text = ""
    user_id: Text = ""
    assigned_at_utc: UtcDateTime
    is_active: bool = False


class Telemetry(Entity):
    device_id: Text = ""
    timestamp_utc: UtcDateTime
    data_source: Text = "device"
    heart_rate: int | None = None
    spo2: int | None = None
    battery: int | None = None
    fall_status: FallStatus = FallStatus.NO_FALL
    fall_probability: float | None = None
    alert_level: AlertSeverity | None = None
    connection_status: ConnectionStatus = ConnectionStatus.GOOD
    rssi: int | None = None
    accel_x: float | None = None
    accel_y: float | None = None
    accel_z: float | None = None
    gyro_x: float | None = None
    gyro_y: float | None = None
    gyro_z: float | None = None
    latitude: float | None = None
    longitude: float | None = None


class Device(Entity):
    id: Text = ""
    user_id: str | None = None
    facility_id: Text = ""
    room_id: Text = ""
    status: DeviceStatus = DeviceStatus.ACTIVE
    battery: int = 100
    heart_rate: int | None = None
    spo2: int | None = None
    fall_status: FallStatus = FallStatus.NO_FALL
    fall_probability: float | None = None
    connection_status: ConnectionStatus = ConnectionStatus.GOOD
    rssi: int | None = None
    last_updated_utc: UtcDateTime = Field(default_factory=utcnow)
    last_sync_utc: UtcDateTime = Field(default_factory=utcnow)
    firmware_version: Text = "v1.2.4"
    latitude: float | None = None
    longitude: float | None = None
    location_updated_at_utc: UtcDateTime | None = None

    def apply_telemetry(self, telemetry: Telemetry) -> None:
        if self.id.lower() != telemetry.device_id.lower():
            raise DomainError("Telemetry không khớp thiết bị.")
        if telemetry.timestamp_utc < self.last_updated_utc:
            raise DomainError("Telemetry cũ hơn trạng thái hiện tại của thiết bị.")
        if telemetry.battery is not None:
            self.battery = telemetry.battery
        if telemetry.heart_rate is not None:
            self.heart_rate = telemetry.heart_rate
        if telemetry.spo2 is not None:
            self.spo2 = telemetry.spo2
        if telemetry.latitude is not None and telemetry.longitude is not None:
            self.latitude = telemetry.latitude
            self.longitude = telemetry.longitude
            self.location_updated_at_utc = telemetry.timestamp_utc
        self.fall_status = telemetry.fall_status
        self.fall_probability = telemetry.fall_probability
        self.connection_status = telemetry.connection_status
        self.rssi = telemetry.rssi
        self.last_updated_utc = telemetry.timestamp_utc
        self.last_sync_utc = telemetry.timestamp_utc
        self.recalculate_status()

    def mark_offline(self) -> None:
        self.connection_status = ConnectionStatus.OFFLINE
        self.status = DeviceStatus.OFFLINE

    def recalculate_status(self) -> None:
        if self.connection_status == ConnectionStatus.OFFLINE:
            self.status = DeviceStatus.OFFLINE
        elif self.battery <= 20:
            self.status = DeviceStatus.LOW_BATTERY
        else:
            self.status = DeviceStatus.ACTIVE


class AlertAudit(Entity):
    at_utc: UtcDateTime
    action: Text = ""
    staff_id: str | None = None
    note: str | None = None


class Alert(Entity):
    id: Text = ""
    type: AlertType = AlertType.FALL
    severity: AlertSeverity = AlertSeverity.LOW
    status: AlertStatus = AlertStatus.OPEN
    device_id: Text = ""
    user_id: str | None = None
    facility_id: Text = ""
    room_id: Text = ""
    latitude: float | None = None
    longitude: float | None = None
    message: Text = ""
    event_at_utc: UtcDateTime
    created_at_utc: UtcDateTime
    updated_at_utc: UtcDateTime
    handled_by_staff_id: str | None = None
    is_urgent: bool = False
    notes: str | None = None
    audits: list[AlertAudit] = Field(default_factory=list)

    @field_validator("audits", mode="before")
    @classmethod
    def _audits_default(cls, value: Any) -> Any:
        return [] if value is None else value

    def add_audit(self, action: str, staff_id: str | None, note: str | None, at: datetime) -> None:
        clean = note.strip() if note and note.strip() else None
        self.audits.append(AlertAudit(at_utc=at, action=action, staff_id=staff_id, note=clean))

    def acknowledge(self, staff_id: str | None, note: str | None, at: datetime) -> bool:
        if self.status == AlertStatus.CLOSED:
            raise DomainError("Không thể xác nhận cảnh báo đã đóng.")
        if self.status == AlertStatus.ACKNOWLEDGED:
            return False
        self.status = AlertStatus.ACKNOWLEDGED
        self.handled_by_staff_id = staff_id
        self.updated_at_utc = at
        self.add_audit("acknowledged", staff_id, note, at)
        return True

    def mark_urgent(self, staff_id: str | None, note: str | None, at: datetime) -> bool:
        if self.status == AlertStatus.CLOSED:
            raise DomainError("Không thể đánh dấu cảnh báo đã đóng.")
        if self.is_urgent and self.severity == AlertSeverity.HIGH:
            return False
        self.is_urgent = True
        self.severity = AlertSeverity.HIGH
        self.updated_at_utc = at
        self.add_audit("marked_urgent", staff_id, note, at)
        return True

    def close(self, staff_id: str | None, note: str | None, at: datetime) -> bool:
        if self.status == AlertStatus.CLOSED:
            return False
        self.status = AlertStatus.CLOSED
        self.handled_by_staff_id = staff_id
        if note and note.strip():
            self.notes = note.strip()
        self.updated_at_utc = at
        self.add_audit("closed", staff_id, note, at)
        return True
