"""REST API cho giao diện quản trị (/api/*). Yêu cầu đăng nhập + CSRF token."""
from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..deps import get_service
from ..schemas import (
    AlertActionInput,
    DeviceInput,
    DeviceLocationInput,
    FacilityInput,
    FacilityLocationInput,
    PortalAccountInput,
    PortalAccountStatusInput,
    StaffInput,
    SupportConfigInput,
    TelegramConfigInput,
    UserInput,
)
from ..security import admin_user, current_user, verify_csrf
from ..service import MonitoringService

router = APIRouter(prefix="/api", dependencies=[Depends(admin_user), Depends(verify_csrf)])

Service = Depends(get_service)


def _not_found(what: str = "Không tìm thấy dữ liệu.") -> HTTPException:
    return HTTPException(status_code=404, detail=what)


@router.get("/portal-accounts")
async def list_portal_accounts(svc: MonitoringService = Service):
    return svc.list_portal_accounts()


@router.post("/portal-accounts", status_code=201)
async def create_portal_account(payload: PortalAccountInput, svc: MonitoringService = Service):
    return svc.create_portal_account(payload)


@router.patch("/portal-accounts/{account_id}")
async def set_portal_account_status(
    account_id: str,
    payload: PortalAccountStatusInput,
    svc: MonitoringService = Service,
):
    result = svc.set_portal_account_active(account_id, payload.active)
    if result is None:
        raise _not_found("Không tìm thấy tài khoản portal.")
    return result


# ---- dashboard ---------------------------------------------------------------------
@router.get("/dashboard/overview")
async def dashboard_overview(svc: MonitoringService = Service):
    return svc.dashboard()


# ---- thiết bị ------------------------------------------------------------------------
@router.get("/devices")
async def list_devices(
    search: str | None = None,
    status: str | None = None,
    facility_id: str | None = Query(None, alias="facilityId"),
    battery: str | None = None,
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    svc: MonitoringService = Service,
):
    return svc.list_devices(search, status, facility_id, battery, page, page_size)


@router.get("/devices/summary")
async def device_summary(svc: MonitoringService = Service):
    return svc.device_summary()


@router.get("/devices/{device_id}")
async def get_device(device_id: str, svc: MonitoringService = Service):
    device = svc.get_device(device_id)
    if device is None:
        raise _not_found("Không tìm thấy thiết bị.")
    return device


@router.post("/devices", status_code=201)
async def create_device(payload: DeviceInput, svc: MonitoringService = Service):
    return svc.create_device(payload)


@router.post("/devices/{device_id}/check", status_code=202)
async def request_device_check(device_id: str, svc: MonitoringService = Service):
    if await svc.request_device_check(device_id) is None:
        raise _not_found("Không tìm thấy thiết bị.")
    return {"accepted": True, "deviceId": device_id}


@router.post("/devices/{device_id}/location")
async def update_device_location(
    device_id: str,
    payload: DeviceLocationInput,
    svc: MonitoringService = Service,
):
    result = await svc.update_device_location(device_id, payload.latitude, payload.longitude)
    if result is None:
        raise _not_found("Không tìm thấy đồng hồ.")
    return result


# ---- người dùng -------------------------------------------------------------------------
@router.get("/users")
async def list_users(
    search: str | None = None,
    facility_id: str | None = Query(None, alias="facilityId"),
    status: str | None = None,
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    svc: MonitoringService = Service,
):
    return svc.list_users(search, facility_id, status, page, page_size)


@router.get("/users/staff")
async def list_staff(facility_id: str | None = Query(None, alias="facilityId"), svc: MonitoringService = Service):
    return svc.list_staff(facility_id)


@router.post("/users/staff", status_code=201)
async def create_staff(payload: StaffInput, svc: MonitoringService = Service):
    return svc.create_staff(payload)


@router.get("/users/{user_id}")
async def get_user(user_id: str, svc: MonitoringService = Service):
    user = svc.get_user(user_id)
    if user is None:
        raise _not_found("Không tìm thấy người dùng.")
    return user


@router.post("/users", status_code=201)
async def create_user(payload: UserInput, svc: MonitoringService = Service):
    return svc.create_user(payload)


# ---- cảnh báo -------------------------------------------------------------------------------
@router.get("/alerts")
async def list_alerts(
    search: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    type: str | None = None,
    facility_id: str | None = Query(None, alias="facilityId"),
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    svc: MonitoringService = Service,
):
    return svc.list_alerts(search, status, severity, type, facility_id, page, page_size)


@router.get("/alerts/summary")
async def alert_summary(svc: MonitoringService = Service):
    return svc.alert_summary()


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str, svc: MonitoringService = Service):
    alert = svc.get_alert(alert_id)
    if alert is None:
        raise _not_found("Không tìm thấy cảnh báo.")
    return alert


@router.post("/alerts/{alert_id}/{operation}")
async def alert_action(
    request: Request,
    alert_id: str,
    operation: str,
    payload: AlertActionInput | None = None,
    svc: MonitoringService = Service,
):
    staff_id = request.session.get("staff_id")
    result = await svc.act_on_alert(alert_id, operation, payload.note if payload else None, staff_id)
    if result is None:
        raise _not_found("Không tìm thấy cảnh báo.")
    return result


# ---- cơ sở ---------------------------------------------------------------------------------------
@router.get("/facilities")
async def list_facilities(svc: MonitoringService = Service):
    return svc.list_facilities()


@router.post("/facilities", status_code=201)
async def create_facility(payload: FacilityInput, svc: MonitoringService = Service):
    return svc.create_facility(payload)


@router.post("/facilities/{facility_id}/location")
async def update_facility_location(
    facility_id: str,
    payload: FacilityLocationInput,
    svc: MonitoringService = Service,
):
    result = svc.update_facility_location(facility_id, payload.latitude, payload.longitude)
    if result is None:
        raise _not_found("Không tìm thấy cơ sở.")
    return result


# ---- Telegram --------------------------------------------------------------------------------------
@router.get("/telegram/status")
async def telegram_status(svc: MonitoringService = Service):
    return svc.telegram_status()


@router.post("/telegram/test")
async def telegram_test(svc: MonitoringService = Service):
    return await svc.test_telegram()


@router.post("/telegram/config")
async def telegram_config(payload: TelegramConfigInput, svc: MonitoringService = Service):
    return svc.configure_telegram(payload.enabled, payload.bot_token, payload.chat_id)


@router.get("/telegram/messages")
async def telegram_messages(svc: MonitoringService = Service):
    return await svc.telegram_messages()


@router.get("/support/config")
async def support_config(svc: MonitoringService = Service):
    return svc.support_config()


@router.post("/support/config")
async def save_support_config(
    payload: SupportConfigInput,
    request: Request,
    svc: MonitoringService = Service,
):
    result = svc.configure_support(payload.name, payload.phone, payload.email, payload.hours)
    request.app.state.settings = svc.settings
    return result


# ---- dữ liệu mô phỏng ---------------------------------------------------------------------------------
@router.get("/simulated/{device_id}")
async def simulated(device_id: str, svc: MonitoringService = Service):
    try:
        return svc.simulated_series(device_id)
    except (OSError, ValueError):
        return JSONResponse({"error": "Không đọc được dữ liệu mô phỏng."}, status_code=500)


# ---- thời gian thực (SSE) -----------------------------------------------------------------------------------
@router.get("/events")
async def events(request: Request, svc: MonitoringService = Service):
    return StreamingResponse(
        svc.hub.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
