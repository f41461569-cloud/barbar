"""RED/GREEN page tests for the Phase 1 UI (docs/SPEC-core.md §8).

Only the document pages are covered in this file for now; cargo and booking page
cases are appended in their own TDD cycles.
"""

from __future__ import annotations

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.models import DriverDocument
from tests.support import (
    client_for,
    make_cargo,
    make_document,
    make_user,
    make_verified_driver,
)

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Phase 1 page tests require PostgreSQL (set DATABASE_URL to a test URL).",
)

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"

VERIFICATION_LABELS = {
    "unverified": "تأیید نشده",
    "pending": "در انتظار بررسی",
    "verified": "تأیید شده",
    "rejected": "رد شده",
}
DOC_TYPE_LABELS = {"license": "گواهینامه", "national_id": "کارت ملی"}
UPLOAD_FLASH = "مدرک بارگذاری شد و در انتظار بررسی است."
REVIEW_FLASH = "وضعیت مدرک به‌روزرسانی شد."
FORBIDDEN = "شما به این بخش دسترسی ندارید."


def _upload_page(
    client: TestClient,
    *,
    doc_type: str = "license",
    name: str = "license.pdf",
    body: bytes = PDF,
    content_type: str = "application/pdf",
):
    return client.post(
        "/driver/documents",
        data={"doc_type": doc_type},
        files={"file": (name, body, content_type)},
    )


def _review_page(
    client: TestClient,
    document_id: int,
    *,
    decision: str = "approved",
    reason: str | None = None,
    version: int | None = 1,
):
    data: dict[str, str] = {"decision": decision}
    if reason is not None:
        data["reason"] = reason
    if version is not None:
        data["version"] = str(version)
    return client.post(f"/admin/documents/{document_id}/review", data=data)


# --------------------------------------------------------------------------- #
# /driver/documents
# --------------------------------------------------------------------------- #


def test_driver_documents_requires_driver_role(upload_dir):
    anonymous = client_for(None, follow_redirects=False)
    redirect = anonymous.get("/driver/documents")
    assert redirect.status_code == 303
    assert redirect.headers["location"] == "/auth/login"

    for role in ("shipper", "carrier", "admin"):
        response = client_for(make_user(role)).get("/driver/documents")
        assert response.status_code == 403, (role, response.text)
        assert 'role="alert"' in response.text
        assert FORBIDDEN in response.text


def test_driver_documents_renders_rtl_page_with_upload_form(upload_dir):
    driver = make_user("driver", name="Driver Page")
    response = client_for(driver).get("/driver/documents")

    assert response.status_code == 200, response.text
    body = response.text
    assert 'dir="rtl"' in body and 'lang="fa"' in body
    assert "مدارک راننده" in body
    assert VERIFICATION_LABELS["unverified"] in body

    assert 'enctype="multipart/form-data"' in body
    assert 'action="/driver/documents"' in body
    assert 'name="doc_type"' in body
    assert 'name="file"' in body
    assert 'type="file"' in body
    assert ".pdf,.jpg,.jpeg,.png" in body

    for doc_type, label in DOC_TYPE_LABELS.items():
        assert f'data-doc-row="{doc_type}"' in body
        assert label in body
        assert 'data-doc-status="missing"' in body

    assert 'role="alert"' not in body


def test_driver_documents_shows_each_type_status(upload_dir):
    driver = make_user("driver")
    make_document(driver, "license", status="approved")
    make_document(driver, "national_id", status="rejected", rejection_reason="ناخوانا")

    body = client_for(driver).get("/driver/documents").text

    assert VERIFICATION_LABELS["rejected"] in body
    assert "ناخوانا" in body
    assert 'data-doc-status="approved"' in body
    assert 'data-doc-status="rejected"' in body


def test_upload_page_redirects_with_flash(upload_dir):
    driver = make_user("driver")
    response = _upload_page(client_for(driver, follow_redirects=False))

    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/driver/documents?ok=uploaded"

    db = SessionLocal()
    try:
        document = db.query(DriverDocument).filter_by(driver_id=driver.id).one()
        assert document.status == "pending"
    finally:
        db.close()

    body = client_for(driver).get("/driver/documents?ok=uploaded").text
    assert UPLOAD_FLASH in body
    assert 'role="status"' in body


def test_upload_page_error_rerenders_with_alert(upload_dir):
    driver = make_user("driver")
    response = _upload_page(
        client_for(driver),
        name="evil.exe",
        body=b"MZ" + b"0" * 32,
        content_type="application/octet-stream",
    )

    assert response.status_code == 415, response.text
    assert 'role="alert"' in response.text
    assert "فقط PDF، JPG و PNG مجاز است." in response.text

    db = SessionLocal()
    try:
        assert db.query(DriverDocument).filter_by(driver_id=driver.id).count() == 0
    finally:
        db.close()


