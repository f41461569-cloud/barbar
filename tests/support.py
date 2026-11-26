"""Shared helpers for the Phase 1 test suite."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth.security import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Cargo, User, UserRole

PASSWORD = "secret123"


def make_user(role: str = "driver", *, name: str | None = None) -> User:
    """Insert a user directly (admin cannot self-register) and return it detached."""
    suffix = uuid.uuid4().hex[:10]
    db = SessionLocal()
    try:
        user = User(
            phone=f"+9891{suffix}",
            name=name or f"{role}-{suffix}",
            password_hash=hash_password(PASSWORD),
            role=UserRole(role),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user.id), "phone": user.phone, "role": user.role.value}
    )
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
