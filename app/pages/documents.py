"""Driver document page: status summary + upload form (SPEC-core §8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.guards import require_driver
from app.database import get_db
from app.models import User
from app.pages import flash_for, render
from app.services.document_service import (
    list_own_documents,
    upload_document,
    verification_status,
)
from app.services.document_storage import MAX_FILE_SIZE
from app.services.errors import DomainError

router = APIRouter(tags=["pages"])

DOC_TYPES = ("license", "national_id")
DOC_TYPE_LABELS = {"license": "گواهینامه", "national_id": "کارت ملی"}
STATUS_LABELS = {
    "pending": "در انتظار بررسی",
    "approved": "تأیید شده",
    "rejected": "رد شده",
}
VERIFICATION_LABELS = {
    "unverified": "تأیید نشده",
    "pending": "در انتظار بررسی",
    "verified": "تأیید شده",
    "rejected": "رد شده",
}


def _render(
    request: Request,
    user: User,
    db: Session,
    *,
    status_code: int = 200,
    error: str | None = None,
    flash: str | None = None,
    selected: str | None = None,
):
    documents = {doc.doc_type: doc for doc in list_own_documents(db, user.id)}
    state = verification_status(db, user.id)
    return render(
        request,
        "driver/documents.html",
        user,
        status_code=status_code,
        error=error,
        flash=flash,
        documents=documents,
        doc_types=DOC_TYPES,
        doc_type_labels=DOC_TYPE_LABELS,
        status_labels=STATUS_LABELS,
        verification_state=state,
        verification_label=VERIFICATION_LABELS[state],
        selected_type=selected,
    )


@router.get("/driver/documents")
def driver_documents_page(
    request: Request,
    ok: str | None = None,
    user: User = Depends(require_driver),
    db: Session = Depends(get_db),
):
    return _render(request, user, db, flash=flash_for(ok))


@router.post("/driver/documents")
def upload_document_page(
    request: Request,
    doc_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    user: User = Depends(require_driver),
    db: Session = Depends(get_db),
):
    data = file.file.read(MAX_FILE_SIZE + 1)
    try:
        upload_document(
            db,
            driver_id=user.id,
            doc_type=doc_type,
            filename=file.filename,
            declared_content_type=file.content_type,
            data=data,
        )
    except DomainError as exc:
        return _render(
            request,
            user,
            db,
            status_code=exc.status_code,
            error=exc.message,
            selected=doc_type,
        )

    return RedirectResponse(url="/driver/documents?ok=uploaded", status_code=303)
