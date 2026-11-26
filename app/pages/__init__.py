"""Shared page helpers and flash-token mapping (SPEC-core §8)."""

from __future__ import annotations

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.models import User

templates = Jinja2Templates(directory="templates")

# Query values are never echoed: fixed tokens map to server-side strings.
FLASH_MESSAGES = {
    "uploaded": "مدرک بارگذاری شد و در انتظار بررسی است.",
    "reviewed": "وضعیت مدرک به‌روزرسانی شد.",
    "created": "بار جدید ثبت شد.",
    "booked": "بار با موفقیت رزرو شد.",
}


def flash_for(token: str | None) -> str | None:
    if not token:
        return None
    return FLASH_MESSAGES.get(token)


def page_context(
    request: Request,
    user: User | None,
    *,
    error: str | None = None,
    flash: str | None = None,
    **extra,
) -> dict:
    context = {
        "request": request,
        "current_user": user,
        "error": error,
        "flash": flash,
    }
    context.update(extra)
    return context


def render(
    request: Request,
    name: str,
    user: User | None,
    *,
    status_code: int = 200,
    error: str | None = None,
    flash: str | None = None,
    **extra,
):
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=page_context(
            request, user, error=error, flash=flash, **extra
        ),
        status_code=status_code,
    )
