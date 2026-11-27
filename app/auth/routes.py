"""Registration v2 routes: landing, role-specific forms, admin login (ADR 007).

Forms use empty-string defaults so validation happens in ``app.auth.service``
and failures re-render the page as HTML instead of FastAPI's JSON 422.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.errors import (
    AdminDisabled,
    AuthValidationError,
    InvalidCredentials,
    RegistrationConflict,
)
from app.auth.security import create_access_token
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")

TRUCK_OPTIONS = (
    ("pickup", "وانت"),
    ("khavar", "خاور"),
    ("truck", "کامیون"),
    ("trailer", "تریلی"),
    ("refrigerated", "یخچال‌دار"),
    ("tanker", "تانکر"),
)

CARGO_OPTIONS = (
    ("general", "عمومی"),
    ("perishable", "فاسدشدنی"),
    ("fragile", "شکستنی"),
    ("bulk", "فله"),
    ("hazardous", "خطرناک"),
    ("heavy", "ماشین‌آلات / سنگین"),
)

SUCCESS_ROLES = {
    "driver": {
        "message": "حساب راننده ساخته شد. برای مشاهده بارها وارد شوید.",
        "action_label": "ورود به حساب",
        "action_href": "/auth/login",
    },
    "shipper": {
        "message": "حساب صاحب کالا ساخته شد. برای ثبت بار وارد شوید.",
        "action_label": "ورود به حساب",
        "action_href": "/auth/login",
    },
    "admin": {
        "message": "حساب مدیر ساخته شد. از صفحه ورود مدیران وارد شوید.",
        "action_label": "ورود مدیران",
        "action_href": "/auth/admin/login",
    },
}


def _render(
    name: str, request: Request, status_code: int = 200, **context
):
    return templates.TemplateResponse(
        request=request,
        name=name,
        context={"request": request, **context},
        status_code=status_code,
    )


def _first_error(exc: AuthValidationError) -> str:
    return next(iter(exc.errors.values()), service.VALIDATION_FAILED)


def _token_payload(user: User) -> dict[str, str]:
    payload = {"sub": str(user.id), "role": user.role.value}
    if user.phone:
        payload["phone"] = user.phone
    if user.username:
        payload["username"] = user.username
    return payload


def _login_response(user: User) -> RedirectResponse:
    token = create_access_token(_token_payload(user))
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return response


# --------------------------------------------------------------------------- #
# Landing
# --------------------------------------------------------------------------- #


@router.get("/register", response_class=HTMLResponse)
def register_landing(request: Request):
    return _render("auth/landing.html", request)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #


def _driver_page(
    request: Request,
    *,
    values: dict | None = None,
    errors: dict | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    return _render(
        "auth/register_driver.html",
        request,
        status_code,
        values=values or {},
        errors=errors or {},
        error=error,
        truck_options=TRUCK_OPTIONS,
    )


@router.get("/register/driver", response_class=HTMLResponse)
def driver_form(request: Request):
    return _driver_page(request)


@router.post("/register/driver", response_class=HTMLResponse)
def register_driver(
    request: Request,
    full_name: str = Form(""),
    phone: str = Form(""),
    national_id: str = Form(""),
    license_number: str = Form(""),
    truck_type: str = Form(""),
    plate_number: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    values = {
        "full_name": full_name,
        "phone": phone,
        "national_id": national_id,
        "license_number": license_number,
        "truck_type": truck_type,
        "plate_number": plate_number,
    }
    try:
        service.register_driver(db, {**values, "password": password})
    except AuthValidationError as exc:
        return _driver_page(
            request,
            values=values,
            errors=exc.errors,
            error=_first_error(exc),
            status_code=422,
        )
    except RegistrationConflict as exc:
        return _driver_page(request, values=values, error=exc.message, status_code=409)
    return RedirectResponse(
        url="/auth/register/success?role=driver", status_code=303
    )


# --------------------------------------------------------------------------- #
# Shipper
# --------------------------------------------------------------------------- #


def _shipper_page(
    request: Request,
    *,
    values: dict | None = None,
    errors: dict | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    return _render(
        "auth/register_shipper.html",
        request,
        status_code,
        values=values or {},
        errors=errors or {},
        error=error,
        cargo_options=CARGO_OPTIONS,
    )


@router.get("/register/shipper", response_class=HTMLResponse)
def shipper_form(request: Request):
    return _shipper_page(request)


@router.post("/register/shipper", response_class=HTMLResponse)
def register_shipper(
    request: Request,
    full_name: str = Form(""),
    phone: str = Form(""),
    cargo_type_preference: str = Form(""),
    national_id: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    values = {
        "full_name": full_name,
        "phone": phone,
        "cargo_type_preference": cargo_type_preference,
        "national_id": national_id,
    }
    try:
        service.register_shipper(db, {**values, "password": password})
    except AuthValidationError as exc:
        return _shipper_page(
            request,
            values=values,
            errors=exc.errors,
            error=_first_error(exc),
            status_code=422,
        )
    except RegistrationConflict as exc:
        return _shipper_page(request, values=values, error=exc.message, status_code=409)
    return RedirectResponse(
        url="/auth/register/success?role=shipper", status_code=303
    )


# --------------------------------------------------------------------------- #
# Admin registration
# --------------------------------------------------------------------------- #


def _admin_register_page(
    request: Request,
    *,
    values: dict | None = None,
    errors: dict | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    return _render(
        "auth/register_admin.html",
        request,
        status_code,
        values=values or {},
        errors=errors or {},
        error=error,
    )


@router.get("/register/admin", response_class=HTMLResponse)
def admin_form(request: Request):
    return _admin_register_page(request)


@router.post("/register/admin", response_class=HTMLResponse)
def register_admin(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    admin_code: str = Form(""),
    db: Session = Depends(get_db),
):
    values = {"username": username}
    try:
        service.register_admin(
            db, {"username": username, "password": password, "admin_code": admin_code}
        )
    except AdminDisabled as exc:
        return _admin_register_page(
            request, values=values, error=exc.message, status_code=503
        )
    except InvalidCredentials as exc:
        return _admin_register_page(
            request, values=values, error=exc.message, status_code=401
        )
    except AuthValidationError as exc:
        return _admin_register_page(
            request,
            values=values,
            errors=exc.errors,
            error=_first_error(exc),
            status_code=422,
        )
    except RegistrationConflict as exc:
        return _admin_register_page(
            request, values=values, error=exc.message, status_code=409
        )
    return RedirectResponse(
        url="/auth/register/success?role=admin", status_code=303
    )


# --------------------------------------------------------------------------- #
# Success
# --------------------------------------------------------------------------- #


@router.get("/register/success", response_class=HTMLResponse)
def register_success(request: Request, role: str = ""):
    details = SUCCESS_ROLES.get(role)
    if details is None:
        raise HTTPException(status_code=404)
    return _render("auth/success.html", request, role=role, **details)


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return _render("auth/login.html", request)


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    phone: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        user = service.authenticate_user(db, phone, password)
    except InvalidCredentials as exc:
        return _render(
            "auth/login.html",
            request,
            401,
            error=exc.message,
            values={"phone": phone},
        )
    return _login_response(user)


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_form(request: Request):
    return _render("auth/admin_login.html", request)


@router.post("/admin/login", response_class=HTMLResponse)
def admin_login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    admin_code: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        user = service.authenticate_admin(db, username, password, admin_code)
    except AdminDisabled as exc:
        return _render(
            "auth/admin_login.html",
            request,
            503,
            error=exc.message,
            values={"username": username},
        )
    except InvalidCredentials as exc:
        return _render(
            "auth/admin_login.html",
            request,
            401,
            error=exc.message,
            values={"username": username},
        )
    return _login_response(user)


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response