def test_unknown_flash_token_is_not_echoed(upload_dir):
    driver = make_user("driver")
    body = client_for(driver).get(
        "/driver/documents", params={"ok": "<script>alert(1)</script>"}
    ).text

    assert "<script>alert(1)</script>" not in body
    assert 'role="status"' not in body


# --------------------------------------------------------------------------- #
# /admin/documents
# --------------------------------------------------------------------------- #


def test_admin_documents_requires_admin(upload_dir):
    anonymous = client_for(None, follow_redirects=False)
    assert anonymous.get("/admin/documents").status_code == 303

    for role in ("driver", "shipper", "carrier"):
        response = client_for(make_user(role)).get("/admin/documents")
        assert response.status_code == 403, role
        assert FORBIDDEN in response.text


def test_admin_documents_lists_queue_without_phone(upload_dir):
    driver = make_user("driver", name="Queue Driver")
    admin = make_user("admin")
    document = make_document(driver, "license", status="pending")

    body = client_for(admin).get("/admin/documents").text

    assert "بررسی مدارک رانندگان" in body
    assert "Queue Driver" in body
    assert "گواهینامه" in body
    assert f"/api/documents/{document.id}/file" in body
    assert 'name="reason"' in body
    assert f'action="/admin/documents/{document.id}/review"' in body
    assert driver.phone not in body
    assert 'role="alert"' not in body


def test_admin_documents_status_filter(upload_dir):
    driver = make_user("driver")
    admin = make_user("admin")
    pending = make_document(driver, "license", status="pending")
    approved = make_document(driver, "national_id", status="approved")

    default_body = client_for(admin).get("/admin/documents").text
    assert f'action="/admin/documents/{pending.id}/review"' in default_body
    assert f'action="/admin/documents/{approved.id}/review"' not in default_body

    everything = client_for(admin).get(
        "/admin/documents", params={"status": "all"}
    ).text
    assert f'action="/admin/documents/{pending.id}/review"' in everything
    assert f'action="/admin/documents/{approved.id}/review"' in everything


