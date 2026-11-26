"""Cargo create/list/detail queries (SPEC-core §5.2, §7.4)."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Cargo
from app.schemas import CargoCreate
from app.services.errors import CargoNotFound


def create_cargo(db: Session, *, shipper_id: int, data: CargoCreate) -> Cargo:
    cargo = Cargo(
        shipper_id=shipper_id,
        title=data.title,
        origin=data.origin,
        destination=data.destination,
        weight_kg=data.weight_kg,
        price=data.price,
        status="available",
    )
    db.add(cargo)
    db.commit()
    db.refresh(cargo)
    return cargo


def list_cargos(
    db: Session,
    *,
    status: str = "available",
    origin: str | None = None,
    destination: str | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Cargo], int]:
    query = db.query(Cargo)

    if status != "all":
        query = query.filter(Cargo.status == status)
    if origin is not None:
        query = query.filter(
            func.lower(Cargo.origin).contains(origin.strip().lower())
        )
    if destination is not None:
        query = query.filter(
            func.lower(Cargo.destination).contains(
                destination.strip().lower()
            )
        )
    if min_weight is not None:
        query = query.filter(Cargo.weight_kg >= min_weight)
    if max_weight is not None:
        query = query.filter(Cargo.weight_kg <= max_weight)
    if min_price is not None:
        query = query.filter(Cargo.price >= min_price)
    if max_price is not None:
        query = query.filter(Cargo.price <= max_price)

    total = query.count()
    items = (
        query.order_by(Cargo.id.desc()).offset(offset).limit(limit).all()
    )
    return items, total


def get_cargo(db: Session, cargo_id: int) -> Cargo:
    cargo = db.get(Cargo, cargo_id)
    if cargo is None:
        raise CargoNotFound()
    return cargo
