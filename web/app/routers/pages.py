"""Các trang HTML (đăng nhập + giao diện quản trị)."""
from __future__ import annotations

import hmac
import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..deps import get_settings
from ..config import Settings
from ..models import utcnow
from ..security import admin_user, current_user, is_local_url, verify_password

router = APIRouter()


def render(request: Request, template: str, page: str, with_facilities: bool = False, **extra) -> HTMLResponse:
    context = {
        "page": page,
        "csrf": request.session.get("csrf", ""),
        "user_name": request.session.get("user", "Admin"),
        "role": request.session.get("role", "admin"),
        "role_label": {"admin": "Quản trị viên", "family": "Người nhà", "facility": "Nhân viên cơ sở"}.get(request.session.get("role", "admin"), "Tài khoản"),
        "support": {
            "name": request.app.state.settings.support_name,
            "phone": request.app.state.settings.support_phone,
            "email": request.app.state.settings.support_email,
            "hours": request.app.state.settings.support_hours,
        },
        "facilities": request.app.state.service.facility_options() if with_facilities else [],
        **extra,
    }
    return request.app.state.templates.TemplateResponse(request, template, context)


# ---- đăng nhập / đăng xuất ---------------------------------------------------------------
@router.get("/account/login", response_class=HTMLResponse)
async def login_page(request: Request, returnUrl: str | None = None):
    if request.session.get("user"):
        return RedirectResponse(_home_for_role(request.session), status_code=303)
    return request.app.state.templates.TemplateResponse(
        request, "login.html", {"return_url": returnUrl if is_local_url(returnUrl) else "", "error": None, "username": ""}
    )


@router.post("/account/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    return_url: str = Form(""),
    settings: Settings = Depends(get_settings),
):
    templates = request.app.state.templates
    limiter = request.app.state.login_limiter

    def fail(message: str):
        return templates.TemplateResponse(
            request, "login.html", {"return_url": return_url if is_local_url(return_url) else "", "error": message, "username": username}
        )

    username = username.strip()
    if not username or not password:
        return fail("Vui lòng nhập tên đăng nhập và mật khẩu.")

    client = request.client.host if request.client else "unknown"
    attempt_key = f"{client}:{username}"
    now = utcnow()
    remaining = limiter.is_locked(attempt_key, now)
    if remaining is not None:
        minutes = int(-(-remaining.total_seconds() // 60))
        return fail(f"Tài khoản tạm khóa do đăng nhập sai nhiều lần. Thử lại sau {minutes} phút.")

    admin_username_ok = hmac.compare_digest(username.lower().encode(), settings.admin_username.lower().encode())
    admin_password_ok = verify_password(password, settings.admin_password_hash)
    account = request.app.state.service.authenticate_portal_account(username)
    account_password_ok = verify_password(
        password,
        account.password_hash if account else settings.admin_password_hash,
    )
    if admin_username_ok and admin_password_ok:
        limiter.register_success(attempt_key)
        request.session.clear()
        request.session.update(
            user=settings.admin_username,
            role="admin",
            staff_id=settings.admin_staff_id,
            csrf=secrets.token_urlsafe(32),
        )
        return RedirectResponse(return_url if is_local_url(return_url) else "/", status_code=303)

    if account and account_password_ok:
        limiter.register_success(attempt_key)
        request.session.clear()
        request.session.update(
            user=account.username,
            role=account.role,
            resident_id=account.resident_id,
            facility_id=account.facility_id,
            staff_id=account.staff_id,
            portal_account_id=account.id,
            csrf=secrets.token_urlsafe(32),
        )
        return RedirectResponse(_home_for_role(request.session), status_code=303)

    limiter.register_failure(attempt_key, now)
    return fail("Tên đăng nhập hoặc mật khẩu không đúng.")


@router.post("/account/logout")
async def logout(request: Request, csrf_token: str = Form("")):
    if request.session.get("user"):
        expected = request.session.get("csrf", "")
        if not expected or not hmac.compare_digest(csrf_token.encode(), expected.encode()):
            return RedirectResponse("/", status_code=303)
    request.session.clear()
    return RedirectResponse("/account/login", status_code=303)


# ---- trang giao diện -----------------------------------------------------------------------
def _home_for_role(session: dict) -> str:
    return {"family": "/family", "facility": "/facility-portal"}.get(session.get("role"), "/")


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(admin_user)])
async def overview(request: Request):
    return render(request, "overview.html", "overview")


@router.get("/devices", response_class=HTMLResponse, dependencies=[Depends(admin_user)])
async def devices(request: Request):
    return render(request, "devices.html", "devices", with_facilities=True)


@router.get("/devices/create", response_class=HTMLResponse, dependencies=[Depends(admin_user)])
async def device_create(request: Request):
    return render(request, "device_create.html", "devices", with_facilities=True)


@router.get("/users", response_class=HTMLResponse, dependencies=[Depends(admin_user)])
async def users(request: Request):
    return render(request, "users.html", "users", with_facilities=True)


@router.get("/alerts", response_class=HTMLResponse, dependencies=[Depends(admin_user)])
async def alerts(request: Request):
    return render(request, "alerts.html", "alerts")


@router.get("/reports", response_class=HTMLResponse, dependencies=[Depends(admin_user)])
async def reports(request: Request):
    return render(request, "reports.html", "reports")


@router.get("/facilities", response_class=HTMLResponse, dependencies=[Depends(admin_user)])
async def facilities(request: Request):
    return render(request, "facilities.html", "facilities")


@router.get("/settings", response_class=HTMLResponse, dependencies=[Depends(admin_user)])
async def settings_page(request: Request):
    return render(request, "settings.html", "settings", with_facilities=True,
                  portal_residents=request.app.state.service.portal_resident_options(),
                  portal_staff=request.app.state.service.list_staff())