def test_admin_review_page_redirects_and_flashes(upload_dir):
    driver = make_user("driver")
    admin = make_user("admin")
    document = make_document(driver, "license", status="pending")

    response = _review_page(
        client_for(admin, follow_redirects=False), document.id
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/admin/documents?ok=reviewed"

    db = SessionLocal()
    try:
        assert db.get(DriverDocument, document.id).status == "approved"
    finally:
        db.close()

    body = client_for(admin).get("/admin/documents?ok=reviewed").text
    assert REVIEW_FLASH in body
    assert 'role="status"' in body


def test_admin_review_page_requires_reason(upload_dir):
    driver = make_user("driver")
    admin = make_user("admin")
    document = make_document(driver, "license", status="pending")

    response = _review_page(
        client_for(admin), document.id, decision="rejected"
    )

    assert response.status_code == 422, response.text
    assert 'role="alert"' in response.text
    assert "برای رد مدرک، دلیل را وارد کنید." in response.text

    db = SessionLocal()
    try:
        assert db.get(DriverDocument, document.id).status == "pending"
    finally:
        db.close()


def test_admin_review_page_version_conflict(upload_dir):
    driver = make_user("driver")
    admin = make_user("admin")
    document = make_document(driver, "license", status="pending", version=2)

    response = _review_page(client_for(admin), document.id, version=1)

    assert response.status_code == 409, response.text
    assert 'role="alert"' in response.text
    assert "تغییر کرده است" in response.text

    db = SessionLocal()
    try:
        assert db.get(DriverDocument, document.id).status == "pending"
    finally:
        db.close()


def test_admin_review_missing_document_returns_404_page(upload_dir):
    admin = make_user("admin")
    response = _review_page(client_for(admin), 2147483647)

    assert response.status_code == 404
    assert "مدرک مورد نظر یافت نشد." in response.text


def test_admin_page_rejects_invalid_status_filter(upload_dir):
    admin = make_user("admin")
    response = client_for(admin).get(
        "/admin/documents", params={"status": "deleted"}
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# /cargos (driver list)
# --------------------------------------------------------------------------- #


def test_cargos_page_requires_authentication():
    response = client_for(None, follow_redirects=False).get("/cargos")
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


@pytest.mark.parametrize("role", ["shipper", "carrier", "admin"])
def test_cargos_page_is_readable_by_every_role(role):
    make_cargo()
    response = client_for(make_user(role)).get("/cargos")
    assert response.status_code == 200, role


def test_cargos_page_lists_available_and_hides_booked(upload_dir):
    shipper = make_user("shipper")
    marker = uuid.uuid4().hex[:8]
    available = make_cargo(
        shipper=shipper,
        origin=f"Tehran {marker}",
        destination=f"Mashhad {marker}",
        title=f"Cargo {marker}",
    )
    booked = make_cargo(
        shipper=shipper,
        origin=f"Tehran {marker}",
        destination=f"Mashhad {marker}",
        title=f"Booked {marker}",
        status="booked",
    )

    body = client_for(make_user("shipper")).get(
        "/cargos", params={"origin": marker}
    ).text

    assert f'data-cargo-id="{available.id}"' in body
    assert f'data-cargo-id="{booked.id}"' not in body
    assert available.title in body
    assert available.origin in body and available.destination in body

    for field in (
        "origin",
        "destination",
        "min_weight",
        "max_weight",
        "min_price",
        "max_price",
    ):
        assert f'name="{field}"' in body, field


def test_cargos_page_applies_filters(upload_dir):
    shipper = make_user("shipper")
    marker = uuid.uuid4().hex[:8]
    match = make_cargo(
        shipper=shipper, origin=f"Origin {marker}", title=f"Match {marker}"
    )
    other = make_cargo(
        shipper=shipper, origin=f"Origin {marker}", title=f"Other {marker}"
    )

    body = client_for(make_user("driver")).get(
        "/cargos", params={"origin": marker, "min_weight": 2000}
    ).text

    # Both default fixtures weigh 1000 kg, so the weight filter excludes both.
    assert f'data-cargo-id="{match.id}"' not in body
    assert f'data-cargo-id="{other.id}"' not in body

    body = client_for(make_user("driver")).get(
        "/cargos", params={"origin": marker, "max_weight": 1000}
    ).text
    assert f'data-cargo-id="{match.id}"' in body
    assert f'data-cargo-id="{other.id}"' in body


def test_unverified_driver_gets_notice_instead_of_book_action(upload_dir):
    cargo = make_cargo()
    driver = make_user("driver")

    body = client_for(driver).get(
        "/cargos", params={"origin": cargo.origin}
    ).text

    assert "برای رزرو بار، ابتدا مدارک شما باید تأیید شود." in body
    assert 'href="/driver/documents"' in body
    assert f'action="/cargos/{cargo.id}/book"' not in body


def test_verified_driver_sees_book_action(upload_dir):
    cargo = make_cargo()
    driver = make_verified_driver()

    body = client_for(driver).get(
        "/cargos", params={"origin": cargo.origin}
    ).text

    assert f'action="/cargos/{cargo.id}/book"' in body
    assert "رزرو" in body


# --------------------------------------------------------------------------- #
# /shipper/cargos
# --------------------------------------------------------------------------- #


def test_shipper_cargos_role_gate(upload_dir):
    anonymous = client_for(None, follow_redirects=False)
    assert anonymous.get("/shipper/cargos").status_code == 303

    for role in ("driver", "carrier", "admin"):
        response = client_for(make_user(role)).get("/shipper/cargos")
        assert response.status_code == 403, role
        assert FORBIDDEN in response.text


def test_shipper_cargos_lists_only_own_cargos(upload_dir):
    shipper = make_user("shipper")
    other = make_user("shipper")
    own = make_cargo(shipper=shipper, title=f"Own {uuid.uuid4().hex[:6]}")
    foreign = make_cargo(shipper=other, title=f"Foreign {uuid.uuid4().hex[:6]}")

    body = client_for(shipper).get("/shipper/cargos").text

    assert own.title in body
    assert foreign.title not in body
    assert "بارهای من" in body


def test_shipper_cargo_new_form_contract(upload_dir):
    response = client_for(make_user("shipper")).get("/shipper/cargos/new")
    assert response.status_code == 200, response.text
    body = response.text

    for field in ("title", "origin", "destination", "weight_kg", "price"):
        assert f'name="{field}"' in body, field
        assert f'id="{field}"' in body, field
        assert f'for="{field}"' in body, field

    assert 'action="/shipper/cargos/new"' in body
    assert 'role="alert"' not in body


def test_shipper_cargo_new_role_gate(upload_dir):
    anonymous = client_for(None, follow_redirects=False)
    assert anonymous.get("/shipper/cargos/new").status_code == 303

    for role in ("driver", "carrier", "admin"):
        response = client_for(make_user(role)).get("/shipper/cargos/new")
        assert response.status_code == 403, role


def test_shipper_creates_cargo_through_page(upload_dir):
    shipper = make_user("shipper")
    payload = {
        "title": "بار صفحه‌ای",
        "origin": "تهران",
        "destination": "اصفهان",
        "weight_kg": "2500",
        "price": "15000000",
    }

    response = client_for(shipper, follow_redirects=False).post(
        "/shipper/cargos/new", data=payload
    )

    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/shipper/cargos?ok=created"

    body = client_for(shipper).get("/shipper/cargos?ok=created").text
    assert "بار جدید ثبت شد." in body
    assert 'role="status"' in body
    assert payload["title"] in body


def test_shipper_cargo_form_error_preserves_values(upload_dir):
    shipper = make_user("shipper")
    payload = {
        "title": "بار نامعتبر",
        "origin": "تهران",
        "destination": "اصفهان",
        "weight_kg": "0",
        "price": "15000000",
    }

    response = client_for(shipper).post("/shipper/cargos/new", data=payload)

    assert response.status_code == 422, response.text
    body = response.text
    assert 'role="alert"' in body
    assert 'value="بار نامعتبر"' in body
    weight_input = re.search(r'<input[^>]*name="weight_kg"[^>]*>', body)
    assert weight_input is not None
    assert 'aria-invalid="true"' in weight_input.group(0)
    assert 'aria-invalid="true"' not in re.search(
        r'<input[^>]*name="title"[^>]*>', body
    ).group(0)


def test_dashboard_cargo_link_and_quick_links(upload_dir):
    driver = make_user("driver")
    body = client_for(driver).get("/dashboard").text
    assert 'href="/cargos"' in body
    assert 'data-future-route="/cargos"' not in body
    assert 'data-future-route="/time-slots"' in body
    assert 'data-future-route="/bol"' in body
    assert 'data-quick-link="driver-documents"' in body
    assert 'href="/driver/documents"' in body

    shipper_body = client_for(make_user("shipper")).get("/dashboard").text
    assert 'data-quick-link="shipper-cargos"' in shipper_body
    assert 'data-quick-link="shipper-cargo-new"' in shipper_body

    admin_body = client_for(make_user("admin")).get("/dashboard").text
    assert 'data-quick-link="admin-documents"' in admin_body

    carrier_body = client_for(make_user("carrier")).get("/dashboard").text
    assert "data-quick-links" not in carrier_body


# --------------------------------------------------------------------------- #
# Booking page
# --------------------------------------------------------------------------- #


def test_book_page_success_redirects_and_flashes(upload_dir):
    driver = make_verified_driver()
    cargo = make_cargo()

    response = client_for(driver, follow_redirects=False).post(
        f"/cargos/{cargo.id}/book"
    )

    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/cargos?ok=booked"

    body = client_for(driver).get("/cargos?ok=booked").text
    assert "بار با موفقیت رزرو شد." in body
    assert 'role="status"' in body

    db = SessionLocal()
    try:
        from app.models import Cargo

        assert db.get(Cargo, cargo.id).status == "booked"
    finally:
        db.close()

    listing = client_for(driver).get(
        "/cargos", params={"origin": cargo.origin}
    ).text
    assert f'data-cargo-id="{cargo.id}"' not in listing


def test_book_page_conflict_rerenders_with_alert(upload_dir):
    first = make_verified_driver()
    second = make_verified_driver()
    cargo = make_cargo()

    assert client_for(first).post(
        f"/api/cargos/{cargo.id}/book"
    ).status_code == 201

    response = client_for(second).post(f"/cargos/{cargo.id}/book")

    assert response.status_code == 409, response.text
    assert 'role="alert"' in response.text
    assert "این بار در همین لحظه توسط راننده دیگری رزرو شد." in response.text


def test_book_page_unverified_driver_gets_403_notice(upload_dir):
    driver = make_user("driver")
    cargo = make_cargo()

    response = client_for(driver).post(f"/cargos/{cargo.id}/book")

    assert response.status_code == 403, response.text
    assert 'role="alert"' in response.text
    assert "برای رزرو بار، ابتدا مدارک شما باید تأیید شود." in response.text

    db = SessionLocal()
    try:
        from app.models import Cargo

        assert db.get(Cargo, cargo.id).status == "available"
    finally:
        db.close()


def test_book_page_role_gates(upload_dir):
    cargo = make_cargo()

    anonymous = client_for(None, follow_redirects=False).post(
        f"/cargos/{cargo.id}/book"
    )
    assert anonymous.status_code == 303
    assert anonymous.headers["location"] == "/auth/login"

    for role in ("shipper", "carrier", "admin"):
        response = client_for(make_user(role)).post(
            f"/cargos/{cargo.id}/book"
        )
        assert response.status_code == 403, role
        assert FORBIDDEN in response.text

