"""Cập nhật thời gian thực tới trình duyệt bằng Server-Sent Events (thay cho SignalR)."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

HEARTBEAT_SECONDS = 15


class RealtimeHub:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._closed = False

    async def publish(self, event: str, payload: Any, facility_id: str | None = None) -> None:
        """Gửi sự kiện tới mọi trình duyệt đang mở (facility_id giữ lại để lọc theo cơ sở sau này)."""
        message = (event, json.dumps(payload, ensure_ascii=False, default=str))
        for queue in list(self._subscribers):
            if queue.full():  # trình duyệt xử lý chậm: bỏ sự kiện cũ nhất
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(message)

    async def stream(self) -> AsyncIterator[str]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            yield "retry: 3000\n\n"
            while not self._closed:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if item is None:  # tín hiệu đóng khi tắt server
                    break
                event, data = item
                yield f"event: {event}\ndata: {data}\n\n"
        finally:
            self._subscribers.discard(queue)

    def close(self) -> None:
        """Đóng mọi kết nối SSE để server tắt nhanh."""
        self._closed = True
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
