"""Locked cargo claim + booking insert (ADR 005)."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Booking, Cargo, User
from app.services.document_service import verification_status
from app.services.errors import (
    CargoNotFound,
    CargoUnavailable,
    DriverNotVerified,
)


def book_cargo(db: Session, *, cargo_id: int, driver: User) -> Booking:
    """Claim a cargo for a verified driver.

    Three layers (ADR 005): verify + row lock, guarded status transition, and the
    partial unique index as a database backstop. The cargo update and booking
    insert commit in one transaction.
    """

    if verification_status(db, driver.id) != "verified":
        raise DriverNotVerified()

    cargo = (
        db.execute(
            select(Cargo)
            .where(Cargo.id == cargo_id)
            .with_for_update()
        )
        .scalar_one_or_none()
    )
    if cargo is None:
        db.rollback()
        raise CargoNotFound()

    claimed = db.execute(
        update(Cargo)
        .where(Cargo.id == cargo_id, Cargo.status == "available")
        .values(status="booked")
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise CargoUnavailable()

    booking = Booking(
        time_slot_id=None,
        driver_id=driver.id,
        cargo_id=cargo_id,
        status="confirmed",
    )
    db.add(booking)

    try:
        db.commit()
    except IntegrityError:
        # The partial unique index saw another confirmed booking first.
        db.rollback()
        raise CargoUnavailable()

    db.refresh(booking)
    return booking
