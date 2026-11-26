"""RED/GREEN tests for concurrency-safe cargo booking (ADR 005, SPEC-core §7.2)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine
from app.models import Booking, Cargo
from tests.support import (
    client_for,
    make_cargo,
    make_user,
    make_verified_driver,
)

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Cargo booking tests require PostgreSQL (set DATABASE_URL to a test URL).",
)

BOOKING_KEYS = {
    "id",
    "cargo_id",
    "driver_id",
    "time_slot_id",
    "status",
    "created_at",
}


def _code(response):
    return response.json()["detail"]["code"]


def _bookings_for(cargo_id: int) -> list[Booking]:
    db = SessionLocal()
    try:
        return (
            db.query(Booking)
            .filter(
                Booking.cargo_id == cargo_id,
                Booking.status == "confirmed",
            )
            .all()
        )
    finally:
        db.close()


def _cargo_status(cargo_id: int) -> str:
    db = SessionLocal()
    try:
        return db.get(Cargo, cargo_id).status
    finally:
        db.close()


def test_verified_driver_books_available_cargo():
    driver = make_verified_driver()
    cargo = make_cargo()

    response = client_for(driver).post(f"/api/cargos/{cargo.id}/book")

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == BOOKING_KEYS
    assert body["cargo_id"] == cargo.id
    assert body["driver_id"] == driver.id
    assert body["time_slot_id"] is None
    assert body["status"] == "confirmed"

    assert _cargo_status(cargo.id) == "booked"
    bookings = _bookings_for(cargo.id)
    assert len(bookings) == 1
    assert bookings[0].time_slot_id is None
    assert bookings[0].driver_id == driver.id


def test_body_driver_id_is_ignored():
    driver = make_verified_driver()
    other = make_user("driver")
    cargo = make_cargo()

    response = client_for(driver).post(
        f"/api/cargos/{cargo.id}/book", json={"driver_id": other.id}
    )

    assert response.status_code == 201, response.text
    assert response.json()["driver_id"] == driver.id
    assert len(_bookings_for(cargo.id)) == 1


def test_duplicate_booking_returns_409():
    driver = make_verified_driver()
    cargo = make_cargo()
    client = client_for(driver)

    assert client.post(f"/api/cargos/{cargo.id}/book").status_code == 201

    second = client.post(f"/api/cargos/{cargo.id}/book")
    assert second.status_code == 409
    assert _code(second) == "cargo_unavailable"
    assert len(_bookings_for(cargo.id)) == 1


def test_second_driver_gets_409():
    first = make_verified_driver()
    second = make_verified_driver()
    cargo = make_cargo()

    assert client_for(first).post(f"/api/cargos/{cargo.id}/book").status_code == 201

    response = client_for(second).post(f"/api/cargos/{cargo.id}/book")
    assert response.status_code == 409
    assert _code(response) == "cargo_unavailable"


def test_unverified_driver_is_forbidden_and_cargo_stays_available():
    driver = make_user("driver")
    cargo = make_cargo()

    response = client_for(driver).post(f"/api/cargos/{cargo.id}/book")

    assert response.status_code == 403
    assert _code(response) == "driver_not_verified"
    assert _cargo_status(cargo.id) == "available"
    assert _bookings_for(cargo.id) == []


def test_only_drivers_may_book():
    cargo = make_cargo()
    assert client_for(None).post(f"/api/cargos/{cargo.id}/book").status_code == 401

    for role in ("shipper", "carrier", "admin"):
        response = client_for(make_user(role)).post(
            f"/api/cargos/{cargo.id}/book"
        )
        assert response.status_code == 403, (role, response.text)
        assert _code(response) == "forbidden"

    assert _cargo_status(cargo.id) == "available"


def test_missing_cargo_is_404():
    driver = make_verified_driver()
    response = client_for(driver).post("/api/cargos/2147483647/book")
    assert response.status_code == 404
    assert _code(response) == "cargo_not_found"


def test_already_booked_cargo_is_409():
    driver = make_verified_driver()
    cargo = make_cargo(status="booked")

    response = client_for(driver).post(f"/api/cargos/{cargo.id}/book")

    assert response.status_code == 409
    assert _code(response) == "cargo_unavailable"
    assert _bookings_for(cargo.id) == []


def test_partial_unique_index_blocks_a_second_confirmed_booking():
    first = make_verified_driver()
    second = make_verified_driver()
    cargo = make_cargo()

    assert client_for(first).post(f"/api/cargos/{cargo.id}/book").status_code == 201

    db = SessionLocal()
    try:
        db.add(
            Booking(
                time_slot_id=None,
                driver_id=second.id,
                cargo_id=cargo.id,
                status="confirmed",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()

    assert len(_bookings_for(cargo.id)) == 1
