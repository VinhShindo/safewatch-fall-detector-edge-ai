"""PostgreSQL storage compatible with the existing Repository interface."""
from __future__ import annotations

import re
from datetime import datetime
from typing import TypeVar

from supabase import Client, create_client
from pydantic import ValidationError

from .models import Entity, utcnow
from .storage import InvalidDataError

T = TypeVar("T", bound=Entity)

_TABLES = {
    "devices.json": "devices",
    "users.json": "residents",
    "alerts.json": "alerts",
    "facilities.json": "facilities",
    "rooms.json": "rooms",
    "staff.json": "staff",
    "assignments.json": "assignments",
}
_TELEMETRY_PATTERN = re.compile(r"^telemetry/(\d{4}-\d{2}-\d{2})\.jsonl$")


class SupabaseStore:
    """Store JSON model payloads through the Supabase PostgREST API."""

    def __init__(self, supabase_url: str, secret_key: str) -> None:
        if not supabase_url.strip():
            raise RuntimeError("SUPABASE_URL chưa được cấu hình.")
        if not secret_key.strip():
            raise RuntimeError("SUPABASE_SECRET_KEY chưa được cấu hình.")
        # Một HTTP client sống suốt vòng đời app; không tạo lại theo từng truy vấn.
        self.conn: Client = create_client(supabase_url.strip(), secret_key.strip())
        self.client = self.conn

    @staticmethod
    def _table(relative: str) -> str:
        try:
            return _TABLES[relative]
        except KeyError as exc:
            raise InvalidDataError(f"File dữ liệu không được hỗ trợ trong PostgreSQL: {relative}") from exc

    def close(self) -> None:
        """Close the shared HTTP session when the application shuts down."""
        self.conn.postgrest.session.close()

    def read_list(self, relative: str, model: type[T]) -> list[T]:
        table = self._table(relative)
        response = self.client.table(table).select("data").order("id").execute()
        try:
            return [model.model_validate(row["data"]) for row in (response.data or [])]
        except (ValueError, ValidationError) as exc:
            raise InvalidDataError(f"Dữ liệu bảng '{table}' không hợp lệ: {exc}") from exc

    def write_list(self, relative: str, items: list[T]) -> None:
        table = self._table(relative)
        self.client.table(table).delete().neq("id", "").execute()
        if items:
            rows = [{"id": str(item.to_json().get("id", "")), "data": item.to_json(), "updated_at": utcnow().isoformat()} for item in items]
            self.client.table(table).insert(rows).execute()

    def append_line(self, relative: str, item: Entity) -> None:
        match = _TELEMETRY_PATTERN.match(relative)
        if not match:
            raise InvalidDataError(f"Nhật ký dữ liệu không được hỗ trợ trong PostgreSQL: {relative}")
        payload = item.to_json()
        timestamp = payload.get("timestamp") or payload.get("timestampUtc")
        self.client.table("telemetry_records").insert({"event_at": timestamp, "data": payload}).execute()

    def read_lines(self, relative: str, model: type[T]) -> list[T]:
        match = _TELEMETRY_PATTERN.match(relative)
        if not match:
            raise InvalidDataError(f"Nhật ký dữ liệu không được hỗ trợ trong PostgreSQL: {relative}")
        day = datetime.strptime(match.group(1), "%Y-%m-%d").date()
        next_day = day.fromordinal(day.toordinal() + 1)
        response = (
            self.client.table("telemetry_records")
            .select("data")
            .gte("event_at", day.isoformat())
            .lt("event_at", next_day.isoformat())
            .order("event_at")
            .execute()
        )
        return [model.model_validate(row["data"]) for row in (response.data or [])]

    def exists(self, relative: str) -> bool:
        if relative in _TABLES:
            table = self._table(relative)
            response = self.client.table(table).select("id").limit(1).execute()
            return bool(response.data)
        return False

    def clear_all(self) -> None:
        """Delete every SafeWatch record; intended for an explicit reset command."""
        self.client.table("telemetry_records").delete().gt("id", 0).execute()
        for table in ("alerts", "assignments", "devices", "residents", "staff", "rooms", "facilities"):
            self.client.table(table).delete().neq("id", "").execute()


class DatabaseRepository:
    """Repository factory kept separate so business logic remains unchanged."""

    @staticmethod
    def create(supabase_url: str, secret_key: str):
        from .storage import Repository

        return Repository(SupabaseStore(supabase_url, secret_key))
