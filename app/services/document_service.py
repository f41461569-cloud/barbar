"""Driver-document upload, verification state and admin review (ADR 006)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import DriverDocument, User
from app.services.document_storage import (
    delete_document,
    resolve_document_path,
    sanitize_filename,
    save_document,
    validate_upload,
)
from app.services.errors import (
    DocumentFileMissing,
    DocumentNotFound,
    DocumentUploadConflict,
    DocumentVersionConflict,
    Forbidden,
    InvalidDocType,
    InvalidRejectionReason,
)

DOC_TYPES = ("license", "national_id")
VERIFICATION_STATES = ("unverified", "pending", "verified", "rejected")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def verification_status(db: Session, driver_id: int) -> str:
    """Derive the driver's state; never stored as a flag (SPEC-core §5.1)."""

    documents = (
        db.query(DriverDocument)
        .filter(DriverDocument.driver_id == driver_id)
        .all()
    )
    by_type = {document.doc_type: document for document in documents}
    if len(by_type) == 2 and all(
        document.status == "approved" for document in by_type.values()
    ):
        return "verified"
    if any(document.status == "rejected" for document in documents):
        return "rejected"
    if any(document.status == "pending" for document in documents):
        return "pending"
    return "unverified"


def list_own_documents(db: Session, driver_id: int) -> list[DriverDocument]:
    return (
        db.query(DriverDocument)
        .filter(DriverDocument.driver_id == driver_id)
        .order_by(DriverDocument.doc_type.asc())
        .all()
    )


def upload_document(
    db: Session,
    *,
    driver_id: int,
    doc_type: str,
    filename: str | None,
    declared_content_type: str | None,
    data: bytes,
) -> tuple[DriverDocument, bool]:
    """Create or replace the driver's active document.

    Returns ``(document, created)``. New rows are 201, replacements 200.
    """

    if doc_type not in DOC_TYPES:
        raise InvalidDocType()

    content_type, extension = validate_upload(declared_content_type, data)
    stored_path = save_document(driver_id, data, extension)
    clean_name = sanitize_filename(filename)

    existing = (
        db.query(DriverDocument)
        .filter(
            DriverDocument.driver_id == driver_id,
            DriverDocument.doc_type == doc_type,
        )
        .one_or_none()
    )
    now = _now()

    try:
        if existing is None:
            document = DriverDocument(
                driver_id=driver_id,
                doc_type=doc_type,
                stored_path=stored_path,
                original_filename=clean_name,
                content_type=content_type,
                size_bytes=len(data),
                status="pending",
                version=1,
                uploaded_at=now,
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            return document, True

        old_path = existing.stored_path
        existing.stored_path = stored_path
        existing.original_filename = clean_name
        existing.content_type = content_type
        existing.size_bytes = len(data)
        existing.status = "pending"
        existing.rejection_reason = None
        existing.reviewed_at = None
        existing.reviewed_by_id = None
        existing.version = (existing.version or 1) + 1
        existing.uploaded_at = now
        db.commit()
        db.refresh(existing)
    except IntegrityError:
        db.rollback()
        delete_document(stored_path)
        raise DocumentUploadConflict()

    if existing is not None and old_path != stored_path:
        delete_document(old_path)
    return existing, False


def get_document(db: Session, document_id: int) -> DriverDocument:
    document = db.get(DriverDocument, document_id)
    if document is None:
        raise DocumentNotFound()
    return document


def get_document_for_download(
    db: Session, document_id: int, user: User
) -> tuple[DriverDocument, "object"]:
    """Return the row and the on-disk path, enforcing owner-or-admin access."""

    document = get_document(db, document_id)
    if user.role.value != "admin" and document.driver_id != user.id:
        raise Forbidden()

    path = resolve_document_path(document.stored_path)
    if not path.is_file():
        raise DocumentFileMissing()
    return document, path


def list_for_admin(
    db: Session,
    *,
    status: str = "pending",
    driver_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[tuple[DriverDocument, str]], int]:
    query = (
        db.query(DriverDocument, User.name)
        .join(User, User.id == DriverDocument.driver_id)
        .filter(DriverDocument.driver_id == User.id)
    )
    if status != "all":
        query = query.filter(DriverDocument.status == status)
    if driver_id is not None:
        query = query.filter(DriverDocument.driver_id == driver_id)

    total = query.count()
    rows = (
        query.order_by(
            DriverDocument.uploaded_at.desc(), DriverDocument.id.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows, total


def review_document(
    db: Session,
    *,
    document_id: int,
    admin: User,
    decision: str,
    reason: str | None = None,
    version: int | None = None,
) -> DriverDocument:
    document = get_document(db, document_id)

    if version is not None and version != document.version:
        raise DocumentVersionConflict()

    clean_reason: str | None = None
    if decision == "rejected":
        clean_reason = (reason or "").strip()
        if not 3 <= len(clean_reason) <= 500:
            raise InvalidRejectionReason()

    document.status = decision
    document.rejection_reason = clean_reason
    document.reviewed_at = _now()
    document.reviewed_by_id = admin.id
    db.commit()
    db.refresh(document)
    return document
