"""Role-scoped family and facility portals."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from ..security import portal_user

pages = APIRouter()
api = APIRouter(prefix="/api/portal")


def _context(request: Request, role: str, role_label: str) -> dict:
    settings = request.app.state.settings
    return {
        "page": role,
        "csrf": request.session.get("csrf", ""),
        "user_name": request.session.get("user", "SeSide"),
        "role": role,
        "role_label": role_label,
        "support": {
            "name": settings.support_name,
            "phone": settings.support_phone,
            "email": settings.support_email,
            "hours": settings.support_hours,
        },
    }


@pages.get("/family", response_class=HTMLResponse)
async def family_home(request: Request):
    portal_user(request, "family")
    return request.app.state.templates.TemplateResponse(
        request,
        "family_portal.html",
        _context(request, "family", "Người nhà"),
    )


@pages.get("/facility-portal", response_class=HTMLResponse)
async def facility_home(request: Request):
    portal_user(request, "facility")
    return request.app.state.templates.TemplateResponse(
        request,
        "facility_portal.html",
        _context(request, "facility", "Nhân viên cơ sở"),
    )


@api.get("/family")
async def family_data(request: Request):
    session = portal_user(request, "family")
    result = request.app.state.service.family_portal_data(session.get("resident_id", ""))
    if result is None:
        raise HTTPException(status_code=404, detail="Hồ sơ được gán cho tài khoản không còn tồn tại.")
    return result


@api.get("/sw002")
async def sw002_data(request: Request, response: Response):
    session = portal_user(request, "family")
    result = request.app.state.service.family_portal_data(session.get("resident_id", ""))
    if result is None:
        raise HTTPException(status_code=404, detail="Hồ sơ được gán cho tài khoản không còn tồn tại.")

    user_id = str(result.get("user", {}).get("id", "")).casefold()
    device_id = str((result.get("device") or {}).get("id", "")).casefold()
    if "sw-002" not in {user_id, device_id}:
        raise HTTPException(status_code=403, detail="Tài khoản này không được gán cho hồ sơ SW-002.")

    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Cookie"
    return result


@api.get("/facility")
async def facility_data(request: Request):
    session = portal_user(request, "facility")
    result = request.app.state.service.facility_portal_data(session.get("facility_id", ""))
    if result is None:
        raise HTTPException(status_code=404, detail="Cơ sở được gán cho tài khoản không còn tồn tại.")
    return result
