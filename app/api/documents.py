"""Driver document, admin review and file-download JSON routes (SPEC-core §7.2)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.guards import require_admin, require_authenticated, require_driver
from app.database import get_db
from app.models import User
from app.schemas import (
    AdminDocumentListResponse,
    AdminDocumentResponse,
    DocumentReviewRequest,
    DriverDocumentResponse,
    DriverDocumentsResponse,
)
from app.services.document_service import (
    get_document_for_download,
    list_for_admin,
    list_own_documents,
    review_document,
    upload_document,
    verification_status,
)
from app.services.document_storage import MAX_FILE_SIZE

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/drivers/me/documents", status_code=201)
def upload_my_document(
    response: Response,
    doc_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    user: User = Depends(require_driver),
    db: Session = Depends(get_db),
):
    data = file.file.read(MAX_FILE_SIZE + 1)
    document, created = upload_document(
        db,
        driver_id=user.id,
        doc_type=doc_type,
        filename=file.filename,
        declared_content_type=file.content_type,
        data=data,
    )
    response.status_code = 201 if created else 200
    return DriverDocumentResponse.model_validate(document)


@router.get("/drivers/me/documents", response_model=DriverDocumentsResponse)
def my_documents(
    user: User = Depends(require_driver),
    db: Session = Depends(get_db),
):
    documents = list_own_documents(db, user.id)
    return DriverDocumentsResponse(
        verification_status=verification_status(db, user.id),
        documents=[
            DriverDocumentResponse.model_validate(document)
            for document in documents
        ],
    )


@router.get("/documents/{document_id}/file")
def download_document(
    document_id: int,
    user: User = Depends(require_authenticated),
    db: Session = Depends(get_db),
):
    document, path = get_document_for_download(db, document_id, user)
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.original_filename,
        content_disposition_type="attachment",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/admin/documents", response_model=AdminDocumentListResponse)
def admin_documents(
    status: Literal["pending", "approved", "rejected", "all"] = "pending",
    driver_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows, total = list_for_admin(
        db,
        status=status,
        driver_id=driver_id,
        limit=limit,
        offset=offset,
    )
    return AdminDocumentListResponse(
        items=[
            AdminDocumentResponse(
                **DriverDocumentResponse.model_validate(document).model_dump(),
                driver_name=driver_name,
            )
            for document, driver_name in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/admin/documents/{document_id}/review",
    response_model=DriverDocumentResponse,
)
def review(
    document_id: int,
    payload: DocumentReviewRequest,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    document = review_document(
        db,
        document_id=document_id,
        admin=user,
        decision=payload.decision,
        reason=payload.reason,
        version=payload.version,
    )
    return DriverDocumentResponse.model_validate(document)
