"""PostgreSQL concurrency proof for cargo booking (ADR 005, SPEC-core AC-12/AC-14)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.models import Booking, Cargo
from tests.support import auth_headers, make_cargo, make_user, make_verified_driver

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Concurrency proof requires PostgreSQL (set DATABASE_URL to a test URL).",
)


def _client_for_thread(driver) -> TestClient:
    from app.main import app

    return TestClient(app, headers=auth_headers(driver))


def _confirmed(cargo_id: int) -> list[Booking]:
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


def _status(cargo_id: int) -> str:
    db = SessionLocal()
    try:
        return db.get(Cargo, cargo_id).status
    finally:
        db.close()


def test_two_drivers_race_for_one_cargo():
    first = make_verified_driver()
    second = make_verified_driver()
    cargo = make_cargo()
    barrier = Barrier(2)

    def book(driver):
        client = _client_for_thread(driver)
        barrier.wait(timeout=10)
        return client.post(f"/api/cargos/{cargo.id}/book")

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(book, (first, second)))

    assert sorted(response.status_code for response in responses) == [201, 409], [
        response.text for response in responses
    ]
    assert len(_confirmed(cargo.id)) == 1
    assert _status(cargo.id) == "booked"


def test_two_unverified_drivers_race_and_cargo_stays_available():
    first = make_user("driver")
    second = make_user("driver")
    cargo = make_cargo()
    barrier = Barrier(2)

    def book(driver):
        client = _client_for_thread(driver)
        barrier.wait(timeout=10)
        return client.post(f"/api/cargos/{cargo.id}/book")

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(book, (first, second)))

    assert sorted(response.status_code for response in responses) == [403, 403]
    assert _confirmed(cargo.id) == []
    assert _status(cargo.id) == "available"


def test_exactly_one_confirmed_row_survives_a_race():
    first = make_verified_driver()
    second = make_verified_driver()
    cargo = make_cargo()

    # Sequential twin of the race: the second request must not add a row.
    assert _client_for_thread(first).post(
        f"/api/cargos/{cargo.id}/book"
    ).status_code == 201
    assert _client_for_thread(second).post(
        f"/api/cargos/{cargo.id}/book"
    ).status_code == 409

    rows = _confirmed(cargo.id)
    assert len(rows) == 1
    assert rows[0].cargo_id == cargo.id
