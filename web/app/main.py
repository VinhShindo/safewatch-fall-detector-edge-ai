"""SeSide Admin và các portal family/facility trên cùng ứng dụng FastAPI."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import BASE_DIR, Settings
from .models import DomainError, NotFoundError
from .realtime import RealtimeHub
from .routers import api, device, pages, portal
from .security import FixedWindowRateLimiter, LoginAttemptLimiter, LoginRequired, TelemetryAuthenticator, login_redirect_target
from .service import MonitoringService
from .storage import InvalidDataError, JsonStore, Repository
from .telegram import TelegramNotifier

log = logging.getLogger("safewatch")

SESSION_HOURS = 8


class SecurityHeadersMiddleware:
    """Thêm các header bảo mật cơ bản cho mọi phản hồi."""

    HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(self)",
    }

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in self.HEADERS.items():
                    headers[key] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def offline_monitor(service: MonitoringService, settings: Settings) -> None:
    """Định kỳ đánh dấu thiết bị lâu không gửi dữ liệu là mất kết nối."""
    interval = max(15, settings.offline_check_interval_seconds)
    while True:
        await asyncio.sleep(interval)
        try:
            updated = await service.mark_stale_devices_offline()
            if updated:
                log.info("Đã đánh dấu %d thiết bị mất kết nối.", updated)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Không thể kiểm tra thiết bị mất kết nối.")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.storage_backend == "postgres":
            from .database import SupabaseStore

            store = SupabaseStore(settings.supabase_url, settings.supabase_secret_key)
            log.info("Lưu trữ Supabase: %s", settings.supabase_url)
        else:
            store = JsonStore(settings.data_dir)
            log.info("Lưu trữ JSON: %s", settings.data_dir)

        hub = RealtimeHub()
        notifier = TelegramNotifier(settings)
        app.state.service = MonitoringService(Repository(store), hub, notifier, settings)
        monitor = asyncio.create_task(offline_monitor(app.state.service, settings))
        try:
            yield
        finally:
            hub.close()  # đóng các kết nối SSE để server tắt nhanh
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
            await notifier.close()
            close_store = getattr(store, "close", None)
            if close_store is not None:
                close_store()

    app = FastAPI(
        title="SeSide Admin",
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )

    # ---- trạng thái dùng chung -------------------------------------------------------------
    app.state.settings = settings
    app.state.login_limiter = LoginAttemptLimiter(settings)
    app.state.telemetry_auth = TelemetryAuthenticator(settings)
    app.state.alert_limiter = FixedWindowRateLimiter(settings.esp32_rate_limit_per_minute, 60)
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    templates.env.globals["asset_v"] = int(time.time())  # đổi mỗi lần khởi động để trình duyệt tải lại CSS/JS
    app.state.templates = templates

    # ---- middleware (cái thêm sau nằm ngoài cùng) ------------------------------------------------
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.resolve_secret_key(),
        session_cookie="safewatch_session",
        max_age=SESSION_HOURS * 3600,
        same_site="strict",
        https_only=settings.require_https,
    )
    app.add_middleware(SecurityHeadersMiddleware)

    # ---- xử lý lỗi -----------------------------------------------------------------------------
    @app.exception_handler(LoginRequired)
    async def on_login_required(request: Request, _exc: LoginRequired):
        if request.url.path.startswith("/api"):
            return JSONResponse({"error": "Chưa đăng nhập hoặc phiên đã hết hạn."}, status_code=401)
        return RedirectResponse(login_redirect_target(request), status_code=303)

    @app.exception_handler(DomainError)
    async def on_domain_error(_request: Request, exc: DomainError):
        return JSONResponse({"error": str(exc)}, status_code=400)

    @app.exception_handler(NotFoundError)
    async def on_not_found(_request: Request, exc: NotFoundError):
        return JSONResponse({"error": str(exc)}, status_code=404)

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        detail = f"{where}: {first.get('msg', 'giá trị không hợp lệ')}" if where else first.get("msg", "yêu cầu không hợp lệ")
        return JSONResponse({"error": f"Dữ liệu gửi lên không hợp lệ ({detail})."}, status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def on_http_error(_request: Request, exc: StarletteHTTPException):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(InvalidDataError)
    async def on_invalid_data(_request: Request, exc: InvalidDataError):
        log.error("%s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)

    @app.exception_handler(Exception)
    async def on_unhandled(_request: Request, exc: Exception):
        log.exception("Lỗi không mong muốn", exc_info=exc)
        return JSONResponse({"error": "Đã có lỗi hệ thống. Vui lòng kiểm tra log máy chủ và thử lại."}, status_code=500)

    # ---- routes --------------------------------------------------------------------------------------
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.mount(
        "/demo-sw002",
        StaticFiles(directory=str(BASE_DIR.parent / "demo_sw002"), html=True),
        name="sw002_demo",
    )
    app.include_router(device.router)  # /health, /alert, /api/telemetry (không cần đăng nhập)
    app.include_router(api.router)  # /api/* (cần đăng nhập)
    app.include_router(pages.router)  # trang HTML
    app.include_router(portal.pages)
    app.include_router(portal.api)
    return app


app = create_app()
