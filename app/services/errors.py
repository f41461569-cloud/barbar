"""Domain exceptions shared by the API and page layers.

Each exception carries the HTTP status, a stable snake_case ``code`` and the
Persian ``message`` returned inside ``{"detail": {"code", "message"}}``
(docs/SPEC-core.md §12).
"""

from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    code = "bad_request"
    message = "درخواست نامعتبر است."

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class Unauthorized(DomainError):
    status_code = 401
    code = "unauthorized"
    message = "برای ادامه باید وارد حساب خود شوید."


class Forbidden(DomainError):
    status_code = 403
    code = "forbidden"
    message = "شما به این بخش دسترسی ندارید."


class DriverNotVerified(DomainError):
    status_code = 403
    code = "driver_not_verified"
    message = "برای رزرو بار، ابتدا مدارک شما باید تأیید شود."


class CargoNotFound(DomainError):
    status_code = 404
    code = "cargo_not_found"
    message = "بار مورد نظر یافت نشد."


class CargoUnavailable(DomainError):
    status_code = 409
    code = "cargo_unavailable"
    message = "این بار در همین لحظه توسط راننده دیگری رزرو شد."


class DocumentNotFound(DomainError):
    status_code = 404
    code = "document_not_found"
    message = "مدرک مورد نظر یافت نشد."


class DocumentFileMissing(DomainError):
    status_code = 404
    code = "document_file_missing"
    message = "فایل مدرک روی سرور موجود نیست."


class DocumentVersionConflict(DomainError):
    status_code = 409
    code = "document_version_conflict"
    message = "این مدرک پس از بازکردن شما تغییر کرده است؛ صفحه را تازه کنید."


class DocumentUploadConflict(DomainError):
    status_code = 409
    code = "document_upload_conflict"
    message = "بارگذاری هم‌زمان برای این مدرک رخ داد؛ دوباره تلاش کنید."


class InvalidDocType(DomainError):
    status_code = 422
    code = "invalid_doc_type"
    message = "نوع مدرک باید گواهینامه یا کارت ملی باشد."


class InvalidFile(DomainError):
    status_code = 422
    code = "invalid_file"
    message = "فایل انتخاب‌شده خالی یا نامعتبر است."


class FileTooLarge(DomainError):
    status_code = 413
    code = "file_too_large"
    message = "حجم فایل نباید بیشتر از ۵ مگابایت باشد."


class UnsupportedFileType(DomainError):
    status_code = 415
    code = "unsupported_file_type"
    message = "فقط PDF، JPG و PNG مجاز است."


class InvalidRejectionReason(DomainError):
    status_code = 422
    code = "invalid_rejection_reason"
    message = "برای رد مدرک، دلیل را وارد کنید."
