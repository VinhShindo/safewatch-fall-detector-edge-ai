"""Logic nghiệp vụ giám sát (tương đương MonitoringApplicationService của bản C#)."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import threading
import uuid
from dataclasses import replace
from pathlib import Path
from datetime import datetime, timedelta
from typing import Iterable, TypeVar

from .config import Settings
from .models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertType,
    Assignment,
    ConnectionStatus,
    Contact,
    Device,
    DeviceStatus,
    DomainError,
    Facility,
    FallStatus,
    NotFoundError,
    PortalAccount,
    Resident,
    Staff,
    Telemetry,
    iso,
    snake_value,
    utcnow,
)
from .realtime import RealtimeHub
from .schemas import DeviceInput, FacilityInput, PortalAccountInput, StaffInput, TelemetryInput, UserInput
from .storage import Context, Repository
from .telegram import AlertNotification, TelegramNotifier
from .security import hash_password

log = logging.getLogger("safewatch.service")
T = TypeVar("T")


# --------------------------------------------------------------------------- tiện ích
def same(a: str | None, b: str | None) -> bool:
    return (a or "").lower() == (b or "").lower()


def contains(text: str, needle: str) -> bool:
    return needle.strip().lower() in text.lower()


def is_all(value: str | None) -> bool:
    return not value or not value.strip() or value.strip().lower() == "all"


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"[: len(prefix) + 9].upper()


def paginate(items: Iterable[T], page: int, page_size: int) -> dict:
    values = list(items)
    size = max(1, min(100, page_size))
    total_pages = max(1, math.ceil(len(values) / size))
    current = max(1, min(total_pages, page))
    start = (current - 1) * size
    return {
        "items": values[start : start + size],
        "total": len(values),
        "page": current,
        "pageSize": size,
        "totalPages": total_pages,
    }


def _find(items: Iterable[T], id_: str | None, attr: str = "id") -> T | None:
    if not id_:
        return None
    return next((item for item in items if same(getattr(item, attr), id_)), None)


def _vector(x: float | None, y: float | None, z: float | None) -> dict | None:
    if x is None and y is None and z is None:
        return None
    return {"x": x, "y": y, "z": z}


# --------------------------------------------------------------------------- chuyển thực thể -> dict trả về cho API
def map_device(device: Device, ctx: Context) -> dict:
    user = _find(ctx.residents, device.user_id)
    facility = _find(ctx.facilities, device.facility_id)
    room = _find(ctx.rooms, device.room_id)
    return {
        "id": device.id,
        "userId": device.user_id,
        "wearerName": user.full_name if user else "Chưa gán người đeo",
        "birthYear": user.birth_year if user else None,
        "facilityId": device.facility_id,
        "facilityName": facility.name if facility else device.facility_id,
        "roomId": device.room_id,
        "roomName": room.name if room else device.room_id,
        "status": snake_value(device.status),
        "battery": device.battery,
        "heartRate": device.heart_rate,
        "spo2": device.spo2,
        "fallStatus": "FALL" if device.fall_status == FallStatus.FALL else "NO_FALL",
        "fallProbability": device.fall_probability,
        "connectionStatus": snake_value(device.connection_status),
        "rssi": device.rssi,
        "lastUpdated": iso(device.last_updated_utc),
        "lastSync": iso(device.last_sync_utc),
        "locationUpdatedAt": iso(device.location_updated_at_utc) if device.location_updated_at_utc else None,
        "firmwareVersion": device.firmware_version,
        "latitude": device.latitude,
        "longitude": device.longitude,
    }


def map_alert(alert: Alert, ctx: Context) -> dict:
    user = _find(ctx.residents, alert.user_id)
    staff = _find(ctx.staff, alert.handled_by_staff_id)
    facility = _find(ctx.facilities, alert.facility_id)
    room = _find(ctx.rooms, alert.room_id)
    return {
        "id": alert.id,
        "type": snake_value(alert.type),
        "severity": snake_value(alert.severity),
        "status": snake_value(alert.status),
        "deviceId": alert.device_id,
        "userId": alert.user_id,
        "userName": user.full_name if user else "Chưa xác định",
        "facilityId": alert.facility_id,
        "facilityName": facility.name if facility else alert.facility_id,
        "roomId": alert.room_id,
        "roomName": room.name if room else alert.room_id,
        "latitude": alert.latitude,
        "longitude": alert.longitude,
        "message": alert.message,
        "eventAt": iso(alert.event_at_utc),
        "updatedAt": iso(alert.updated_at_utc),
        "isUrgent": alert.is_urgent,
        "handledByName": staff.full_name if staff else None,
        "notes": alert.notes,
    }


def map_user(user: Resident, ctx: Context) -> dict:
    facility = _find(ctx.facilities, user.facility_id)
    room = _find(ctx.rooms, user.room_id)
    return {
        "id": user.id,
        "fullName": user.full_name,
        "gender": user.gender,
        "birthYear": user.birth_year,
        "age": max(0, utcnow().year - user.birth_year),
        "facilityId": user.facility_id,
        "facilityName": facility.name if facility else user.facility_id,
        "roomId": user.room_id,
        "roomName": room.name if room else user.room_id,
        "deviceId": user.device_id,
        "monitoringStatus": "active" if user.is_monitored else "inactive",
    }


def map_staff(staff: Staff) -> dict:
    return {
        "id": staff.id,
        "fullName": staff.full_name,
        "role": staff.role,
        "phone": staff.phone,
        "email": staff.email,
        "shiftStart": staff.shift_start,
        "shiftEnd": staff.shift_end,
    }


def map_facility(facility, ctx: Context) -> dict:
    devices = [d for d in ctx.devices if same(d.facility_id, facility.id)]
    staff = _find(ctx.staff, facility.manager_staff_id) or _find(ctx.staff, facility.id, "facility_id")
    return {
        "id": facility.id,
        "name": facility.name,
        "address": facility.address,
        "latitude": facility.latitude,
        "longitude": facility.longitude,
        "phone": facility.phone,
        "totalDevices": len(devices),
        "totalUsers": sum(1 for u in ctx.residents if same(u.facility_id, facility.id)),
        "openAlerts": sum(1 for a in ctx.alerts if same(a.facility_id, facility.id) and a.status != AlertStatus.CLOSED),
        "normalDevices": sum(1 for d in devices if d.status == DeviceStatus.ACTIVE),
        "alertDevices": sum(1 for d in devices if d.status in (DeviceStatus.LOW_BATTERY, DeviceStatus.ERROR)),
        "offlineDevices": sum(1 for d in devices if d.status == DeviceStatus.OFFLINE),
        "onDutyStaff": map_staff(staff) if staff else None,
    }


def map_telemetry(t: Telemetry) -> dict:
    return {
        "deviceId": t.device_id,
        "timestamp": iso(t.timestamp_utc),
        "dataSource": t.data_source,
        "heartRate": t.heart_rate,
        "spo2": t.spo2,
        "battery": t.battery,
        "fallStatus": "FALL" if t.fall_status == FallStatus.FALL else "NO_FALL",
        "fallProbability": t.fall_probability,
        "connectionStatus": snake_value(t.connection_status),
        "rssi": t.rssi,
        "accel": _vector(t.accel_x, t.accel_y, t.accel_z),
        "gyro": _vector(t.gyro_x, t.gyro_y, t.gyro_z),
        "latitude": t.latitude,
        "longitude": t.longitude,
    }


# --------------------------------------------------------------------------- service
class MonitoringService:
    def __init__(
        self,
        repo: Repository,
        hub: RealtimeHub,
        notifier: TelegramNotifier,
        settings: Settings,
    ) -> None:
        self.repo = repo
        self.hub = hub
        self.notifier = notifier
        self.settings = settings
        self._lock = threading.RLock()  # tuần tự hóa mọi thao tác ghi dữ liệu
        self._tasks: set[asyncio.Task] = set()

    # ---- dashboard ------------------------------------------------------------
    def dashboard(self) -> dict:
        ctx = self.repo.load_context()
        now = utcnow()
        devices = [map_device(d, ctx) for d in ctx.devices]
        alerts = sorted((map_alert(a, ctx) for a in ctx.alerts), key=lambda a: a["eventAt"], reverse=True)

        trend = []
        for index in range(7):
            day = (now - timedelta(days=6 - index)).date()
            trend.append({
                "date": iso(datetime.combine(day, datetime.min.time(), tzinfo=now.tzinfo)),
                "label": day.strftime("%d/%m"),
                "value": sum(1 for a in ctx.alerts if a.event_at_utc.date() == day),
            })

        total = max(len(devices), 1)
        status = []
        for value in ("active", "low_battery", "offline", "error"):
            count = sum(1 for d in devices if d["status"] == value)
            if count > 0 or value != "error":
                status.append({"status": value, "count": count, "percentage": round(count * 100 / total, 1)})

        live = sorted(devices, key=lambda d: d["lastUpdated"], reverse=True)[:7]
        return {
            "generatedAt": iso(now),
            "totalDevices": len(devices),
            "activeDevices": sum(1 for d in devices if d["status"] == "active"),
            "openAlerts": sum(1 for a in alerts if a["status"] != "closed"),
            "monitoredUsers": sum(1 for u in ctx.residents if u.is_monitored),
            "fallsToday": sum(1 for a in ctx.alerts if a.type == AlertType.FALL and a.event_at_utc.date() == now.date()),
            "alertsTrend": trend,
            "deviceStatus": status,
            "liveDevices": live,
            "latestAlerts": alerts[:5],
            "facilities": [map_facility(f, ctx) for f in ctx.facilities],
        }

    # ---- thiết bị ---------------------------------------------------------------
    def list_devices(self, search=None, status=None, facility_id=None, battery=None, page=1, page_size=20) -> dict:
        ctx = self.repo.load_context()
        devices = [map_device(d, ctx) for d in ctx.devices]
        if search and search.strip():
            devices = [d for d in devices if contains(f"{d['id']} {d['wearerName']} {d['roomName']}", search)]
        if not is_all(status):
            devices = [d for d in devices if same(d["status"], status)]
        if not is_all(facility_id):
            devices = [d for d in devices if same(d["facilityId"], facility_id)]
        if same(battery, "low"):
            devices = [d for d in devices if d["battery"] <= 20]
        elif same(battery, "normal"):
            devices = [d for d in devices if d["battery"] > 20]

        # mới cập nhật trước, sau đó ưu tiên: mất kết nối -> pin yếu -> bình thường
        devices.sort(key=lambda d: d["lastUpdated"], reverse=True)
        devices.sort(key=lambda d: 2 if d["status"] == "active" else 1 if d["status"] == "low_battery" else 0)
        return paginate(devices, page, page_size)

    def get_device(self, device_id: str) -> dict | None:
        ctx = self.repo.load_context()
        device = _find(ctx.devices, device_id)
        return map_device(device, ctx) if device else None

    def device_summary(self) -> dict:
        devices = self.repo.load_context().devices
        count = lambda s: sum(1 for d in devices if d.status == s)  # noqa: E731
        return {
            "total": len(devices),
            "active": count(DeviceStatus.ACTIVE),
            "lowBattery": count(DeviceStatus.LOW_BATTERY),
            "offline": count(DeviceStatus.OFFLINE),
            "error": count(DeviceStatus.ERROR),
        }

    def create_device(self, inp: DeviceInput) -> dict:
        self._validate_device_input(inp)
        with self._lock:
            ctx = self.repo.load_context()
            device_id = inp.id.strip().upper()  # type: ignore[union-attr]
            if _find(ctx.devices, device_id):
                raise DomainError(f"Thiết bị {device_id} đã tồn tại.")

            facility_id = inp.facility_id.strip().upper()  # type: ignore[union-attr]
            room_id = inp.room_id.strip().upper()  # type: ignore[union-attr]
            self._validate_location(ctx, facility_id, room_id)

            now = utcnow()
            doctor_name = inp.doctor_name.strip()  # type: ignore[union-attr]
            staff = next((s for s in ctx.staff if same(s.full_name, doctor_name)), None)
            if staff is None:
                staff = Staff(
                    id=new_id("STAFF"),
                    full_name=doctor_name,
                    role="Bác sĩ phụ trách",
                    phone=(inp.doctor_phone or "").strip(),
                    facility_id=facility_id,
                )
                ctx.staff.append(staff)
            else:
                staff.facility_id = facility_id
                if inp.doctor_phone and inp.doctor_phone.strip():
                    staff.phone = inp.doctor_phone.strip()

            resident = Resident(
                id=new_id("USR"),
                full_name=inp.patient_name.strip(),  # type: ignore[union-attr]
                birth_year=inp.birth_year,
                facility_id=facility_id,
                room_id=room_id,
                staff_id=staff.id,
                device_id=device_id,
                contact=Contact(
                    name=inp.contact_name.strip(),  # type: ignore[union-attr]
                    relation=(inp.contact_relation or "").strip(),
                    phone=inp.contact_phone.strip(),  # type: ignore[union-attr]
                ),
            )
            device = Device(
                id=device_id,
                user_id=resident.id,
                facility_id=facility_id,
                room_id=room_id,
                battery=100 if inp.battery is None else inp.battery,
                heart_rate=inp.heart_rate,
                spo2=inp.spo2,
                connection_status=self._parse_initial_connection(inp.status),
                firmware_version=(inp.firmware_version or "").strip() or "v1.2.4",
                last_updated_utc=now,
                last_sync_utc=now,
            )
            device.recalculate_status()

            ctx.residents.append(resident)
            ctx.devices.append(device)
            ctx.assignments.append(
                Assignment(id=new_id("ASN"), device_id=device.id, user_id=resident.id, assigned_at_utc=now, is_active=True)
            )
            self.repo.save_residents(ctx.residents)
            self.repo.save_devices(ctx.devices)
            self.repo.save_assignments(ctx.assignments)
            self.repo.save_staff(ctx.staff)
            return map_device(device, ctx)

    async def request_device_check(self, device_id: str) -> dict | None:
        device = self.get_device(device_id)
        if device is None:
            return None
        await self.hub.publish(
            "DeviceCheckRequested",
            {"deviceId": device["id"], "requestedAt": iso(utcnow())},
            device["facilityId"],
        )
        return device

    # ---- cảnh báo -----------------------------------------------------------------
    def list_alerts(self, search=None, status=None, severity=None, type_=None, facility_id=None, page=1, page_size=20) -> dict:
        ctx = self.repo.load_context()
        alerts = [map_alert(a, ctx) for a in ctx.alerts]
        if search and search.strip():
            alerts = [a for a in alerts if contains(f"{a['id']} {a['userName']} {a['message']}", search)]
        if not is_all(status):
            alerts = [a for a in alerts if same(a["status"], status)]
        if not is_all(severity):
            alerts = [a for a in alerts if same(a["severity"], severity)]
        if not is_all(type_):
            alerts = [a for a in alerts if same(a["type"], type_)]
        if not is_all(facility_id):
            alerts = [a for a in alerts if same(a["facilityId"], facility_id)]

        # đang mở trước -> khẩn cấp trước -> mới nhất trước
        alerts.sort(key=lambda a: a["eventAt"], reverse=True)
        alerts.sort(key=lambda a: not a["isUrgent"])
        alerts.sort(key=lambda a: 0 if a["status"] == "open" else 1)
        return paginate(alerts, page, page_size)

    def alert_summary(self) -> dict:
        alerts = self.repo.load_context().alerts
        return {
            "total": len(alerts),
            "open": sum(1 for a in alerts if a.status == AlertStatus.OPEN),
            "high": sum(1 for a in alerts if a.severity == AlertSeverity.HIGH),
            "acknowledged": sum(1 for a in alerts if a.status == AlertStatus.ACKNOWLEDGED),
            "closed": sum(1 for a in alerts if a.status == AlertStatus.CLOSED),
        }

    def get_alert(self, alert_id: str) -> dict | None:
        ctx = self.repo.load_context()
        alert = _find(ctx.alerts, alert_id)
        if alert is None:
            return None
        device = _find(ctx.devices, alert.device_id)
        user = _find(ctx.residents, alert.user_id)
        return {
            "alert": map_alert(alert, ctx),
            "device": map_device(device, ctx) if device else None,
            "user": map_user(user, ctx) if user else None,
            "actions": [self._map_audit(a, ctx) for a in sorted(alert.audits, key=lambda a: a.at_utc)],
        }

    @staticmethod
    def _map_audit(audit, ctx: Context) -> dict:
        actor = _find(ctx.staff, audit.staff_id)
        return {
            "at": iso(audit.at_utc),
            "action": audit.action,
            "note": audit.note,
            "actorName": actor.full_name if actor else "Hệ thống",
        }

    async def act_on_alert(self, alert_id: str, operation: str, note: str | None, actor_staff_id: str | None) -> dict | None:
        with self._lock:
            ctx = self.repo.load_context()
            alert = _find(ctx.alerts, alert_id)
            if alert is None:
                return None
            now = utcnow()
            action = operation.strip().lower()
            if action == "acknowledge":
                changed = alert.acknowledge(actor_staff_id, note, now)
            elif action == "urgent":
                changed = alert.mark_urgent(actor_staff_id, note, now)
            elif action == "close":
                changed = alert.close(actor_staff_id, note, now)
            else:
                raise DomainError("Thao tác cảnh báo không hợp lệ.")
            if changed:
                self.repo.save_alerts(ctx.alerts)
            result = map_alert(alert, ctx)

        if changed:
            await self.hub.publish("AlertUpdated", result, result["facilityId"])
        return result

    # ---- người dùng (bệnh nhân) -----------------------------------------------------
    def list_users(self, search=None, facility_id=None, status=None, page=1, page_size=20) -> dict:
        ctx = self.repo.load_context()
        users = [map_user(u, ctx) for u in ctx.residents]
        if search and search.strip():
            users = [u for u in users if contains(f"{u['fullName']} {u['id']} {u['deviceId'] or ''}", search)]
        if not is_all(facility_id):
            users = [u for u in users if same(u["facilityId"], facility_id)]
        if not is_all(status):
            users = [u for u in users if same(u["monitoringStatus"], status)]
        users.sort(key=lambda u: u["fullName"].lower())
        return paginate(users, page, page_size)

    def list_staff(self, facility_id: str | None = None) -> list[dict]:
        ctx = self.repo.load_context()
        staff = ctx.staff if not facility_id or is_all(facility_id) else [s for s in ctx.staff if same(s.facility_id, facility_id)]
        return [map_staff(s) for s in sorted(staff, key=lambda s: s.full_name.lower())]

    def create_staff(self, inp: StaffInput) -> dict:
        name, facility_id = inp.full_name.strip(), inp.facility_id.strip().upper()
        if not name or not facility_id:
            raise DomainError("Họ tên và cơ sở của nhân viên là bắt buộc.")
        with self._lock:
            ctx = self.repo.load_context()
            if not _find(ctx.facilities, facility_id):
                raise DomainError("Cơ sở không tồn tại.")
            staff = Staff(id=new_id("STAFF"), full_name=name, role=inp.role.strip(), facility_id=facility_id,
                          phone=inp.phone.strip(), email=inp.email.strip(), shift_start=inp.shift_start.strip(), shift_end=inp.shift_end.strip())
            ctx.staff.append(staff)
            self.repo.save_staff(ctx.staff)
            return map_staff(staff)

    def list_facilities(self) -> list[dict]:
        ctx = self.repo.load_context()
        return [map_facility(f, ctx) for f in ctx.facilities]

    def create_facility(self, inp: FacilityInput) -> dict:
        name = inp.name.strip()
        address = inp.address.strip()
        phone = inp.phone.strip()
        if not name:
            raise DomainError("Tên cơ sở là bắt buộc.")
        if (inp.latitude is None) != (inp.longitude is None):
            raise DomainError("Vĩ độ và kinh độ phải được nhập cùng nhau.")
        with self._lock:
            ctx = self.repo.load_context()
            if any(same(f.name, name) for f in ctx.facilities):
                raise DomainError("Tên cơ sở đã tồn tại.")
            facility = Facility(id=new_id("FAC"), name=name, address=address, phone=phone)
            facility.latitude = inp.latitude
            facility.longitude = inp.longitude
            ctx.facilities.append(facility)
            self.repo.save_facilities(ctx.facilities)
            return map_facility(facility, ctx)

    def update_facility_location(self, facility_id: str, latitude: float, longitude: float) -> dict | None:
        with self._lock:
            ctx = self.repo.load_context()
            facility = _find(ctx.facilities, facility_id)
            if facility is None:
                return None
            facility.latitude = latitude
            facility.longitude = longitude
            self.repo.save_facilities(ctx.facilities)
            return map_facility(facility, ctx)

    async def update_device_location(self, device_id: str, latitude: float, longitude: float) -> dict | None:
        with self._lock:
            ctx = self.repo.load_context()
            device = _find(ctx.devices, device_id)
            if device is None:
                return None
            device.latitude = latitude
            device.longitude = longitude
            device.location_updated_at_utc = utcnow()
            self.repo.save_devices(ctx.devices)
            result = map_device(device, ctx)

        await self.hub.publish("DeviceUpdated", result, result["facilityId"])
        return result

    def facility_options(self) -> list[dict]:
        """Danh sách cơ sở gọn (id, name) để dựng ô chọn trong trang HTML."""
        return [{"id": f.id, "name": f.name} for f in self.repo.load_context().facilities]

    def get_user(self, user_id: str) -> dict | None:
        ctx = self.repo.load_context()
        user = _find(ctx.residents, user_id)
        return self._build_user_detail(user, ctx) if user else None

    def authenticate_portal_account(self, username: str) -> PortalAccount | None:
        account = _find(self.repo.load_context().portal_accounts, username, "username")
        return account if account and account.active else None

    def portal_resident_options(self) -> list[dict]:
        ctx = self.repo.load_context()
        return [map_user(user, ctx) for user in sorted(ctx.residents, key=lambda item: item.full_name.casefold())]

    def list_portal_accounts(self) -> list[dict]:
        ctx = self.repo.load_context()
        result = []
        for account in ctx.portal_accounts:
            resident = _find(ctx.residents, account.resident_id)
            facility = _find(ctx.facilities, account.facility_id)
            staff = _find(ctx.staff, account.staff_id)
            result.append({
                "id": account.id,
                "username": account.username,
                "role": account.role,
                "active": account.active,
                "residentId": account.resident_id,
                "residentName": resident.full_name if resident else None,
                "facilityId": account.facility_id,
                "facilityName": facility.name if facility else None,
                "staffId": account.staff_id,
                "staffName": staff.full_name if staff else None,
            })
        return sorted(result, key=lambda item: item["username"].casefold())

    def create_portal_account(self, inp: PortalAccountInput) -> dict:
        username = inp.username.strip().casefold()
        role = inp.role.strip().casefold()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,39}", username):
            raise DomainError("Tên đăng nhập cần 3–40 ký tự, chỉ gồm chữ thường, số, dấu chấm, gạch ngang hoặc gạch dưới.")
        if len(inp.password) < 12:
            raise DomainError("Mật khẩu portal phải có ít nhất 12 ký tự.")
        if role not in {"family", "facility"}:
            raise DomainError("Loại tài khoản phải là family hoặc facility.")
        if username == self.settings.admin_username.casefold():
            raise DomainError("Tên đăng nhập này đã được dành cho quản trị viên.")

        with self._lock:
            ctx = self.repo.load_context()
            if any(account.username.casefold() == username for account in ctx.portal_accounts):
                raise DomainError("Tên đăng nhập đã tồn tại.")

            resident_id = inp.resident_id.strip().upper() if inp.resident_id and inp.resident_id.strip() else None
            facility_id = inp.facility_id.strip().upper() if inp.facility_id and inp.facility_id.strip() else None
            staff_id = inp.staff_id.strip().upper() if inp.staff_id and inp.staff_id.strip() else None
            if role == "family":
                resident = _find(ctx.residents, resident_id)
                if resident is None:
                    raise DomainError("Tài khoản người nhà phải được gắn với một bệnh nhân hợp lệ.")
                facility_id = None
                staff_id = None
            else:
                facility = _find(ctx.facilities, facility_id)
                if facility is None:
                    raise DomainError("Tài khoản cơ sở phải được gắn với một cơ sở hợp lệ.")
                if staff_id:
                    staff = _find(ctx.staff, staff_id)
                    if staff is None or not same(staff.facility_id, facility.id):
                        raise DomainError("Nhân viên không thuộc cơ sở đã chọn.")
                resident_id = None

            account = PortalAccount(
                id=new_id("PORTAL"),
                username=username,
                password_hash=hash_password(inp.password),
                role=role,
                resident_id=resident_id,
                facility_id=facility_id,
                staff_id=staff_id,
            )
            ctx.portal_accounts.append(account)
            self.repo.save_portal_accounts(ctx.portal_accounts)
        return next(item for item in self.list_portal_accounts() if item["id"] == account.id)

    def set_portal_account_active(self, account_id: str, active: bool) -> dict | None:
        with self._lock:
            ctx = self.repo.load_context()
            account = _find(ctx.portal_accounts, account_id)
            if account is None:
                return None
            account.active = active
            self.repo.save_portal_accounts(ctx.portal_accounts)
        return next(item for item in self.list_portal_accounts() if item["id"] == account.id)

    def family_portal_data(self, resident_id: str) -> dict | None:
        ctx = self.repo.load_context()
        resident = _find(ctx.residents, resident_id)
        if resident is None:
            return None
        detail = self._build_user_detail(resident, ctx)
        detail.pop("responsibleStaff", None)
        return detail

    def facility_portal_data(self, facility_id: str) -> dict | None:
        ctx = self.repo.load_context()
        facility = _find(ctx.facilities, facility_id)
        if facility is None:
            return None
        users = [u for u in ctx.residents if same(u.facility_id, facility_id)]
        devices = [d for d in ctx.devices if same(d.facility_id, facility_id)]
        alerts = sorted(
            (map_alert(a, ctx) for a in ctx.alerts if same(a.facility_id, facility_id)),
            key=lambda item: item["eventAt"], reverse=True,
        )
        return {
            "facility": map_facility(facility, ctx),
            "users": [map_user(user, ctx) for user in users],
            "devices": [map_device(device, ctx) for device in devices],
            "alerts": alerts[:20],
            "metrics": {
                "users": len(users),
                "devices": len(devices),
                "openAlerts": sum(1 for alert in alerts if alert["status"] != "closed"),
                "fallAlerts": sum(1 for alert in alerts if alert["type"] == "fall"),
            },
        }

    def create_user(self, inp: UserInput) -> dict:
        self._validate_user_input(inp)
        with self._lock:
            ctx = self.repo.load_context()
            facility_id = inp.facility_id.strip().upper()
            room_id = inp.room_id.strip().upper()
            self._validate_location(ctx, facility_id, room_id)
            staff_id = inp.staff_id.strip().upper() if inp.staff_id and inp.staff_id.strip() else None
            if staff_id and not _find(ctx.staff, staff_id):
                raise DomainError("Người phụ trách không tồn tại.")

            now = utcnow()
            device_id = inp.device_id.strip().upper() if inp.device_id and inp.device_id.strip() else None
            resident = Resident(
                id=new_id("USR"),
                full_name=inp.full_name.strip(),
                gender=inp.gender.strip(),
                birth_year=inp.birth_year,
                facility_id=facility_id,
                room_id=room_id,
                staff_id=staff_id,
                device_id=device_id,
                contact=Contact(
                    name=(inp.contact_name or "").strip(),
                    relation=(inp.contact_relation or "").strip(),
                    phone=(inp.contact_phone or "").strip(),
                    email=(inp.contact_email or "").strip(),
                ),
            )

            if device_id:
                for previous in ctx.residents:
                    if same(previous.device_id, device_id):
                        previous.device_id = None
                for assignment in ctx.assignments:
                    if same(assignment.device_id, device_id) and assignment.is_active:
                        assignment.is_active = False

                device = _find(ctx.devices, device_id)
                if device is None:
                    device = Device(
                        id=device_id,
                        facility_id=facility_id,
                        room_id=room_id,
                        battery=100,
                        connection_status=ConnectionStatus.GOOD,
                        last_updated_utc=now,
                        last_sync_utc=now,
                    )
                    device.recalculate_status()
                    ctx.devices.append(device)
                device.user_id = resident.id
                device.facility_id = facility_id
                device.room_id = room_id
                ctx.assignments.append(
                    Assignment(id=new_id("ASN"), device_id=device.id, user_id=resident.id, assigned_at_utc=now, is_active=True)
                )

            ctx.residents.append(resident)
            self.repo.save_residents(ctx.residents)
            self.repo.save_devices(ctx.devices)
            self.repo.save_assignments(ctx.assignments)

        return self._build_user_detail(resident, ctx)

    # ---- telemetry --------------------------------------------------------------------
    async def ingest_telemetry(self, inp: TelemetryInput) -> dict:
        self._validate_telemetry(inp)
        applied = False
        message: str | None = None
        created: list[Alert] = []

        with self._lock:
            ctx = self.repo.load_context()
            device = _find(ctx.devices, inp.device_id)
            if device is None:
                raise NotFoundError("Không tìm thấy thiết bị.")
            facility = _find(ctx.facilities, device.facility_id)
            location_label = (
                facility.address.strip()
                if facility and facility.address.strip()
                else "U07–L16, Khu đô thị mới Dương Nội, Yên Nghĩa, Hà Nội"
            )

            now = utcnow()
            event_time = inp.event_time or now
            if event_time < now - timedelta(hours=max(1, self.settings.telemetry_max_past_hours)):
                raise DomainError("Telemetry quá cũ và đã bị từ chối.")
            latitude = inp.latitude if inp.latitude is not None else device.latitude
            longitude = inp.longitude if inp.longitude is not None else device.longitude
            location_updated_at = (
                event_time
                if inp.latitude is not None and inp.longitude is not None
                else device.location_updated_at_utc
            )

            telemetry = Telemetry(
                device_id=device.id,
                timestamp_utc=event_time,
                heart_rate=inp.heart_rate,
                spo2=inp.spo2,
                battery=inp.battery,
                fall_status=self._parse_fall(inp.fall_status, device.fall_status),
                fall_probability=inp.fall_probability,
                alert_level=self._parse_severity(inp.alert_level),
                connection_status=self._parse_connection(inp.connection_status, device.connection_status),
                rssi=inp.rssi,
                accel_x=inp.accel_x,
                accel_y=inp.accel_y,
                accel_z=inp.accel_z,
                gyro_x=inp.gyro_x,
                gyro_y=inp.gyro_y,
                gyro_z=inp.gyro_z,
                latitude=latitude,
                longitude=longitude,
            )
            self.repo.append_telemetry(telemetry)

            if event_time < device.last_updated_utc:
                message = "Telemetry đã được lưu vào lịch sử nhưng không ghi đè trạng thái mới hơn."
                if telemetry.fall_status == FallStatus.FALL:
                    created = self._create_alerts_for_telemetry(
                        device,
                        telemetry,
                        ctx,
                        include_non_fall=False,
                    )
                    if created:
                        self.repo.save_alerts(ctx.alerts)
            else:
                device.apply_telemetry(telemetry)
                if inp.latitude is None or inp.longitude is None:
                    device.location_updated_at_utc = location_updated_at
                self.repo.save_devices(ctx.devices)
                created = self._create_alerts_for_telemetry(device, telemetry, ctx)
                if created:
                    self.repo.save_alerts(ctx.alerts)
                applied = True

            device_dto = map_device(device, ctx)
            alert_dtos = [map_alert(a, ctx) for a in created]
            repeated_fall_alert = None
            if telemetry.fall_status == FallStatus.FALL:
                has_new_fall_alert = any(alert.type == AlertType.FALL for alert in created)
                if not has_new_fall_alert:
                    repeated_fall_alert = next(
                        (
                            alert
                            for alert in ctx.alerts
                            if same(alert.device_id, device.id)
                            and alert.type == AlertType.FALL
                            and alert.status != AlertStatus.CLOSED
                            and abs((alert.event_at_utc - event_time).total_seconds()) > 60
                        ),
                        None,
                    )

        if applied:
            await self.hub.publish("TelemetryUpdated", map_telemetry(telemetry), device_dto["facilityId"])
            await self.hub.publish("DeviceUpdated", device_dto, device_dto["facilityId"])
        for alert, dto in zip(created, alert_dtos):
            await self.hub.publish("AlertCreated", dto, dto["facilityId"])
            self._spawn(
                self.notifier.notify_alert(
                    AlertNotification(
                        alert_id=alert.id,
                        message=alert.message,
                        severity=dto["severity"],
                        resident_name=dto["userName"],
                        location=location_label,
                        event_at_utc=alert.event_at_utc,
                        device_id=telemetry.device_id,
                        latitude=telemetry.latitude,
                        longitude=telemetry.longitude,
                        location_updated_at_utc=location_updated_at,
                        heart_rate=telemetry.heart_rate,
                        spo2=telemetry.spo2,
                        battery=telemetry.battery,
                        fall_probability=telemetry.fall_probability,
                        rssi=telemetry.rssi,
                        accel_x=telemetry.accel_x,
                        accel_y=telemetry.accel_y,
                        accel_z=telemetry.accel_z,
                        gyro_x=telemetry.gyro_x,
                        gyro_y=telemetry.gyro_y,
                        gyro_z=telemetry.gyro_z,
                    )
                )
            )
        if repeated_fall_alert is not None:
            self._spawn(
                self.notifier.notify_alert(
                    AlertNotification(
                        alert_id=repeated_fall_alert.id,
                        message="Có lần té ngã mới được phát hiện; cảnh báo trước đó vẫn đang mở.",
                        severity=snake_value(telemetry.alert_level or AlertSeverity.HIGH),
                        resident_name=device_dto["wearerName"],
                        location=location_label,
                        event_at_utc=event_time,
                        device_id=telemetry.device_id,
                        latitude=telemetry.latitude,
                        longitude=telemetry.longitude,
                        location_updated_at_utc=location_updated_at,
                        heart_rate=telemetry.heart_rate,
                        spo2=telemetry.spo2,
                        battery=telemetry.battery,
                        fall_probability=telemetry.fall_probability,
                        rssi=telemetry.rssi,
                        accel_x=telemetry.accel_x,
                        accel_y=telemetry.accel_y,
                        accel_z=telemetry.accel_z,
                        gyro_x=telemetry.gyro_x,
                        gyro_y=telemetry.gyro_y,
                        gyro_z=telemetry.gyro_z,
                    )
                )
            )

        return {
            "telemetry": map_telemetry(telemetry),
            "device": device_dto,
            "createdAlerts": alert_dtos,
            "appliedToCurrentState": applied,
            "message": message,
        }

    async def mark_stale_devices_offline(self) -> int:
        updates: list[tuple[dict, dict]] = []
        with self._lock:
            ctx = self.repo.load_context()
            now = utcnow()
            cutoff = now - timedelta(seconds=max(30, self.settings.offline_after_seconds))
            for device in ctx.devices:
                if device.connection_status != ConnectionStatus.OFFLINE and device.last_updated_utc < cutoff:
                    device.mark_offline()
                    alert = self._new_alert(device, AlertType.CONNECTION, AlertSeverity.MEDIUM, "Mất kết nối thiết bị", now, ctx)
                    updates.append((map_device(device, ctx), map_alert(alert, ctx)))
            if updates:
                self.repo.save_devices(ctx.devices)
                self.repo.save_alerts(ctx.alerts)

        for device_dto, alert_dto in updates:
            await self.hub.publish("DeviceUpdated", device_dto, device_dto["facilityId"])
            await self.hub.publish("AlertCreated", alert_dto, alert_dto["facilityId"])
        return len(updates)

    # ---- dữ liệu mô phỏng (giữ tương thích trang hồ sơ người dùng) ------------------
    def simulated_series(self, device_id: str) -> list[dict]:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", device_id):
            raise DomainError("Mã thiết bị không hợp lệ.")
        root = getattr(self.repo.store, "root", None)
        if root is not None:
            path = root / "simulated" / f"{device_id}.json"
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8-sig") or "[]")
                if isinstance(data, list) and data:
                    return data

        # không có file mô phỏng -> dùng telemetry 24 giờ gần nhất của thiết bị
        since = utcnow() - timedelta(hours=24)
        items = sorted(
            (t for t in self.repo.telemetry_since(since) if same(t.device_id, device_id)),
            key=lambda t: t.timestamp_utc,
        )
        return [
            {
                "timestamp": iso(t.timestamp_utc),
                "deviceId": t.device_id,
                "heart_rate": t.heart_rate,
                "battery": t.battery,
                "fall_status": "FALL" if t.fall_status == FallStatus.FALL else "NO_FALL",
                "fall_probability": t.fall_probability,
                "accel": {"ax": t.accel_x, "ay": t.accel_y, "az": t.accel_z},
                "gyro": {"gx": t.gyro_x, "gy": t.gyro_y, "gz": t.gyro_z},
                "latitude": t.latitude,
                "longitude": t.longitude,
            }
            for t in items
        ]

    # ---- Telegram -------------------------------------------------------------------
    def telegram_status(self) -> dict:
        return self.notifier.status()

    async def test_telegram(self) -> dict:
        return await self.notifier.test()

    async def telegram_messages(self) -> list[dict]:
        return await self.notifier.get_messages()

    def configure_telegram(self, enabled: bool, token: str, chat_id: str) -> dict:
        self.notifier.configure(enabled, token, chat_id)
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.is_file():
            lines = env_path.read_text(encoding="utf-8").splitlines()
            values = {"TELEGRAM_ENABLED": "true" if enabled else "false", "TELEGRAM_BOT_TOKEN": token.strip(), "TELEGRAM_CHAT_ID": chat_id.strip()}
            updated = []
            seen = set()
            for line in lines:
                key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
                if key in values:
                    updated.append(f"{key}={values[key]}")
                    seen.add(key)
                else:
                    updated.append(line)
            updated.extend(f"{key}={value}" for key, value in values.items() if key not in seen)
            env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
        return self.notifier.status()

    def support_config(self) -> dict:
        return {
            "name": self.settings.support_name,
            "phone": self.settings.support_phone,
            "email": self.settings.support_email,
            "hours": self.settings.support_hours,
        }

    def configure_support(self, name: str, phone: str, email: str, hours: str) -> dict:
        self.settings = replace(
            self.settings,
            support_name=name.strip(),
            support_phone=phone.strip(),
            support_email=email.strip(),
            support_hours=hours.strip(),
        )
        env_path = Path(__file__).resolve().parent.parent / ".env"
        values = {
            "SUPPORT_NAME": self.settings.support_name,
            "SUPPORT_PHONE": self.settings.support_phone,
            "SUPPORT_EMAIL": self.settings.support_email,
            "SUPPORT_HOURS": self.settings.support_hours,
        }
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []
        updated = []
        seen = set()
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
            if key in values:
                updated.append(f"{key}={values[key]}")
                seen.add(key)
            else:
                updated.append(line)
        updated.extend(f"{key}={value}" for key, value in values.items() if key not in seen)
        env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
        return self.support_config()

    # ---- nội bộ ----------------------------------------------------------------------
    def _spawn(self, coro) -> None:
        async def runner() -> None:
            try:
                await coro
            except Exception:  # noqa: BLE001 - thông báo lỗi không được làm hỏng luồng chính
                log.exception("Gửi thông báo thất bại")

        task = asyncio.get_running_loop().create_task(runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _create_alerts_for_telemetry(
        self,
        device: Device,
        telemetry: Telemetry,
        ctx: Context,
        include_non_fall: bool = True,
    ) -> list[Alert]:
        specs: list[tuple[AlertType, AlertSeverity, str]] = []
        if telemetry.fall_status == FallStatus.FALL:
            specs.append((AlertType.FALL, telemetry.alert_level or AlertSeverity.HIGH, "Té ngã được phát hiện"))
        if include_non_fall and telemetry.heart_rate is not None and self._has_persistent_abnormal_heart_rate(device.id, telemetry.timestamp_utc):
            specs.append((
                AlertType.HEART_RATE,
                telemetry.alert_level or AlertSeverity.HIGH,
                f"Nhịp tim bất thường kéo dài: {telemetry.heart_rate} bpm",
            ))
        if include_non_fall and telemetry.connection_status == ConnectionStatus.OFFLINE:
            specs.append((AlertType.CONNECTION, AlertSeverity.MEDIUM, "Mất kết nối thiết bị"))
        if include_non_fall and telemetry.battery is not None and telemetry.battery <= 20:
            specs.append((AlertType.LOW_BATTERY, AlertSeverity.LOW, f"Pin yếu ({telemetry.battery}%)"))
        unresolved_types = {
            alert.type
            for alert in ctx.alerts
            if same(alert.device_id, device.id) and alert.status != AlertStatus.CLOSED
        }
        return [
            self._new_alert(device, alert_type, severity, message, telemetry.timestamp_utc, ctx)
            for alert_type, severity, message in specs
            if alert_type not in unresolved_types
        ]

    def _has_persistent_abnormal_heart_rate(self, device_id: str, at: datetime) -> bool:
        rules = self.settings
        required = max(2, min(10, rules.heart_rate_samples_required))
        since = at - timedelta(minutes=max(1, rules.heart_rate_window_minutes))
        history = sorted(
            (
                t
                for t in self.repo.telemetry_since(since)
                if same(t.device_id, device_id) and t.timestamp_utc <= at and t.heart_rate is not None
            ),
            key=lambda t: t.timestamp_utc,
            reverse=True,
        )[:required]
        values = [t.heart_rate for t in history]
        if len(values) < required:
            return False

    @staticmethod
    def _new_alert(device: Device, type_: AlertType, severity: AlertSeverity, message: str, event_at: datetime, ctx: Context) -> Alert:
        now = utcnow()
        alert = Alert(
            id=f"ALERT-{now:%Y%m%d%H%M%S}-{uuid.uuid4().hex}"[:27].upper(),
            type=type_,
            severity=severity,
            device_id=device.id,
            user_id=device.user_id,
            facility_id=device.facility_id,
            room_id=device.room_id,
            latitude=device.latitude,
            longitude=device.longitude,
            message=message,
            event_at_utc=event_at,
            created_at_utc=now,
            updated_at_utc=now,
            is_urgent=severity == AlertSeverity.HIGH,
        )
        alert.add_audit("created", None, "Hệ thống tự động tạo cảnh báo", now)
        ctx.alerts.append(alert)
        return alert

    def _build_user_detail(self, user: Resident, ctx: Context) -> dict:
        device = _find(ctx.devices, user.device_id)
        alerts = sorted((a for a in ctx.alerts if same(a.user_id, user.id)), key=lambda a: a.event_at_utc, reverse=True)
        alert_dtos = [map_alert(a, ctx) for a in alerts]

        history: list[dict] = []
        if device is not None:
            since = utcnow() - timedelta(hours=24)
            history = [
                map_telemetry(t)
                for t in sorted(
                    (t for t in self.repo.telemetry_since(since) if same(t.device_id, device.id)),
                    key=lambda t: t.timestamp_utc,
                )
            ]

        events = [
            {
                "at": a["eventAt"],
                "type": a["type"],
                "status": a["status"],
                "description": a["message"],
                "value": f"{device.heart_rate} bpm" if a["type"] == "heart_rate" and device and device.heart_rate is not None else None,
                "isAutomatic": True,
            }
            for a in alert_dtos[:5]
        ]
        staff = _find(ctx.staff, user.staff_id)
        facility = _find(ctx.facilities, user.facility_id)
        return {
            "user": map_user(user, ctx),
            "facilityLocation": {
                "latitude": facility.latitude if facility else None,
                "longitude": facility.longitude if facility else None,
            },
            "contact": {
                "name": user.contact.name,
                "relation": user.contact.relation,
                "phone": user.contact.phone,
                "email": user.contact.email,
            },
            "responsibleStaff": map_staff(staff) if staff else None,
            "device": map_device(device, ctx) if device else None,
            "heartRateHistory": history,
            "recentEvents": events,
            "alertHistory": alert_dtos,
        }

    # ---- kiểm tra dữ liệu đầu vào ------------------------------------------------------
    @staticmethod
    def _validate_birth_year(year: int) -> None:
        if year < 1900 or year > utcnow().year:
            raise DomainError("Năm sinh không hợp lệ.")

    def _validate_device_input(self, inp: DeviceInput) -> None:
        if not inp.id or not inp.id.strip():
            raise DomainError("Device ID là bắt buộc.")
        required = (inp.patient_name, inp.contact_name, inp.contact_phone, inp.doctor_name)
        if not all((value or "").strip() for value in required):
            raise DomainError("Cần nhập bệnh nhân, người thân, số điện thoại và bác sĩ phụ trách.")
        if not (inp.facility_id or "").strip() or not (inp.room_id or "").strip():
            raise DomainError("Cần chọn cơ sở và phòng.")
        self._validate_birth_year(inp.birth_year)
        if inp.battery is not None and not 0 <= inp.battery <= 100:
            raise DomainError("Pin ban đầu phải nằm trong khoảng 0–100%.")

    def _validate_user_input(self, inp: UserInput) -> None:
        if not inp.full_name.strip():
            raise DomainError("Tên bệnh nhân là bắt buộc.")
        if not inp.facility_id.strip() or not inp.room_id.strip():
            raise DomainError("Cần chọn cơ sở và phòng.")
        self._validate_birth_year(inp.birth_year)

    @staticmethod
    def _validate_telemetry(inp: TelemetryInput) -> None:
        if not inp.device_id.strip():
            raise DomainError("DeviceId là bắt buộc.")
        if inp.battery is not None and not 0 <= inp.battery <= 100:
            raise DomainError("Battery phải nằm trong khoảng 0–100%.")
        if inp.fall_probability is not None and not 0 <= inp.fall_probability <= 1:
            raise DomainError("FallProbability phải nằm trong khoảng 0–1.")
        if inp.rssi is not None and not -130 <= inp.rssi <= 0:
            raise DomainError("RSSI phải nằm trong khoảng -130 đến 0 dBm.")
        if (inp.latitude is None) != (inp.longitude is None):
            raise DomainError("Latitude và longitude phải được gửi cùng nhau.")
        validate_motion(inp.accel_x, inp.accel_y, inp.accel_z, 1_000, "gia tốc")
        validate_motion(inp.gyro_x, inp.gyro_y, inp.gyro_z, 10_000, "con quay")

    @staticmethod
    def _validate_location(ctx: Context, facility_id: str, room_id: str) -> None:
        if not _find(ctx.facilities, facility_id):
            raise DomainError("Cơ sở không tồn tại.")
        if not any(same(r.id, room_id) and same(r.facility_id, facility_id) for r in ctx.rooms):
            raise DomainError("Phòng không tồn tại hoặc không thuộc cơ sở đã chọn.")

    @staticmethod
    def _parse_initial_connection(value: str | None) -> ConnectionStatus:
        key = (value or "").strip().lower()
        if key == "offline":
            return ConnectionStatus.OFFLINE
        if key == "weak":
            return ConnectionStatus.WEAK
        if key in ("", "active", "good"):
            return ConnectionStatus.GOOD
        raise DomainError("Trạng thái thiết bị ban đầu không hợp lệ.")

    @staticmethod
    def _parse_fall(value: str | None, fallback: FallStatus) -> FallStatus:
        key = (value or "").strip().lower()
        if key == "":
            return fallback
        if key in ("fall", "fallen", "1", "true"):
            return FallStatus.FALL
        if key in ("no_fall", "nofall", "normal", "0", "false"):
            return FallStatus.NO_FALL
        raise DomainError("FallStatus không hợp lệ.")

    @staticmethod
    def _parse_connection(value: str | None, fallback: ConnectionStatus) -> ConnectionStatus:
        key = (value or "").strip().lower()
        if key == "":
            return fallback
        if key in ("good", "online", "connected"):
            return ConnectionStatus.GOOD
        if key == "weak":
            return ConnectionStatus.WEAK
        if key in ("offline", "disconnected"):
            return ConnectionStatus.OFFLINE
        raise DomainError("ConnectionStatus không hợp lệ.")

    @staticmethod
    def _parse_severity(value: str | None) -> AlertSeverity | None:
        key = (value or "").strip().lower()
        if key == "":
            return None
        mapping = {"high": AlertSeverity.HIGH, "medium": AlertSeverity.MEDIUM, "low": AlertSeverity.LOW}
        if key not in mapping:
            raise DomainError("AlertLevel không hợp lệ.")
        return mapping[key]


def validate_motion(x: float | None, y: float | None, z: float | None, limit: float, label: str) -> None:
    for value in (x, y, z):
        if value is not None and (not math.isfinite(value) or abs(value) > limit):
            raise DomainError(f"Dữ liệu {label} không hợp lệ.")
