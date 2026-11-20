#!/usr/bin/env python3
"""Seed clearly marked synthetic heart-rate history for devices without recent HR data."""
from __future__ import annotations

import argparse
import math
from datetime import timedelta

from app.config import Settings
from app.database import DatabaseRepository
from app.models import AlertSeverity, ConnectionStatus, FallStatus, Telemetry, utcnow
from app.storage import JsonStore, Repository


def create_repository(settings: Settings) -> Repository:
    if settings.storage_backend == "postgres":
        return DatabaseRepository.create(settings.supabase_url, settings.supabase_secret_key)
    return Repository(JsonStore(settings.data_dir))


def demo_heart_rate(device_id: str, index: int, total: int, current: int | None) -> int:
    base = current if current is not None and 55 <= current <= 95 else 72
    phase = sum(ord(char) for char in device_id) % 17 / 5
    wave = 7.0 * math.sin(2 * math.pi * index / max(total - 1, 1) * 2 + phase)
    detail = 2.0 * math.sin(index * 1.7 + phase)
    return max(58, min(94, round(base + wave + detail)))


def seed(points: int, hours: float, apply: bool) -> tuple[int, int, int]:
    settings = Settings.from_env()
    repository = create_repository(settings)
    now = utcnow()
    since = now - timedelta(hours=hours)
    devices = repository.load_context().devices
    recent = [item for item in repository.telemetry_since(since) if item.heart_rate is not None]

    by_device: dict[str, list[Telemetry]] = {}
    for item in recent:
        by_device.setdefault(item.device_id.casefold(), []).append(item)

    planned: list[Telemetry] = []
    skipped_real = 0
    skipped_seeded = 0
    for device in devices:
        history = by_device.get(device.id.casefold(), [])
        if any(item.data_source != "demo" for item in history):
            skipped_real += 1
            continue
        if history:
            skipped_seeded += 1
            continue

        phase = sum(ord(char) for char in device.id) % 17 / 5
        for index in range(points):
            offset_hours = hours * (points - index) / (points + 1)
            event_time = now - timedelta(hours=offset_hours)
            planned.append(
                Telemetry(
                    device_id=device.id,
                    timestamp_utc=event_time,
                    data_source="demo",
                    heart_rate=demo_heart_rate(device.id, index, points, device.heart_rate),
                    battery=device.battery,
                    fall_status=FallStatus.NO_FALL,
                    fall_probability=0.01,
                    alert_level=AlertSeverity.LOW,
                    connection_status=device.connection_status,
                    rssi=device.rssi,
                )
            )

    print(f"Storage backend: {settings.storage_backend}")
    print(f"Devices found: {len(devices)}")
    print(f"Devices skipped (recent real HR): {skipped_real}")
    print(f"Devices skipped (demo history already present): {skipped_seeded}")
    print(f"Synthetic telemetry to {'write' if apply else 'write with --apply'}: {len(planned)}")

    if apply:
        for telemetry in planned:
            repository.append_telemetry(telemetry)
        print(f"Inserted {len(planned)} clearly marked demo samples.")
    else:
        print("Dry run only. Add --apply to write demo data.")

    close = getattr(repository.store, "close", None)
    if close:
        close()
    return len(devices), len(planned), skipped_real


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", type=int, default=24, help="Samples per device (default: 24)")
    parser.add_argument("--hours", type=float, default=24, help="History window in hours (default: 24)")
    parser.add_argument("--apply", action="store_true", help="Write the generated samples; otherwise only preview")
    args = parser.parse_args()
    if args.points < 2 or args.hours <= 0 or args.hours > 24:
        parser.error("--points phải >= 2 và --hours phải trong khoảng (0, 24].")
    seed(args.points, args.hours, args.apply)


if __name__ == "__main__":
    main()
