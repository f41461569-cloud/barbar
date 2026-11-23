"""Failing (RED) TDD tests for login/registration.

Run against PostgreSQL:

    $env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
    pytest tests/test_auth.py -v

Skipped unless DATABASE_URL is a PostgreSQL URL, matching tests/test_booking_concurrency.py.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.models import User

DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL.lower().startswith(("postgres", "postgresql")),
    reason="Auth tests require PostgreSQL (set DATABASE_URL to a postgres URL).",
)

PASSWORD = "secret123"


def _new_phone():
    return "+9891" + uuid.uuid4().hex[:9]


def _cleanup(*phones):
    db = SessionLocal()
    try:
        db.query(User).filter(User.phone.in_(phones)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _register(client, phone, role="driver", password=PASSWORD):
    return client.post(
        "/auth/register",
        data={
            "phone": phone,
            "name": "Test User",
            "password": password,
            "role": role,
        },
    )


def test_register_success():
    from app.main import app  # RED: auth routes do not exist yet.

    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    client = TestClient(app)
    try:
        response = _register(client, phone)
        assert response.status_code in (200, 201), response.text

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone == phone).one_or_none()
        finally:
            db.close()
        assert user is not None
    finally:
        _cleanup(phone)


def test_register_duplicate_phone():
    from app.main import app  # RED: auth routes do not exist yet.

    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    client = TestClient(app)
    try:
        first = _register(client, phone)
        assert first.status_code in (200, 201), first.text

        second = _register(client, phone)
        assert second.status_code == 409, second.text
    finally:
        _cleanup(phone)


def test_login_wrong_password():
    from app.main import app  # RED: auth routes do not exist yet.

    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    client = TestClient(app)
    try:
        assert _register(client, phone).status_code in (200, 201)

        response = client.post(
            "/auth/login",
            data={"phone": phone, "password": "definitely-wrong"},
        )
        assert response.status_code == 401, response.text
    finally:
        _cleanup(phone)


def test_login_success_sets_cookie():
    from app.main import app  # RED: auth routes do not exist yet.

    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    register_client = TestClient(app)
    client = TestClient(app, follow_redirects=False)
    try:
        assert _register(register_client, phone).status_code in (200, 201)

        response = client.post(
            "/auth/login",
            data={"phone": phone, "password": PASSWORD},
        )
        # 303 See Other is the post-login contract (ADR 004); 302/307 kept for compatibility.
        assert response.status_code in (302, 303, 307), response.text
        assert response.headers.get("location") == "/dashboard"

        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie, set_cookie
        # Separate, explicit HttpOnly assertion (SPEC-auth.md / ADR 003).
        assert "httponly" in set_cookie.lower(), set_cookie
        assert client.cookies.get("access_token")
    finally:
        _cleanup(phone)


def test_password_not_plaintext():
    from app.main import app  # RED: auth routes do not exist yet.

    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    client = TestClient(app)
    try:
        assert _register(client, phone).status_code in (200, 201)

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone == phone).one_or_none()
            assert user is not None
            assert user.password_hash != PASSWORD
            assert user.password_hash
        finally:
            db.close()
    finally:
        _cleanup(phone)
