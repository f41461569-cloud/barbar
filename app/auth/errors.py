"""Registration/auth errors with a status code and a user-facing message (ADR 007)."""

from __future__ import annotations


class AuthError(Exception):
    status_code = 400
    message = "خطایی رخ داد."

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)


class AuthValidationError(AuthError):
    """One or more field-level validation failures (rendered as 422)."""

    status_code = 422
    message = "اطلاعات وارد شده معتبر نیست."

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__(self.message)


class RegistrationConflict(AuthError):
    """A unique field is already taken (rendered as 409)."""

    status_code = 409


class InvalidCredentials(AuthError):
    """Wrong password, unknown account, wrong admin code, or wrong role (401)."""

    status_code = 401


class AdminDisabled(AuthError):
    """ADMIN_CODE is not configured, so admin registration/login is off (503)."""

    status_code = 503
