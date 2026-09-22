"""Chạy SafeWatch Admin:  python run.py"""
from __future__ import annotations

import socket

import uvicorn

from app.config import Settings


def lan_ip() -> str:
    """Địa chỉ IP trong mạng LAN (để nhập vào firmware ESP32)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))  # không gửi gói tin nào, chỉ để hệ điều hành chọn card mạng
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1" if host in ("0.0.0.0", "") else host, port)) != 0


class GracefulServer(uvicorn.Server):
    """Đóng các kết nối realtime (SSE) trước khi tắt để Ctrl+C dừng ngay, không phải chờ trình duyệt."""

    async def shutdown(self, sockets=None) -> None:
        from app.main import app

        service = getattr(app.state, "service", None)
        if service is not None:
            service.hub.close()
        await super().shutdown(sockets)


def main() -> None:
    settings = Settings.from_env()
    if not port_is_free(settings.host, settings.port):
        raise SystemExit(
            f"Cổng {settings.port} đang được dùng. Hãy tắt chương trình đang chạy "
            "hoặc đổi PORT trong file .env."
        )

    ip = lan_ip()
    print("=" * 60)
    print(" SafeWatch Admin (FastAPI)")
    print(f" Trình duyệt : http://localhost:{settings.port}")
    print(f" ESP32 gửi tới: http://{ip}:{settings.port}/alert")
    print(" Dừng server  : Ctrl+C")
    print("=" * 60)

    # Chỉ chạy 1 tiến trình: dữ liệu lưu bằng file JSON nên không dùng nhiều worker.
    config = uvicorn.Config("app.main:app", host=settings.host, port=settings.port, timeout_graceful_shutdown=3)
    GracefulServer(config).run()


if __name__ == "__main__":
    main()
