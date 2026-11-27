"""PostgreSQL-gated duplicate-registration race (PLAN-registration-v2 phase 4).

Two threads release on a barrier and submit the identical driver payload. The
unique indexes must let exactly one through; the loser must get a styled 409,
never a 500 or an unhandled IntegrityError.
"""

import os
import threading

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from tests.support import driver_payload

DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL.lower().startswith(("postgres", "postgresql")),
    reason="Concurrency test requires PostgreSQL.",
)


def test_concurrent_duplicate_registration_creates_one_row():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload()
    barrier = threading.Barrier(2)
    results: list = []
    lock = threading.Lock()

    def submit() -> None:
        client = TestClient(app, follow_redirects=False)
        barrier.wait(timeout=10)
        response = client.post("/auth/register/driver", data=payload)
        with lock:
            results.append(response)

    threads = [threading.Thread(target=submit) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    try:
        assert len(results) == 2, results
        statuses = sorted(response.status_code for response in results)
        assert statuses == [303, 409], [
            (response.status_code, response.text[:200]) for response in results
        ]
        for response in results:
            assert response.status_code != 500

        db = SessionLocal()
        try:
            assert (
                db.query(User).filter(User.phone == payload["phone"]).count() == 1
            )
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            db.query(User).filter(User.phone == payload["phone"]).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()
