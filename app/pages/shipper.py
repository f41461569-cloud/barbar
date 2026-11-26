"""Shipper pages: own cargos and the create form (SPEC-core §8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.guards import require_shipper
from app.database import get_db
from app.models import Cargo, User
from app.pages import flash_for, render
from app.schemas import CargoCreate
from app.services.cargo_service import create_cargo

router = APIRouter(tags=["pages"])

STATUS_LABELS = {"available": "آماده رزرو", "booked": "رزرو شده"}
FORM_FIELDS = ("title", "origin", "destination", "weight_kg", "price")


def _own_cargos(db: Session, shipper_id: int) -> list[Cargo]:
    return (
        db.query(Cargo)
        .filter(Cargo.shipper_id == shipper_id)
        .order_by(Cargo.id.desc())
        .all()
    )


def _render_new(
    request: Request,
    user: User,
    *,
    values: dict | None = None,
    errors: dict | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    return render(
        request,
        "shipper/cargo_new.html",
        user,
        status_code=status_code,
        error=error,
        values=values or {field: "" for field in FORM_FIELDS},
        errors=errors or {},
    )


@router.get("/shipper/cargos")
def shipper_cargos_page(
    request: Request,
    ok: str | None = None,
    user: User = Depends(require_shipper),
    db: Session = Depends(get_db),
):
    cargos = _own_cargos(db, user.id)
    return render(
        request,
        "shipper/cargos.html",
        user,
        flash=flash_for(ok),
        cargos=cargos,
        status_labels=STATUS_LABELS,
    )


@router.get("/shipper/cargos/new")
def shipper_cargo_new_page(
    request: Request,
    user: User = Depends(require_shipper),
):
    return _render_new(request, user)


@router.post("/shipper/cargos/new")
def shipper_cargo_create_page(
    request: Request,
    title: Annotated[str, Form()] = "",
    origin: Annotated[str, Form()] = "",
    destination: Annotated[str, Form()] = "",
    weight_kg: Annotated[str, Form()] = "",
    price: Annotated[str, Form()] = "",
    user: User = Depends(require_shipper),
    db: Session = Depends(get_db),
):
    values = {
        "title": title,
        "origin": origin,
        "destination": destination,
        "weight_kg": weight_kg,
        "price": price,
    }

    try:
        payload = CargoCreate(
            title=title,
            origin=origin,
            destination=destination,
            weight_kg=weight_kg,
            price=price,
        )
    except ValidationError as exc:
        errors = {
            str(error["loc"][0]): error["msg"] for error in exc.errors()
        }
        return _render_new(
            request,
            user,
            values=values,
            errors=errors,
            error="اطلاعات واردشده معتبر نیست؛ موارد مشخص‌شده را اصلاح کنید.",
            status_code=422,
        )

    create_cargo(db, shipper_id=user.id, data=payload)
    return RedirectResponse(
        url="/shipper/cargos?ok=created", status_code=303
    )
