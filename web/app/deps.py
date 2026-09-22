"""Các dependency dùng chung cho router."""
from __future__ import annotations

from fastapi import Request

from .config import Settings
from .service import MonitoringService


def get_service(request: Request) -> MonitoringService:
    return request.app.state.service


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
