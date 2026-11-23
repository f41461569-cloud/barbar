from typing import Literal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")

# User-facing messages for the styled error alert (docs/SPEC-ui.md §7.3).
REGISTER_PHONE_TAKEN = "این شماره تلفن قبلاً ثبت شده است."
LOGIN_INVALID_CREDENTIALS = "شماره تلفن یا رمز عبور نادرست است."


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={"request": request},
    )


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"request": request},
    )


@router.post("/register")
def register(
    request: Request,
    phone: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    role: Literal["driver", "shipper", "carrier"] = Form(...),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.phone == phone).one_or_none()
    if existing:
        # UI spec D1/A: same 409 status, but render the styled form instead of JSON.
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "request": request,
                "error": REGISTER_PHONE_TAKEN,
                "phone": phone,
                "name": name,
                "role": role,
            },
            status_code=409,
        )

    user = User(
        phone=phone,
        name=name,
        password_hash=hash_password(password),
        role=UserRole(role),
    )
    db.add(user)
    db.commit()
    return RedirectResponse(url="/auth/login", status_code=302)


@router.post("/login")
def login(
    request: Request,
    phone: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.phone == phone).one_or_none()
    if not user or not verify_password(password, user.password_hash):
        # UI spec D1/A: same 401 status, but render the styled form instead of JSON.
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "request": request,
                "error": LOGIN_INVALID_CREDENTIALS,
                "phone": phone,
            },
            status_code=401,
        )

    token = create_access_token(
        {"sub": str(user.id), "phone": user.phone, "role": user.role.value}
    )
    redirect_response = RedirectResponse(url="/dashboard", status_code=303)
    redirect_response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return redirect_response


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response
