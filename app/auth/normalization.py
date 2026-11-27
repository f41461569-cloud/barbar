"""Normalization and validation helpers for registration v2 (ADR 007).

Every function is pure and returns a canonical value or ``None``. Routes and the
service decide how to turn ``None`` into a field error, so these rules can be
unit-tested without a database.
"""

from __future__ import annotations

import re

TRUCK_TYPES = frozenset(
    {"pickup", "khavar", "truck", "trailer", "refrigerated", "tanker"}
)
CARGO_TYPES = frozenset(
    {"general", "perishable", "fragile", "bulk", "hazardous", "heavy"}
)

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_TRANSLATION = str.maketrans(
    _PERSIAN_DIGITS + _ARABIC_DIGITS, "0123456789" * 2
)

_PHONE_RE = re.compile(r"9\d{9}\Z")
_LICENSE_RE = re.compile(r"[0-9A-Z-]{5,30}\Z")
_USERNAME_RE = re.compile(r"[a-z0-9][a-z0-9._-]{2,49}\Z")


def to_latin_digits(value: str) -> str:
    return str(value or "").translate(_DIGIT_TRANSLATION)


def normalize_phone(raw: str | None) -> str | None:
    """Return ``+989xxxxxxxxx`` for a valid Iranian mobile, else ``None``."""

    value = to_latin_digits(raw).strip()
    value = re.sub(r"[\s\-()]", "", value)
    if value.startswith("+"):
        value = value[1:]
    if value.startswith("0098"):
        value = value[4:]
    elif value.startswith("98"):
        value = value[2:]
    elif value.startswith("0"):
        value = value[1:]
    if not _PHONE_RE.fullmatch(value):
        return None
    return "+98" + value


def _national_id_checksum(digits: str) -> bool:
    total = sum(int(digits[i]) * (10 - i) for i in range(9)) % 11
    check = total if total < 2 else 11 - total
    return check == int(digits[9])


def normalize_national_id(raw: str | None) -> str | None:
    """Return the 10-digit national ID if its checksum is valid."""

    value = to_latin_digits(raw).strip()
    value = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"\d{10}", value):
        return None
    if len(set(value)) == 1:
        return None
    if not _national_id_checksum(value):
        return None
    return value


def normalize_license_number(raw: str | None) -> str | None:
    value = to_latin_digits(raw).strip().upper()
    value = re.sub(r"\s", "", value)
    if not _LICENSE_RE.fullmatch(value):
        return None
    return value


def normalize_plate_number(raw: str | None) -> str | None:
    value = to_latin_digits(raw)
    value = re.sub(r"\s+", " ", value).strip()
    if not 5 <= len(value) <= 20:
        return None
    return value


def normalize_name(raw: str | None) -> str | None:
    value = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not 3 <= len(value) <= 100:
        return None
    return value


def normalize_username(raw: str | None) -> str | None:
    value = str(raw or "").strip().lower()
    if not _USERNAME_RE.fullmatch(value):
        return None
    return value


def password_error(password: str | None) -> str | None:
    """Return a user-facing message when the password is invalid."""

    value = str(password or "")
    if len(value) < 8 or len(value.encode("utf-8")) > 72:
        return "رمز عبور باید بین ۸ تا ۷۲ کاراکتر باشد."
    if not value.strip():
        return "رمز عبور باید بین ۸ تا ۷۲ کاراکتر باشد."
    return None
