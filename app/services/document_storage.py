"""Validated local-disk storage for driver documents (ADR 006, SPEC-core §10)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.config import settings
from app.services.errors import (
    DocumentFileMissing,
    FileTooLarge,
    InvalidFile,
    UnsupportedFileType,
)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MiB

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# (declared/normalized MIME types, magic-byte prefix, canonical type, extension)
SIGNATURES = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
)

ALLOWED_CONTENT_TYPES = frozenset(
    {content_type for _, content_type, _ in SIGNATURES}
)


def normalize_content_type(declared: str | None) -> str:
    """Lowercase a declared MIME type, dropping parameters and aliases."""

    if not declared:
        return ""
    base = declared.split(";", 1)[0].strip().lower()
    if base == "image/jpg":
        base = "image/jpeg"
    if base == "application/x-pdf":
        base = "application/pdf"
    return base


def sniff_content_type(data: bytes) -> tuple[str, str] | None:
    """Return ``(content_type, extension)`` from magic bytes, or ``None``."""

    for prefix, content_type, extension in SIGNATURES:
        if data.startswith(prefix):
            return content_type, extension
    return None


def sanitize_filename(name: str | None) -> str:
    """Keep only the final path component; never use the client name as a path."""

    candidate = (name or "").replace("\\", "/")
    candidate = candidate.rsplit("/", 1)[-1]
    candidate = _CONTROL_CHARS.sub("", candidate).strip()
    if not candidate or candidate in {".", ".."}:
        candidate = "document"
    return candidate[:255]


def validate_upload(declared: str | None, data: bytes) -> tuple[str, str]:
    """Validate size/magic bytes and return ``(content_type, extension)``."""

    if not data:
        raise InvalidFile()
    if len(data) > MAX_FILE_SIZE:
        raise FileTooLarge()

    sniffed = sniff_content_type(data)
    if sniffed is None:
        raise UnsupportedFileType()
    content_type, extension = sniffed

    declared_type = normalize_content_type(declared)
    if declared_type not in ALLOWED_CONTENT_TYPES or declared_type != content_type:
        raise UnsupportedFileType()

    return content_type, extension


def _root() -> Path:
    # Read the setting on every call so tests can repoint it via monkeypatch.
    return Path(settings.UPLOAD_DIR).expanduser().resolve()


def save_document(driver_id: int, data: bytes, extension: str) -> str:
    """Write the bytes under a UUID name and return the relative POSIX path."""

    directory = _root() / "documents" / str(driver_id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    (directory / filename).write_bytes(data)
    return f"documents/{driver_id}/{filename}"


def resolve_document_path(stored_path: str) -> Path:
    """Resolve a stored relative path, refusing anything outside ``UPLOAD_DIR``."""

    root = _root()
    target = (root / stored_path).resolve()
    if not target.is_relative_to(root):
        raise DocumentFileMissing()
    return target


def delete_document(stored_path: str) -> None:
    """Best-effort cleanup; a missing file is not an error."""

    try:
        resolve_document_path(stored_path).unlink(missing_ok=True)
    except DocumentFileMissing:
        return
