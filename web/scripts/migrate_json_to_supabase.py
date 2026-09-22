"""Migrate existing JSON/JSONL data into Supabase PostgreSQL.

Run after scripts/supabase_schema.sql and Supabase credentials are configured:
    python scripts/migrate_json_to_supabase.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings
from app.database import SupabaseStore
from app.models import Alert, Assignment, Device, Facility, Resident, Room, Staff, Telemetry
from app.storage import JsonStore

LISTS = (
    ("facilities.json", Facility),
    ("rooms.json", Room),
    ("staff.json", Staff),
    ("users.json", Resident),
    ("devices.json", Device),
    ("assignments.json", Assignment),
    ("alerts.json", Alert),
)


def migrate(data_dir: Path, supabase_url: str, secret_key: str, dry_run: bool) -> None:
    source = JsonStore(data_dir)
    target = SupabaseStore(supabase_url, secret_key)
    total = 0

    for relative, model in LISTS:
        items = source.read_list(relative, model)
        total += len(items)
        print(f"{relative}: {len(items)}")
        if not dry_run and items:
            target.write_list(relative, items)

    for path in sorted((data_dir / "telemetry").glob("*.jsonl")):
        items = source.read_lines(f"telemetry/{path.name}", Telemetry)
        total += len(items)
        print(f"telemetry/{path.name}: {len(items)}")
        if not dry_run:
            for item in items:
                target.append_line(f"telemetry/{path.name}", item)

    print(f"Tổng số bản ghi: {total}")
    if dry_run:
        print("Dry run: chưa ghi dữ liệu.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SafeWatch JSON data to Supabase PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ đếm dữ liệu, không ghi database")
    args = parser.parse_args()
    settings = Settings.from_env()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SystemExit("Thiếu SUPABASE_URL hoặc SUPABASE_SECRET_KEY trong file .env.")
    migrate(settings.data_dir, settings.supabase_url, settings.supabase_secret_key, args.dry_run)


if __name__ == "__main__":
    main()
