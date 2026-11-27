"""RED/GREEN tests for registration v2 and login (ADR 007).

Run against PostgreSQL:

    $env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
    pytest tests/test_auth.py -v

Skipped unless DATABASE_URL is a PostgreSQL URL, matching the other DB tests.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.auth.security import hash_password
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User, UserRole
from tests.support import (
    PASSWORD,
    admin_payload,
    driver_payload,
    login_admin,
    login_user,
    make_user,
    new_license_number,
    new_national_id,
    new_phone,
    new_username,
    register_admin,
    register_driver,
    register_shipper,
    shipper_payload,
)

DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL.lower().startswith(("postgres", "postgresql")),
    reason="Auth tests require PostgreSQL (set DATABASE_URL to a postgres URL).",
)


def _client(follow_redirects: bool = False) -> TestClient:
    return TestClient(app, follow_redirects=follow_redirects)


def _cleanup(*phones, usernames=()):
    db = SessionLocal()
    try:
        if phones:
            db.query(User).filter(User.phone.in_(phones)).delete(
                synchronize_session=False
            )
        if usernames:
            db.query(User).filter(User.username.in_(usernames)).delete(
                synchronize_session=False
            )
        db.commit()
    finally:
        db.close()


def _user_by_phone(phone: str) -> User | None:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.phone == phone).one_or_none()
    finally:
        db.close()


def _user_by_username(username: str) -> User | None:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).one_or_none()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #


def test_user_model_has_registration_columns():
    Base.metadata.create_all(bind=engine)
    columns = User.__table__.columns
    for name in (
        "username",
        "national_id",
        "license_number",
        "truck_type",
        "plate_number",
        "cargo_type_preference",
    ):
        assert name in columns, name
    assert columns.phone.nullable is True


def test_admin_can_have_null_phone():
    Base.metadata.create_all(bind=engine)
    username = new_username()
    db = SessionLocal()
    try:
        user = User(
            phone=None,
            name=username,
            password_hash=hash_password(PASSWORD),
            role=UserRole.ADMIN,
            username=username,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.id is not None
        assert user.phone is None
    finally:
        db.rollback()
        db.close()
        _cleanup(usernames=(username,))


def test_admin_code_is_not_a_user_column():
    assert "admin_code" not in User.__table__.columns


def test_unique_indexes_are_declared():
    indexes = {index.name for index in inspect(User).local_table.indexes}
    assert "ix_users_username" in indexes
    assert "ix_users_national_id" in indexes
    assert "ix_users_license_number" in indexes
    assert "ix_users_plate_number" in indexes


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


def test_register_driver_success():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload(full_name="  Ali   Driver  ", phone="09121234567")
    try:
        response = _client().post("/auth/register/driver", data=payload)
        assert response.status_code == 303, response.text
        assert response.headers["location"] == "/auth/register/success?role=driver"

        user = _user_by_phone("+989121234567")
        assert user is not None
        assert user.name == "Ali Driver"
        assert user.role == UserRole.DRIVER
        assert user.national_id == payload["national_id"]
        assert user.license_number == payload["license_number"].upper()
        assert user.truck_type == "truck"
        assert user.plate_number
        assert user.password_hash != payload["password"]
    finally:
        _cleanup("+989121234567")


def test_register_shipper_success():
    Base.metadata.create_all(bind=engine)
    payload = shipper_payload(full_name="  Sara   Shipper  ")
    try:
        response = _client().post("/auth/register/shipper", data=payload)
        assert response.status_code == 303, response.text
        assert response.headers["location"] == "/auth/register/success?role=shipper"

        user = _user_by_phone(payload["phone"])
        assert user is not None
        assert user.name == "Sara Shipper"
        assert user.role == UserRole.SHIPPER
        assert user.national_id == payload["national_id"]
        assert user.cargo_type_preference == "general"
        assert user.password_hash != payload["password"]
    finally:
        _cleanup(payload["phone"])


def test_register_admin_success(admin_code):
    Base.metadata.create_all(bind=engine)
    username = f"admin.{uuid.uuid4().hex[:8]}"
    try:
        response = register_admin(_client(), admin_code, username=f"  {username}  ")
        assert response.status_code == 303, response.text
        assert response.headers["location"] == "/auth/register/success?role=admin"

        user = _user_by_username(username)
        assert user is not None
        assert user.phone is None
        assert user.name == username
        assert user.role == UserRole.ADMIN
        assert user.password_hash != PASSWORD
    finally:
        _cleanup(usernames=(username,))


def test_register_admin_wrong_code(admin_code):
    Base.metadata.create_all(bind=engine)
    username = new_username()
    try:
        response = register_admin(
            _client(), admin_code, username=username, admin_code="wrong-code"
        )
        assert response.status_code == 401, response.text
        assert "کد مدیریت نادرست است." in response.text
        assert _user_by_username(username) is None
    finally:
        _cleanup(usernames=(username,))


def test_register_admin_disabled(admin_code, monkeypatch):
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "ADMIN_CODE", "")
    username = new_username()
    try:
        response = register_admin(_client(), admin_code, username=username)
        assert response.status_code == 503, response.text
        assert "ورود مدیران در حال حاضر فعال نیست." in response.text
        assert _user_by_username(username) is None
    finally:
        _cleanup(usernames=(username,))


def test_duplicate_phone_returns_409():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload()
    try:
        assert (
            _client().post("/auth/register/driver", data=payload).status_code == 303
        )
        second = _client().post(
            "/auth/register/driver",
            data=driver_payload(phone=payload["phone"]),
        )
        assert second.status_code == 409, second.text
        assert "این شماره تلفن قبلاً ثبت شده است." in second.text

        db = SessionLocal()
        try:
            assert db.query(User).filter(User.phone == payload["phone"]).count() == 1
        finally:
            db.close()
    finally:
        _cleanup(payload["phone"])


def test_duplicate_national_id_returns_409():
    Base.metadata.create_all(bind=engine)
    first = driver_payload()
    second = driver_payload(
        phone=new_phone(), national_id=first["national_id"]
    )
    try:
        assert _client().post("/auth/register/driver", data=first).status_code == 303
        response = _client().post("/auth/register/driver", data=second)
        assert response.status_code == 409, response.text
        assert "این کد ملی قبلاً ثبت شده است." in response.text
    finally:
        _cleanup(first["phone"], second["phone"])


def test_duplicate_license_returns_409():
    Base.metadata.create_all(bind=engine)
    first = driver_payload()
    second = driver_payload(
        phone=new_phone(), license_number=first["license_number"]
    )
    try:
        assert _client().post("/auth/register/driver", data=first).status_code == 303
        response = _client().post("/auth/register/driver", data=second)
        assert response.status_code == 409, response.text
        assert "این شماره گواهینامه قبلاً ثبت شده است." in response.text
    finally:
        _cleanup(first["phone"], second["phone"])


def test_duplicate_username_returns_409(admin_code):
    Base.metadata.create_all(bind=engine)
    username = new_username()
    try:
        assert (
            register_admin(_client(), admin_code, username=username).status_code
            == 303
        )
        response = register_admin(_client(), admin_code, username=username)
        assert response.status_code == 409, response.text
        assert "این نام کاربری قبلاً ثبت شده است." in response.text
    finally:
        _cleanup(usernames=(username,))


def test_invalid_national_id_returns_html_422():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload(national_id="1234567890")
    try:
        response = _client().post("/auth/register/driver", data=payload)
        assert response.status_code == 422, response.text
        assert 'role="alert"' in response.text
        assert 'aria-invalid="true"' in response.text
        assert "کد ملی معتبر نیست." in response.text
        assert _user_by_phone(payload["phone"]) is None
    finally:
        _cleanup(payload["phone"])


def test_invalid_phone_returns_html_422():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload(phone="0212345678")
    response = _client().post("/auth/register/driver", data=payload)
    assert response.status_code == 422, response.text
    assert "شماره تلفن معتبر نیست." in response.text
    assert _user_by_phone(payload["phone"]) is None


def test_error_preserves_values_and_never_echoes_password():
    Base.metadata.create_all(bind=engine)
    first = driver_payload()
    submitted_password = "never-echo-this-password"
    second = driver_payload(
        phone=first["phone"],
        full_name="Preserved Name",
        password=submitted_password,
    )
    try:
        assert _client().post("/auth/register/driver", data=first).status_code == 303
        response = _client().post("/auth/register/driver", data=second)
        assert response.status_code == 409, response.text
        assert "Preserved Name" in response.text
        assert first["phone"] in response.text
        assert submitted_password not in response.text
    finally:
        _cleanup(first["phone"])


def test_legacy_register_post_is_405():
    response = _client().post(
        "/auth/register",
        data={"phone": new_phone(), "name": "Old", "password": PASSWORD, "role": "driver"},
    )
    assert response.status_code == 405, response.text


def test_carrier_registration_is_absent():
    assert _client().get("/auth/register/carrier").status_code == 404


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #


def test_login_success_sets_cookie():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload()
    try:
        assert _client().post("/auth/register/driver", data=payload).status_code == 303

        client = _client()
        response = login_user(client, payload["phone"], payload["password"])
        assert response.status_code == 303, response.text
        assert response.headers["location"] == "/dashboard"

        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie, set_cookie
        assert "httponly" in set_cookie.lower(), set_cookie
        assert client.cookies.get("access_token")
    finally:
        _cleanup(payload["phone"])


def test_login_wrong_password_returns_401():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload()
    try:
        assert _client().post("/auth/register/driver", data=payload).status_code == 303
        response = login_user(_client(), payload["phone"], "definitely-wrong")
        assert response.status_code == 401, response.text
        assert "شماره تلفن یا رمز عبور نادرست است." in response.text
        assert "set-cookie" not in response.headers
    finally:
        _cleanup(payload["phone"])


def test_login_unknown_phone_returns_401():
    response = login_user(_client(), new_phone())
    assert response.status_code == 401
    assert "شماره تلفن یا رمز عبور نادرست است." in response.text


def test_admin_cannot_use_user_login():
    Base.metadata.create_all(bind=engine)
    admin = make_user("admin")
    try:
        response = login_user(_client(), admin.phone)
        assert response.status_code == 401, response.text
        assert "set-cookie" not in response.headers
    finally:
        _cleanup(admin.phone, usernames=(admin.username,))


def test_admin_login_success(admin_code):
    Base.metadata.create_all(bind=engine)
    username = new_username()
    try:
        assert (
            register_admin(_client(), admin_code, username=username).status_code
            == 303
        )
        client = _client()
        response = login_admin(client, username, PASSWORD, admin_code)
        assert response.status_code == 303, response.text
        assert response.headers["location"] == "/dashboard"
        assert "access_token=" in response.headers.get("set-cookie", "")
        assert client.cookies.get("access_token")
    finally:
        _cleanup(usernames=(username,))


def test_admin_login_wrong_code_returns_401(admin_code):
    Base.metadata.create_all(bind=engine)
    username = new_username()
    try:
        assert (
            register_admin(_client(), admin_code, username=username).status_code
            == 303
        )
        response = login_admin(_client(), username, PASSWORD, "wrong-code")
        assert response.status_code == 401, response.text
        assert "نام کاربری، رمز عبور یا کد مدیریت نادرست است." in response.text
        assert "set-cookie" not in response.headers
    finally:
        _cleanup(usernames=(username,))


def test_admin_login_rejects_non_admin(admin_code):
    Base.metadata.create_all(bind=engine)
    driver = driver_payload()
    try:
        assert (
            _client().post("/auth/register/driver", data=driver).status_code == 303
        )
        response = login_admin(
            _client(), driver["phone"], driver["password"], admin_code
        )
        assert response.status_code == 401, response.text
        assert "set-cookie" not in response.headers
    finally:
        _cleanup(driver["phone"])


def test_admin_login_legacy_phone_fallback(admin_code):
    Base.metadata.create_all(bind=engine)
    phone = new_phone()
    db = SessionLocal()
    try:
        db.add(
            User(
                phone=phone,
                name="Legacy Admin",
                password_hash=hash_password(PASSWORD),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
    finally:
        db.close()
    try:
        response = login_admin(_client(), phone, PASSWORD, admin_code)
        assert response.status_code == 303, response.text
        assert response.headers["location"] == "/dashboard"
    finally:
        _cleanup(phone)


def test_logout_clears_cookie():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload()
    try:
        assert _client().post("/auth/register/driver", data=payload).status_code == 303
        client = _client()
        assert login_user(client, payload["phone"]).status_code == 303
        assert client.cookies.get("access_token")

        response = client.post("/auth/logout", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/auth/login"
        set_cookie = response.headers.get("set-cookie", "").lower()
        assert "access_token=" in set_cookie
        assert "max-age=0" in set_cookie or "expires=" in set_cookie
        assert not client.cookies.get("access_token")
    finally:
        _cleanup(payload["phone"])


# --------------------------------------------------------------------------- #
# Success page
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "role,message,link",
    [
        ("driver", "حساب راننده ساخته شد", "/auth/login"),
        ("shipper", "حساب صاحب کالا ساخته شد", "/auth/login"),
        ("admin", "حساب مدیر ساخته شد", "/auth/admin/login"),
    ],
)
def test_success_page_roles(role, message, link):
    response = _client(follow_redirects=True).get(
        f"/auth/register/success?role={role}"
    )
    assert response.status_code == 200, response.text
    assert message in response.text
    assert f'href="{link}"' in response.text


def test_unknown_success_role_returns_404():
    assert (
        _client().get("/auth/register/success?role=carrier").status_code == 404
    )
