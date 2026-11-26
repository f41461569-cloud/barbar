"""RED tests for driver document upload and admin verification (docs/SPEC-core.md §5.1, §7.2)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.models import DriverDocument
from tests.support import client_for, make_user

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Document tests require PostgreSQL (set DATABASE_URL to a PostgreSQL test URL).",
)

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
TOO_BIG = b"%PDF-" + b"x" * (5 * 1024 * 1024)


def _upload(
    client,
    *,
    doc_type: str = "license",
    name: str = "license.pdf",
    body: bytes = PDF,
    content_type: str = "application/pdf",
):
    return client.post(
        "/api/drivers/me/documents",
        data={"doc_type": doc_type},
        files={"file": (name, body, content_type)},
    )


def _review(client, doc_id, *, decision="approved", reason=None, version=None):
    payload = {"decision": decision}
    if reason is not None:
        payload["reason"] = reason
    if version is not None:
        payload["version"] = version
    return client.post(f"/api/admin/documents/{doc_id}/review", json=payload)


def _code(response):
    return response.json()["detail"]["code"]


def test_upload_pdf_creates_pending_document(upload_dir):
    driver = make_user("driver")

    response = _upload(client_for(driver))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["driver_id"] == driver.id
    assert body["doc_type"] == "license"
    assert body["status"] == "pending"
    assert body["version"] == 1
    assert body["original_filename"] == "license.pdf"
    assert body["rejection_reason"] is None
    assert body["reviewed_at"] is None
    assert "stored_path" not in body

    db = SessionLocal()
    try:
        document = (
            db.query(DriverDocument)
            .filter_by(driver_id=driver.id, doc_type="license")
            .one()
        )
        path = Path(upload_dir) / document.stored_path
        assert path.is_file()
        assert path.read_bytes() == PDF
        assert document.stored_path.startswith(f"documents/{driver.id}/")
        assert document.stored_path.endswith(".pdf")
    finally:
        db.close()


def test_reupload_replaces_in_place_and_resets_review(upload_dir):
    driver = make_user("driver")
    admin = make_user("admin")
    driver_client = client_for(driver)
    first = _upload(driver_client).json()

    approved = _review(client_for(admin), first["id"], decision="approved", version=1)
    assert approved.status_code == 200, approved.text

    db = SessionLocal()
    try:
        before = db.get(DriverDocument, first["id"])
        old_path = Path(upload_dir) / before.stored_path
    finally:
        db.close()
    assert old_path.is_file()

    second = _upload(
        driver_client, name="license-v2.pdf", body=PDF + b"v2"
    )

    assert second.status_code == 200, second.text
    body = second.json()
    assert body["id"] == first["id"]
    assert body["version"] == 2
    assert body["status"] == "pending"
    assert body["rejection_reason"] is None
    assert body["reviewed_at"] is None
    assert body["original_filename"] == "license-v2.pdf"
    assert not old_path.exists()

    db = SessionLocal()
    try:
        after = db.get(DriverDocument, first["id"])
        new_path = Path(upload_dir) / after.stored_path
        assert new_path.is_file()
        assert new_path != old_path
        assert after.reviewed_by_id is None
        assert (
            db.query(DriverDocument)
            .filter_by(driver_id=driver.id, doc_type="license")
            .count()
            == 1
        )
    finally:
        db.close()


@pytest.mark.parametrize(
    "case,status,code",
    [
        ("too_big", 413, "file_too_large"),
        ("unsupported", 415, "unsupported_file_type"),
        ("mismatch", 415, "unsupported_file_type"),
        ("empty", 422, "invalid_file"),
        ("bad_type", 422, "invalid_doc_type"),
    ],
)
def test_upload_validation(upload_dir, case, status, code):
    driver = make_user("driver")
    client = client_for(driver)

    if case == "too_big":
        response = _upload(client, body=TOO_BIG)
    elif case == "unsupported":
        response = _upload(
            client,
            name="evil.exe",
            body=b"MZ" + b"0" * 32,
            content_type="application/octet-stream",
        )
    elif case == "mismatch":
        response = _upload(
            client, name="fake.pdf", body=PNG, content_type="application/pdf"
        )
    elif case == "empty":
        response = _upload(client, body=b"")
    else:
        response = _upload(client, doc_type="passport")

    assert response.status_code == status, response.text
    assert _code(response) == code

    db = SessionLocal()
    try:
        assert db.query(DriverDocument).filter_by(driver_id=driver.id).count() == 0
    finally:
        db.close()


def test_upload_is_driver_only(upload_dir):
    assert _upload(client_for(None)).status_code == 401
    assert _upload(client_for(make_user("shipper"))).status_code == 403
    assert _upload(client_for(make_user("admin"))).status_code == 403


def test_verification_requires_both_documents_approved(upload_dir):
    driver = make_user("driver")
    admin_client = client_for(make_user("admin"))
    driver_client = client_for(driver)

    assert (
        driver_client.get("/api/drivers/me/documents").json()["verification_status"]
        == "unverified"
    )

    license_doc = _upload(driver_client, doc_type="license").json()
    national_id = _upload(
        driver_client,
        doc_type="national_id",
        name="national-id.png",
        body=PNG,
        content_type="image/png",
    ).json()

    assert (
        driver_client.get("/api/drivers/me/documents").json()["verification_status"]
        == "pending"
    )

    assert _review(admin_client, license_doc["id"], version=1).status_code == 200
    assert (
        driver_client.get("/api/drivers/me/documents").json()["verification_status"]
        == "pending"
    )

    assert _review(admin_client, national_id["id"], version=1).status_code == 200
    assert (
        driver_client.get("/api/drivers/me/documents").json()["verification_status"]
        == "verified"
    )

    rejected = _review(
        admin_client,
        license_doc["id"],
        decision="rejected",
        reason="تصویر ناخوانا است",
        version=1,
    )
    assert rejected.status_code == 200, rejected.text
    assert (
        driver_client.get("/api/drivers/me/documents").json()["verification_status"]
        == "rejected"
    )


def test_admin_queue_is_role_gated_and_hides_pii(upload_dir):
    driver = make_user("driver", name="Driver Queue")
    admin = make_user("admin")
    document = _upload(client_for(driver)).json()

    response = client_for(admin).get(
        "/api/admin/documents",
        params={"status": "pending", "driver_id": driver.id},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    item = next(item for item in body["items"] if item["id"] == document["id"])
    assert item["driver_name"] == "Driver Queue"
    assert "phone" not in item
    assert "stored_path" not in item

    assert client_for(driver).get("/api/admin/documents").status_code == 403
    assert client_for(None).get("/api/admin/documents").status_code == 401


def test_admin_queue_defaults_to_pending(upload_dir):
    driver = make_user("driver")
    admin = make_user("admin")
    pending = _upload(client_for(driver)).json()
    approved = _upload(
        client_for(driver), doc_type="national_id", name="national-id.pdf"
    ).json()
    assert _review(client_for(admin), approved["id"], version=1).status_code == 200

    default = client_for(admin).get(
        "/api/admin/documents", params={"driver_id": driver.id}
    )
    assert default.status_code == 200
    ids = {item["id"] for item in default.json()["items"]}
    assert pending["id"] in ids
    assert approved["id"] not in ids

    everything = client_for(admin).get(
        "/api/admin/documents",
        params={"driver_id": driver.id, "status": "all"},
    )
    all_ids = {item["id"] for item in everything.json()["items"]}
    assert {pending["id"], approved["id"]} <= all_ids


def test_rejection_requires_a_reason_and_records_reviewer(upload_dir):
    driver = make_user("driver")
    admin = make_user("admin")
    document = _upload(client_for(driver)).json()
    admin_client = client_for(admin)

    missing = _review(admin_client, document["id"], decision="rejected")
    assert missing.status_code == 422
    assert _code(missing) == "invalid_rejection_reason"

    short = _review(
        admin_client, document["id"], decision="rejected", reason="x"
    )
    assert short.status_code == 422
    assert _code(short) == "invalid_rejection_reason"

    rejected = _review(
        admin_client,
        document["id"],
        decision="rejected",
        reason="تصویر ناخوانا است",
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "تصویر ناخوانا است"
    assert body["reviewed_at"] is not None

    db = SessionLocal()
    try:
        stored = db.get(DriverDocument, document["id"])
        assert stored.reviewed_by_id == admin.id
    finally:
        db.close()

    approved = _review(admin_client, document["id"], version=1)
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    assert body["rejection_reason"] is None


def test_stale_review_version_is_rejected(upload_dir):
    driver = make_user("driver")
    admin = make_user("admin")
    document = _upload(client_for(driver)).json()
    admin_client = client_for(admin)

    assert _review(admin_client, document["id"], version=1).status_code == 200
    replacement = _upload(client_for(driver), name="license-v2.pdf")
    assert replacement.status_code == 200

    stale = _review(admin_client, document["id"], version=1)
    assert stale.status_code == 409
    assert _code(stale) == "document_version_conflict"

    db = SessionLocal()
    try:
        assert db.get(DriverDocument, document["id"]).status == "pending"
    finally:
        db.close()


def test_download_is_owner_or_admin_only(upload_dir):
    driver = make_user("driver")
    other_driver = make_user("driver")
    admin = make_user("admin")
    document = _upload(client_for(driver)).json()
    url = f"/api/documents/{document['id']}/file"

    response = client_for(driver).get(url)
    assert response.status_code == 200
    assert response.content == PDF
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"

    assert client_for(other_driver).get(url).status_code == 403
    assert client_for(admin).get(url).status_code == 200
    assert client_for(None).get(url).status_code == 401

    db = SessionLocal()
    try:
        stored = db.get(DriverDocument, document["id"])
        path = Path(upload_dir) / stored.stored_path
    finally:
        db.close()
    path.unlink()

    missing = client_for(admin).get(url)
    assert missing.status_code == 404
    assert _code(missing) == "document_file_missing"


def test_driver_only_sees_own_documents(upload_dir):
    driver_a = make_user("driver")
    driver_b = make_user("driver")
    _upload(client_for(driver_a))

    own = client_for(driver_a).get("/api/drivers/me/documents").json()
    assert len(own["documents"]) == 1

    other = client_for(driver_b).get("/api/drivers/me/documents").json()
    assert other["documents"] == []
    assert other["verification_status"] == "unverified"


def test_stored_filename_is_server_generated(upload_dir):
    driver = make_user("driver")
    response = _upload(client_for(driver), name="../../evil.PDF")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["original_filename"] == "evil.PDF"

    db = SessionLocal()
    try:
        document = db.get(DriverDocument, body["id"])
        assert ".." not in document.stored_path
        assert "evil" not in document.stored_path.lower()
        assert document.stored_path.startswith(f"documents/{driver.id}/")
    finally:
        db.close()


def test_missing_document_returns_404():
    admin = make_user("admin")
    assert client_for(admin).get("/api/documents/2147483647/file").status_code == 404

    response = _review(client_for(admin), 2147483647)
    assert response.status_code == 404
    assert _code(response) == "document_not_found"
