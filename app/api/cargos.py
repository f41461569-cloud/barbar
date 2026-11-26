"""Cargo JSON routes (SPEC-core §7.2)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.auth.guards import (
    require_authenticated,
    require_roles,
    require_shipper,
)
from app.database import get_db
from app.models import User
from app.schemas import (
    CargoBookingResponse,
    CargoCreate,
    CargoListResponse,
    CargoResponse,
)
from app.services.cargo_booking_service import book_cargo
from app.services.cargo_service import create_cargo, get_cargo, list_cargos
from app.services.errors import Forbidden

router = APIRouter(prefix="/api/cargos", tags=["cargos"])


def _reject_empty(value: str | None, field: str) -> None:
    if value is not None and not value.strip():
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", field),
                    "msg": "must not be blank",
                    "input": value,
                }
            ]
        )


@router.post("", status_code=201, response_model=CargoResponse)
def create(
    payload: CargoCreate,
    response: Response,
    user: User = Depends(require_shipper),
    db: Session = Depends(get_db),
):
    cargo = create_cargo(db, shipper_id=user.id, data=payload)
    response.headers["Location"] = f"/api/cargos/{cargo.id}"
    return cargo


@router.get("", response_model=CargoListResponse)
def index(
    status: Literal["available", "booked", "all"] = "available",
    origin: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    destination: Annotated[
        str | None, Query(min_length=1, max_length=200)
    ] = None,
    min_weight: Annotated[float | None, Query()] = None,
    max_weight: Annotated[float | None, Query()] = None,
    min_price: Annotated[float | None, Query()] = None,
    max_price: Annotated[float | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(require_authenticated),
    db: Session = Depends(get_db),
):
    _reject_empty(origin, "origin")
    _reject_empty(destination, "destination")

    if (
        min_weight is not None
        and max_weight is not None
        and min_weight > max_weight
    ):
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "min_weight"),
                    "msg": "min_weight must be less than or equal to max_weight",
                    "input": min_weight,
                }
            ]
        )
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "min_price"),
                    "msg": "min_price must be less than or equal to max_price",
                    "input": min_price,
                }
            ]
        )

    if user.role.value != "admin" and status != "available":
        raise Forbidden()

    items, total = list_cargos(
        db,
        status=status,
        origin=origin,
        destination=destination,
        min_weight=min_weight,
        max_weight=max_weight,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
        offset=offset,
    )
    return CargoListResponse(
        items=[CargoResponse.model_validate(cargo) for cargo in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{cargo_id}", response_model=CargoResponse)
def detail(
    cargo_id: int,
    user: User = Depends(require_authenticated),
    db: Session = Depends(get_db),
):
    return CargoResponse.model_validate(get_cargo(db, cargo_id))


@router.post(
    "/{cargo_id}/book",
    status_code=201,
    response_model=CargoBookingResponse,
)
def book(
    cargo_id: int,
    user: User = Depends(require_roles("driver")),
    db: Session = Depends(get_db),
):
    return book_cargo(db, cargo_id=cargo_id, driver=user)
