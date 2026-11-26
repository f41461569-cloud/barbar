"""Driver cargo list and the booking action (SPEC-core §8)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.guards import require_authenticated, require_driver
from app.database import get_db
from app.models import User
from app.pages import flash_for, render
from app.services.cargo_booking_service import book_cargo
from app.services.cargo_service import list_cargos
from app.services.document_service import verification_status
from app.services.errors import DomainError, Forbidden

router = APIRouter(tags=["pages"])


def _render_list(
    request: Request,
    user: User,
    db: Session,
    *,
    status: str = "available",
    origin: str | None = None,
    destination: str | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    flash: str | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    cargos, total = list_cargos(
        db,
        status=status,
        origin=origin,
        destination=destination,
        min_weight=min_weight,
        max_weight=max_weight,
        min_price=min_price,
        max_price=max_price,
        limit=100,
    )

    is_driver = user.role.value == "driver"
    state = verification_status(db, user.id) if is_driver else None

    return render(
        request,
        "cargos/list.html",
        user,
        status_code=status_code,
        error=error,
        flash=flash,
        cargos=cargos,
        total=total,
        is_driver=is_driver,
        is_verified=state == "verified",
        verification_state=state,
        active_status=status,
        filters={
            "origin": origin or "",
            "destination": destination or "",
            "min_weight": "" if min_weight is None else min_weight,
            "max_weight": "" if max_weight is None else max_weight,
            "min_price": "" if min_price is None else min_price,
            "max_price": "" if max_price is None else max_price,
        },
    )


@router.get("/cargos")
def cargos_page(
    request: Request,
    status: Literal["available", "booked", "all"] = "available",
    origin: Annotated[str | None, Query(max_length=200)] = None,
    destination: Annotated[str | None, Query(max_length=200)] = None,
    min_weight: Annotated[float | None, Query()] = None,
    max_weight: Annotated[float | None, Query()] = None,
    min_price: Annotated[float | None, Query()] = None,
    max_price: Annotated[float | None, Query()] = None,
    ok: str | None = None,
    user: User = Depends(require_authenticated),
    db: Session = Depends(get_db),
):
    is_admin = user.role.value == "admin"
    if not is_admin and status != "available":
        raise Forbidden()

    error = None
    if (
        min_weight is not None
        and max_weight is not None
        and min_weight > max_weight
    ):
        error = "کمینه وزن نباید بیشتر از بیشینه وزن باشد."
    elif (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        error = "کمینه قیمت نباید بیشتر از بیشینه قیمت باشد."

    if error:
        return render(
            request,
            "cargos/list.html",
            user,
            status_code=422,
            error=error,
            cargos=[],
            total=0,
            is_driver=user.role.value == "driver",
            is_verified=False,
            verification_state=None,
            active_status=status,
            filters={
                "origin": origin or "",
                "destination": destination or "",
                "min_weight": "" if min_weight is None else min_weight,
                "max_weight": "" if max_weight is None else max_weight,
                "min_price": "" if min_price is None else min_price,
                "max_price": "" if max_price is None else max_price,
            },
        )

    return _render_list(
        request,
        user,
        db,
        status=status,
        origin=origin,
        destination=destination,
        min_weight=min_weight,
        max_weight=max_weight,
        min_price=min_price,
        max_price=max_price,
        flash=flash_for(ok),
    )


@router.post("/cargos/{cargo_id}/book")
def book_cargo_page(
    request: Request,
    cargo_id: int,
    user: User = Depends(require_driver),
    db: Session = Depends(get_db),
):
    try:
        book_cargo(db, cargo_id=cargo_id, driver=user)
    except DomainError as exc:
        return _render_list(
            request,
            user,
            db,
            error=exc.message,
            status_code=exc.status_code,
        )

    return RedirectResponse(url="/cargos?ok=booked", status_code=303)
