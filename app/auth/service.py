"""Registration and authentication service for registration v2 (ADR 007).

Routes stay thin: they collect form fields, call this module, and translate the
domain errors into HTML status codes. Everything here is synchronous and uses
the request's SQLAlchemy session.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.errors import (
    AdminDisabled,
    AuthValidationError,
    InvalidCredentials,
    RegistrationConflict,
)
from app.auth.normalization import (
    CARGO_TYPES,
    TRUCK_TYPES,
    normalize_license_number,
    normalize_name,
    normalize_national_id,
    normalize_phone,
    normalize_plate_number,
    normalize_username,
    password_error,
)
from app.auth.security import hash_password, verify_password
from app.config import settings
from app.models import User, UserRole

PHONE_TAKEN = "این شماره تلفن قبلاً ثبت شده است."
NATIONAL_ID_TAKEN = "این کد ملی قبلاً ثبت شده است."
LICENSE_TAKEN = "این شماره گواهینامه قبلاً ثبت شده است."
USERNAME_TAKEN = "این نام کاربری قبلاً ثبت شده است."
DUPLICATE_GENERIC = "این اطلاعات قبلاً ثبت شده است."

LOGIN_INVALID = "شماره تلفن یا رمز عبور نادرست است."
ADMIN_LOGIN_INVALID = "نام کاربری، رمز عبور یا کد مدیریت نادرست است."
ADMIN_CODE_INVALID = "کد مدیریت نادرست است."
ADMIN_DISABLED = "ورود مدیران در حال حاضر فعال نیست."
VALIDATION_FAILED = "اطلاعات وارد شده معتبر نیست."


def _field(data: Mapping[str, str], key: str) -> str:
    return str(data.get(key, "") or "")


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def validate_driver(data: Mapping[str, str]) -> dict[str, str]:
    """Normalize a driver submission or raise ``AuthValidationError``."""

    errors: dict[str, str] = {}

    name = normalize_name(_field(data, "full_name"))
    if name is None:
        errors["full_name"] = "نام و نام خانوادگی معتبر نیست."

    phone = normalize_phone(_field(data, "phone"))
    if phone is None:
        errors["phone"] = "شماره تلفن معتبر نیست."

    national_id = normalize_national_id(_field(data, "national_id"))
    if national_id is None:
        errors["national_id"] = "کد ملی معتبر نیست."

    license_number = normalize_license_number(_field(data, "license_number"))
    if license_number is None:
        errors["license_number"] = "شماره گواهینامه معتبر نیست."

    truck_type = _field(data, "truck_type").strip().lower()
    if truck_type not in TRUCK_TYPES:
        errors["truck_type"] = "نوع خودرو معتبر نیست."

    plate_number = normalize_plate_number(_field(data, "plate_number"))
    if plate_number is None:
        errors["plate_number"] = "شماره پلاک معتبر نیست."

    password = _field(data, "password")
    password_problem = password_error(password)
    if password_problem:
        errors["password"] = password_problem

    if errors:
        raise AuthValidationError(errors)

    return {
        "name": name,
        "phone": phone,
        "national_id": national_id,
        "license_number": license_number,
        "truck_type": truck_type,
        "plate_number": plate_number,
        "password": password,
    }


def validate_shipper(data: Mapping[str, str]) -> dict[str, str]:
    errors: dict[str, str] = {}

    name = normalize_name(_field(data, "full_name"))
    if name is None:
        errors["full_name"] = "نام و نام خانوادگی معتبر نیست."

    phone = normalize_phone(_field(data, "phone"))
    if phone is None:
        errors["phone"] = "شماره تلفن معتبر نیست."

    cargo_type = _field(data, "cargo_type_preference").strip().lower()
    if cargo_type not in CARGO_TYPES:
        errors["cargo_type_preference"] = "نوع بار معتبر نیست."

    national_id = normalize_national_id(_field(data, "national_id"))
    if national_id is None:
        errors["national_id"] = "کد ملی معتبر نیست."

    password = _field(data, "password")
    password_problem = password_error(password)
    if password_problem:
        errors["password"] = password_problem

    if errors:
        raise AuthValidationError(errors)

    return {
        "name": name,
        "phone": phone,
        "national_id": national_id,
        "cargo_type_preference": cargo_type,
        "password": password,
    }


def validate_admin(data: Mapping[str, str]) -> dict[str, str]:
    errors: dict[str, str] = {}

    username = normalize_username(_field(data, "username"))
    if username is None:
        errors["username"] = "نام کاربری معتبر نیست."

    password = _field(data, "password")
    password_problem = password_error(password)
    if password_problem:
        errors["password"] = password_problem

    if errors:
        raise AuthValidationError(errors)

    return {
        "username": username,
        "password": password,
        "admin_code": _field(data, "admin_code"),
    }


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


def _raise_conflicts(
    db: Session,
    *,
    phone: str | None = None,
    national_id: str | None = None,
    license_number: str | None = None,
    username: str | None = None,
) -> None:
    checks = (
        (User.phone, phone, PHONE_TAKEN),
        (User.national_id, national_id, NATIONAL_ID_TAKEN),
        (User.license_number, license_number, LICENSE_TAKEN),
        (User.username, username, USERNAME_TAKEN),
    )
    for column, value, message in checks:
        if value is None:
            continue
        if db.query(User.id).filter(column == value).first() is not None:
            raise RegistrationConflict(message)


def _insert_user(db: Session, *, conflicts: dict[str, str], **values) -> User:
    """Insert a user, mapping a lost uniqueness race to ``RegistrationConflict``."""

    _raise_conflicts(db, **conflicts)
    user = User(**values)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Another request won the race between our pre-check and the insert.
        _raise_conflicts(db, **conflicts)
        raise RegistrationConflict(DUPLICATE_GENERIC) from exc
    db.refresh(user)
    return user


def register_driver(db: Session, data: Mapping[str, str]) -> User:
    values = validate_driver(data)
    return _insert_user(
        db,
        conflicts={
            "phone": values["phone"],
            "national_id": values["national_id"],
            "license_number": values["license_number"],
        },
        phone=values["phone"],
        name=values["name"],
        password_hash=hash_password(values["password"]),
        role=UserRole.DRIVER,
        national_id=values["national_id"],
        license_number=values["license_number"],
        truck_type=values["truck_type"],
        plate_number=values["plate_number"],
    )


def register_shipper(db: Session, data: Mapping[str, str]) -> User:
    values = validate_shipper(data)
    return _insert_user(
        db,
        conflicts={
            "phone": values["phone"],
            "national_id": values["national_id"],
        },
        phone=values["phone"],
        name=values["name"],
        password_hash=hash_password(values["password"]),
        role=UserRole.SHIPPER,
        national_id=values["national_id"],
        cargo_type_preference=values["cargo_type_preference"],
    )


def _admin_code_enabled() -> None:
    if not settings.ADMIN_CODE:
        raise AdminDisabled(ADMIN_DISABLED)


def register_admin(db: Session, data: Mapping[str, str]) -> User:
    _admin_code_enabled()
    values = validate_admin(data)
    code = values["admin_code"]
    if not code or not secrets.compare_digest(code, settings.ADMIN_CODE):
        raise InvalidCredentials(ADMIN_CODE_INVALID)
    return _insert_user(
        db,
        conflicts={"username": values["username"]},
        phone=None,
        name=values["username"],
        password_hash=hash_password(values["password"]),
        role=UserRole.ADMIN,
        username=values["username"],
    )


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #

USER_ROLES = (UserRole.DRIVER, UserRole.SHIPPER, UserRole.CARRIER)


def authenticate_user(db: Session, phone: str, password: str) -> User:
    """Phone + password for driver/shipper/carrier; admins are rejected generically."""

    normalized = normalize_phone(phone)
    user = None
    if normalized is not None:
        user = db.query(User).filter(User.phone == normalized).one_or_none()
    if (
        user is None
        or user.role not in USER_ROLES
        or not verify_password(str(password or ""), user.password_hash)
    ):
        raise InvalidCredentials(LOGIN_INVALID)
    return user


def authenticate_admin(
    db: Session, identifier: str, password: str, admin_code: str
) -> User:
    """Username (or a legacy admin phone) + password + admin code."""

    _admin_code_enabled()

    code_ok = bool(admin_code) and secrets.compare_digest(
        str(admin_code), settings.ADMIN_CODE
    )

    raw_identifier = str(identifier or "").strip()
    user = None
    if raw_identifier:
        user = (
            db.query(User)
            .filter(User.username == raw_identifier.lower())
            .one_or_none()
        )
        if user is None:
            phone = normalize_phone(raw_identifier)
            if phone is not None:
                user = db.query(User).filter(User.phone == phone).one_or_none()

    if (
        not code_ok
        or user is None
        or user.role != UserRole.ADMIN
        or not verify_password(str(password or ""), user.password_hash)
    ):
        raise InvalidCredentials(ADMIN_LOGIN_INVALID)
    return user
