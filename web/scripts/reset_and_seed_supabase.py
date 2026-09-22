"""Replace all Supabase data with validated real data from a JSON file.

The script never invents records. It validates the complete input before deleting
anything. Example:

    python scripts/reset_and_seed_supabase.py data/real_data.json --dry-run
    python scripts/reset_and_seed_supabase.py data/real_data.json --yes

Input format:
{
  "facilities": [], "rooms": [], "staff": [], "residents": [],
  "devices": [], "assignments": [], "alerts": [], "telemetry": []
}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings
from app.database import SupabaseStore
from app.models import Alert, Assignment, Device, Facility, Resident, Room, Staff, Telemetry

COLLECTIONS = {
    "facilities": Facility,
    "rooms": Room,
    "staff": Staff,
    "residents": Resident,
    "devices": Device,
    "assignments": Assignment,
    "alerts": Alert,
    "telemetry": Telemetry,
}


def load_and_validate(path: Path) -> dict[str, list[Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Không đọc được file dữ liệu: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemExit("File dữ liệu phải là một JSON object chứa các mảng dữ liệu.")

    unknown = set(raw) - set(COLLECTIONS)
    if unknown:
        raise SystemExit(f"Nhóm dữ liệu không hỗ trợ: {', '.join(sorted(unknown))}")

    validated: dict[str, list[Any]] = {}
    for name, model in COLLECTIONS.items():
        values = raw.get(name, [])
        if not isinstance(values, list):
            raise SystemExit(f"'{name}' phải là một mảng JSON.")
        try:
            validated[name] = [model.model_validate(value) for value in values]
        except Exception as exc:  # Pydantic validation errors include the record path.
            raise SystemExit(f"Dữ liệu '{name}' không hợp lệ: {exc}") from exc
    return validated


def seed(store: SupabaseStore, data: dict[str, list[Any]], dry_run: bool) -> None:
    counts = ", ".join(f"{name}={len(items)}" for name, items in data.items())
    print(f"Dữ liệu đã kiểm tra: {counts}")
    if dry_run:
        print("Dry run: chưa xóa hoặc ghi dữ liệu.")
        return

    store.clear_all()
    mapping = (
        ("facilities", "facilities.json"),
        ("rooms", "rooms.json"),
        ("staff", "staff.json"),
        ("residents", "users.json"),
        ("devices", "devices.json"),
        ("assignments", "assignments.json"),
        ("alerts", "alerts.json"),
    )
    for name, relative in mapping:
        if data[name]:
            store.write_list(relative, data[name])
    for item in data["telemetry"]:
        timestamp = item.timestamp_utc
        store.append_line(f"telemetry/{timestamp:%Y-%m-%d}.jsonl", item)
    print("Đã xóa dữ liệu cũ và chèn dữ liệu mới vào Supabase.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset and seed SafeWatch Supabase with real data")
    parser.add_argument("input", type=Path, help="JSON chứa dữ liệu thật theo format của script")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ kiểm tra dữ liệu, không ghi/xóa")
    parser.add_argument("--yes", action="store_true", help="Xác nhận xóa toàn bộ dữ liệu hiện tại")
    args = parser.parse_args()
    if not args.dry_run and not args.yes:
        raise SystemExit("Lệnh này sẽ xóa toàn bộ bảng. Dùng --yes để xác nhận.")

    settings = Settings.from_env()
    if settings.storage_backend != "postgres":
        raise SystemExit("Hãy đặt STORAGE_BACKEND=postgres trong .env.")
    data = load_and_validate(args.input)
    seed(SupabaseStore(settings.supabase_url, settings.supabase_secret_key), data, args.dry_run)


if __name__ == "__main__":
    main()