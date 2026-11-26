"""Admin document review queue (SPEC-core §8)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.guards import require_admin
from app.database import get_db
from app.models import User
from app.pages import flash_for, render
from app.services.document_service import list_for_admin, review_document
from app.services.errors import DomainError

router = APIRouter(tags=["pages"])

DOC_TYPE_LABELS = {"license": "گواهینامه", "national_id": "کارت ملی"}
STATUS_LABELS = {
    "pending": "در انتظار بررسی",
    "approved": "تأیید شده",
    "rejected": "رد شده",
}
STATUS_OPTIONS = (
    ("pending", "در انتظار بررسی"),
    ("approved", "تأیید شده"),
    ("rejected", "رد شده"),
    ("all", "همه"),
)


def _render(
    request: Request,
    user: User,
    db: Session,
    *,
    status: str = "pending",
    status_code: int = 200,
    error: str | None = None,
    flash: str | None = None,
):
    rows, total = list_for_admin(db, status=status, limit=100)
    return render(
        request,
        "admin/documents.html",
        user,
        status_code=status_code,
        error=error,
        flash=flash,
        rows=rows,
        total=total,
        active_status=status,
        status_options=STATUS_OPTIONS,
        doc_type_labels=DOC_TYPE_LABELS,
        status_labels=STATUS_LABELS,
    )


@router.get("/admin/documents")
def admin_documents_page(
    request: Request,
    status: Literal["pending", "approved", "rejected", "all"] = "pending",
    ok: str | None = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _render(
        request, user, db, status=status, flash=flash_for(ok)
    )


@router.post("/admin/documents/{document_id}/review")
def review_document_page(
    request: Request,
    document_id: int,
    decision: Annotated[Literal["approved", "rejected"], Form()],
    reason: Annotated[str | None, Form()] = None,
    version: Annotated[int | None, Form()] = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        review_document(
            db,
            document_id=document_id,
            admin=user,
            decision=decision,
            reason=reason,
            version=version,
        )
    except DomainError as exc:
        # Show the queue (pending by default) with the error above it.
        return _render(
            request,
            user,
            db,
            status_code=exc.status_code,
            error=exc.message,
        )

    return RedirectResponse(url="/admin/documents?ok=reviewed", status_code=303)
