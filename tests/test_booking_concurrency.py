"""Failing (RED) test for the booking feature.

Run against PostgreSQL:

    $env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
    pytest tests/test_booking_concurrency.py -v

The module is skipped unless DATABASE_URL is a PostgreSQL URL so SQLite can never silently
"validate" row locking.
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.models import Booking, TimeSlot, User, UserRole, Warehouse

DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL.lower().startswith(("postgres", "postgresql")),
    reason="Concurrency test requires PostgreSQL (set DATABASE_URL to a postgres URL).",
)


def _seed_slot():
    Base.metadata.create_all(bind=engine)
    suffix = uuid.uuid4().hex[:10]
    db = SessionLocal()
    try:
        warehouse = Warehouse(
            name=f"warehouse-{suffix}",
            address="Test address",
            timezone="Asia/Tehran",
        )
        driver_a = User(
            phone=f"a-{suffix}",
            name="Driver A",
            password_hash="$2b$12$svNQgwIH2dBuNt4wW3CMD.h/NAYyZBgtgI835ranH6flXYC9fBmLK",
            role=UserRole.DRIVER,
        )
        driver_b = User(
            phone=f"b-{suffix}",
            name="Driver B",
            password_hash="$2b$12$svNQgwIH2dBuNt4wW3CMD.h/NAYyZBgtgI835ranH6flXYC9fBmLK",
            role=UserRole.DRIVER,
        )
        db.add_all([warehouse, driver_a, driver_b])
        db.flush()

        now = datetime.utcnow()
        slot = TimeSlot(
            warehouse_id=warehouse.id,
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=1),
            capacity=1,
        )
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return {
            "slot_id": slot.id,
            "driver_ids": [driver_a.id, driver_b.id],
            "warehouse_id": warehouse.id,
        }
    finally:
        db.close()


def _cleanup(ids):
    db = SessionLocal()
    try:
        db.query(Booking).filter(Booking.time_slot_id == ids["slot_id"]).delete(
            synchronize_session=False
        )
        db.query(TimeSlot).filter(TimeSlot.id == ids["slot_id"]).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.id.in_(ids["driver_ids"])).delete(
            synchronize_session=False
        )
        db.query(Warehouse).filter(Warehouse.id == ids["warehouse_id"]).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def test_only_one_of_two_concurrent_bookings_succeeds():
    from app.main import app  # RED: the public endpoint does not exist yet.

    ids = _seed_slot()
    barrier = Barrier(2)

    def book(driver_id):
        # A separate client per thread avoids sharing TestClient's event-loop portal.
        client = TestClient(app)
        barrier.wait(timeout=10)
        return client.post(
            "/api/bookings",
            json={"time_slot_id": ids["slot_id"], "driver_id": driver_id},
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(book, ids["driver_ids"]))

        assert sorted(response.status_code for response in responses) == [200, 409], [
            response.text for response in responses
        ]
    finally:
        _cleanup(ids)


def test_booking_nonexistent_time_slot_is_not_success():
    from app.main import app  # RED: the public endpoint does not exist yet.

    ids = _seed_slot()
    try:
        response = TestClient(app).post(
            "/api/bookings",
            json={"time_slot_id": 2_147_483_647, "driver_id": ids["driver_ids"][0]},
        )
        assert response.status_code in (404, 409), response.text
        assert response.status_code != 200
    finally:
        _cleanup(ids)
