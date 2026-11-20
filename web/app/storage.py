"""Lưu trữ dữ liệu bằng file JSON (không cần database).

- ``*.json``  : danh sách thực thể, ghi nguyên tử (ghi file tạm rồi đổi tên) và giữ bản ``.bak``.
- ``telemetry/YYYY-MM-DD.jsonl`` : mỗi dòng một bản ghi telemetry.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import ValidationError

from .models import (
    Alert,
    Assignment,
    Device,
    Entity,
    Facility,
    PortalAccount,
    Resident,
    Room,
    Staff,
    Telemetry,
    utcnow,
)

log = logging.getLogger("safewatch.storage")
T = TypeVar("T", bound=Entity)
_CONTEXT_CACHE_TTL_SECONDS = 10


class InvalidDataError(Exception):
    """File dữ liệu bị hỏng hoặc sai định dạng."""


def _iter_json_objects(text: str) -> Iterator[tuple[object | None, str]]:
    """Đọc lần lượt các object JSON trong file .jsonl.

    Hỗ trợ cả dạng một-dòng-một-object lẫn object bị xuống dòng (pretty-printed) như trong
    dữ liệu cũ. Đoạn lỗi được bỏ qua và trả về (None, nội dung lỗi).
    """
    decoder = json.JSONDecoder()
    pos, length = 0, len(text)
    while pos < length:
        while pos < length and text[pos].isspace():
            pos += 1
        if pos >= length:
            break
        try:
            obj, end = decoder.raw_decode(text, pos)
            yield obj, ""
            pos = end
        except json.JSONDecodeError:
            newline = text.find("\n", pos)
            end = length if newline == -1 else newline + 1
            yield None, text[pos:end].strip()
            pos = end


class JsonStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "telemetry").mkdir(exist_ok=True)
        self._lock = threading.RLock()
        self._warned: set[str] = set()

    # ---- đường dẫn -------------------------------------------------------
    def _path(self, relative: str) -> Path:
        if not relative.strip():
            raise InvalidDataError("Đường dẫn dữ liệu không được để trống.")
        path = (self.root / relative).resolve()
        if path != self.root and self.root not in path.parents:
            raise InvalidDataError("Đường dẫn dữ liệu không hợp lệ.")
        return path

    def exists(self, relative: str) -> bool:
        return self._path(relative).is_file()

    # ---- danh sách thực thể (.json) --------------------------------------
    def read_list(self, relative: str, model: type[T]) -> list[T]:
        path = self._path(relative)
        with self._lock:
            if not path.is_file():
                return []
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig") or "[]")
                if not isinstance(data, list):
                    raise ValueError("Nội dung phải là một mảng JSON.")
                return [model.model_validate(item) for item in data]
            except (ValueError, ValidationError) as exc:  # JSONDecodeError là ValueError
                corrupt = path.with_name(f"{path.name}.corrupt-{utcnow():%Y%m%d%H%M%S}")
                shutil.copyfile(path, corrupt)
                raise InvalidDataError(
                    f"File dữ liệu '{relative}' không hợp lệ. Bản sao đã được lưu tại '{corrupt.name}'. Chi tiết: {exc}"
                ) from exc

    def write_list(self, relative: str, items: list[T]) -> None:
        path = self._path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([item.to_json() for item in items], ensure_ascii=False, indent=2)
        with self._lock:
            temp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
            try:
                with open(temp, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                if path.is_file():
                    shutil.copyfile(path, path.with_name(path.name + ".bak"))
                os.replace(temp, path)
            finally:
                if temp.exists():
                    temp.unlink()

    # ---- nhật ký dòng (.jsonl) -------------------------------------------
    def append_line(self, relative: str, item: Entity) -> None:
        path = self._path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(item.to_json(), ensure_ascii=False, separators=(",", ":"))
        with self._lock, open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")

    def read_lines(self, relative: str, model: type[T]) -> list[T]:
        path = self._path(relative)
        with self._lock:
            if not path.is_file():
                return []
            text = path.read_text(encoding="utf-8-sig")
        result: list[T] = []
        invalid = 0
        for obj, _bad in _iter_json_objects(text):
            if obj is None:
                invalid += 1
                continue
            try:
                result.append(model.model_validate(obj))
            except ValidationError:
                invalid += 1
        if invalid and relative not in self._warned:  # chỉ cảnh báo một lần, không sinh file rác
            self._warned.add(relative)
            log.warning("Bỏ qua %d bản ghi không hợp lệ trong %s", invalid, relative)
        return result


@dataclass
class Context:
    """Ảnh chụp toàn bộ dữ liệu tại một thời điểm (tương đương LoadContext của bản cũ)."""

    devices: list[Device] = field(default_factory=list)
    residents: list[Resident] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    facilities: list[Facility] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    staff: list[Staff] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    portal_accounts: list[PortalAccount] = field(default_factory=list)


class Repository:
    """Truy cập các file JSON theo tên nghiệp vụ."""

    def __init__(self, store: JsonStore) -> None:
        self.store = store
        self._context_cache: Context | None = None
        self._context_cache_loaded_at: float | None = None
        self._context_cache_lock = threading.RLock()

    def load_context(self) -> Context:
        with self._context_cache_lock:
            now = time.monotonic()
            if (
                self._context_cache is not None
                and self._context_cache_loaded_at is not None
                and now - self._context_cache_loaded_at < _CONTEXT_CACHE_TTL_SECONDS
            ):
                return self._context_cache
            s = self.store
            context = Context(
                devices=s.read_list("devices.json", Device),
                residents=s.read_list("users.json", Resident),
                alerts=s.read_list("alerts.json", Alert),
                facilities=s.read_list("facilities.json", Facility),
                rooms=s.read_list("rooms.json", Room),
                staff=s.read_list("staff.json", Staff),
                assignments=s.read_list("assignments.json", Assignment),
                portal_accounts=s.read_list("portal_accounts.json", PortalAccount),
            )
            self._context_cache = context
            self._context_cache_loaded_at = time.monotonic()
            return self._context_cache

    def invalidate_context(self) -> None:
        with self._context_cache_lock:
            self._context_cache = None
            self._context_cache_loaded_at = None

    def save_devices(self, items: list[Device]) -> None:
        self.store.write_list("devices.json", items)
        self.invalidate_context()

    def save_residents(self, items: list[Resident]) -> None:
        self.store.write_list("users.json", items)
        self.invalidate_context()

    def save_alerts(self, items: list[Alert]) -> None:
        self.store.write_list("alerts.json", items)
        self.invalidate_context()

    def save_staff(self, items: list[Staff]) -> None:
        self.store.write_list("staff.json", items)
        self.invalidate_context()

    def save_assignments(self, items: list[Assignment]) -> None:
        self.store.write_list("assignments.json", items)
        self.invalidate_context()

    def save_portal_accounts(self, items: list[PortalAccount]) -> None:
        self.store.write_list("portal_accounts.json", items)
        self.invalidate_context()

    def save_facilities(self, items: list[Facility]) -> None:
        self.store.write_list("facilities.json", items)
        self.invalidate_context()

    # ---- telemetry ---------------------------------------------------------
    @staticmethod
    def _telemetry_file(day: datetime) -> str:
        return f"telemetry/{day:%Y-%m-%d}.jsonl"

    def append_telemetry(self, telemetry: Telemetry) -> None:
        self.store.append_line(self._telemetry_file(telemetry.timestamp_utc), telemetry)

    def telemetry_since(self, since: datetime) -> list[Telemetry]:
        now = utcnow()
        values: list[Telemetry] = []
        day = since.replace(hour=0, minute=0, second=0, microsecond=0)
        while day.date() <= now.date():
            values.extend(self.store.read_lines(self._telemetry_file(day), Telemetry))
            day += timedelta(days=1)
        upper = now + timedelta(minutes=2)
        return [item for item in values if since <= item.timestamp_utc <= upper]
