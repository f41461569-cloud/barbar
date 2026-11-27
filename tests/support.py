"""Shared helpers for the Phase 1 and registration-v2 test suites."""

from __future__ import annotations

import random
import string
import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Cargo, User, UserRole

PASSWORD = "secret123"


def new_phone() -> str:
    """Return a canonical Iranian mobile number that passes form validation."""
    suffix = "".join(random.choice(string.digits) for _ in range(9))
    return f"+989{suffix}"


def new_national_id() -> str:
    """Return a 10-digit national ID with a valid Iranian checksum."""
    digits = [random.randint(0, 9) for _ in range(9)]
    if len(set(digits)) == 1:
        digits[0] = (digits[0] + 1) % 10
    total = sum(digits[i] * (10 - i) for i in range(9)) % 11
    check = total if total < 2 else 11 - total
    return "".join(str(d) for d in digits) + str(check)


def new_license_number() -> str:
    return "L" + uuid.uuid4().hex[:10].upper()


def new_username() -> str:
    return "admin" + uuid.uuid4().hex[:8]


def new_plate_number() -> str:
    return f"{random.randint(10, 99)} ب {random.randint(100, 999)} ایران {random.randint(10, 99)}"


def driver_payload(**overrides) -> dict[str, str]:
    data = {
        "full_name": "Test Driver",
        "phone": new_phone(),
        "national_id": new_national_id(),
        "license_number": new_license_number(),
        "truck_type": "truck",
        "plate_number": new_plate_number(),
        "password": PASSWORD,
    }
    data.update(overrides)
    return data


def shipper_payload(**overrides) -> dict[str, str]:
    data = {
        "full_name": "Test Shipper",
        "phone": new_phone(),
        "cargo_type_preference": "general",
        "national_id": new_national_id(),
        "password": PASSWORD,
    }
    data.update(overrides)
    return data


def admin_payload(code: str, **overrides) -> dict[str, str]:
    """Admin form payload; ``admin_code=`` in overrides replaces ``code``."""

    data = {
        "username": new_username(),
        "password": PASSWORD,
        "admin_code": code,
    }
    data.update(overrides)
    return data


def register_driver(client: TestClient, **overrides):
    return client.post(
        "/auth/register/driver",
        data=driver_payload(**overrides),
        follow_redirects=False,
    )


def register_shipper(client: TestClient, **overrides):
    return client.post(
        "/auth/register/shipper",
        data=shipper_payload(**overrides),
        follow_redirects=False,
    )


def register_admin(client: TestClient, code: str, **overrides):
    return client.post(
        "/auth/register/admin",
        data=admin_payload(code, **overrides),
        follow_redirects=False,
    )


def login_user(client: TestClient, phone: str, password: str = PASSWORD):
    return client.post(
        "/auth/login",
        data={"phone": phone, "password": password},
        follow_redirects=False,
    )


def login_admin(
    client: TestClient,
    username: str,
    password: str = PASSWORD,
    admin_code: str = "",
):
    return client.post(
        "/auth/admin/login",
        data={
            "username": username,
            "password": password,
            "admin_code": admin_code,
        },
        follow_redirects=False,
    )


def make_user(
    role: str = "driver", *, name: str | None = None, **profile
) -> User:
    """Insert a user directly and return it detached.

    New profile columns are nullable, so most tests can ignore them. Admins get
    a username so the separate admin login can authenticate them.
    """
    suffix = uuid.uuid4().hex[:10]
    values = {
        "phone": profile.pop("phone", new_phone()),
        "name": name or f"{role}-{suffix}",
        "password_hash": hash_password(profile.pop("password", PASSWORD)),
        "role": UserRole(role),
    }
    if role == "admin":
        values["username"] = profile.pop("username", new_username())
    values.update(profile)

    db = SessionLocal()
    try:
        user = User(**values)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def auth_headers(user: User) -> dict[str, str]:
    payload = {"sub": str(user.id), "role": user.role.value}
    if user.phone:
        payload["phone"] = user.phone
    if getattr(user, "username", None):
        payload["username"] = user.username
    token = create_access_token(payload)
    return {"Authorization": f"Bearer {token}"}


def client_for(user: User | None = None, *, follow_redirects: bool = True) -> TestClient:
    from app.main import app

    client = TestClient(app, follow_redirects=follow_redirects)
    if user is not None:
        client.headers.update(auth_headers(user))
    return client


def make_verified_driver() -> User:
    """A driver whose license and national ID are both approved."""
    from app.models import DriverDocument

    admin = make_user("admin")
    driver = make_user("driver")
    db = SessionLocal()
    try:
        for doc_type in ("license", "national_id"):
            db.add(
                DriverDocument(
                    driver_id=driver.id,
                    doc_type=doc_type,
                    stored_path=f"documents/{driver.id}/{uuid.uuid4().hex}.pdf",
                    original_filename=f"{doc_type}.pdf",
                    content_type="application/pdf",
                    size_bytes=10,
                    status="approved",
                    reviewed_at=datetime.utcnow(),
                    reviewed_by_id=admin.id,
                )
            )
        db.commit()
    finally:
        db.close()
    return driver


def make_cargo(shipper: User | None = None, **overrides) -> Cargo:
    shipper = shipper or make_user("shipper")
    suffix = uuid.uuid4().hex[:8]
    values = {
        "title": f"cargo-{suffix}",
        "origin": f"origin-{suffix}",
        "destination": f"destination-{suffix}",
        "weight_kg": 1000.0,
        "price": 5_000_000.0,
        "status": "available",
    }
    values.update(overrides)
    db = SessionLocal()
    try:
        cargo = Cargo(shipper_id=shipper.id, **values)
        db.add(cargo)
        db.commit()
        db.refresh(cargo)
        db.expunge(cargo)
        return cargo
    finally:
        db.close()


def make_document(
    driver: User,
    doc_type: str = "license",
    status: str = "pending",
    **overrides,
):
    from app.models import DriverDocument

    values = {
        "driver_id": driver.id,
        "doc_type": doc_type,
        "stored_path": f"documents/{driver.id}/{uuid.uuid4().hex}.pdf",
        "original_filename": f"{doc_type}.pdf",
        "content_type": "application/pdf",
        "size_bytes": 10,
        "status": status,
    }
    values.update(overrides)
    db = SessionLocal()
    try:
        document = DriverDocument(**values)
        db.add(document)
        db.commit()
        db.refresh(document)
        db.expunge(document)
        return document
    finally:
        db.close()
