"""RED/GREEN unit tests for registration normalization and validation.

No database is required; these run on SQLite and PostgreSQL.
"""

import pytest

from app.auth.errors import AuthValidationError
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
from app.auth.service import validate_admin, validate_driver, validate_shipper
from tests.support import (
    admin_payload,
    driver_payload,
    new_national_id,
    shipper_payload,
)


# --------------------------------------------------------------------------- #
# Phone
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw",
    [
        "09121234567",
        "+989121234567",
        "00989121234567",
        "989121234567",
        "۰۹۱۲۱۲۳۴۵۶۷",
    ],
)
def test_phone_normalizes_to_canonical_form(raw):
    assert normalize_phone(raw) == "+989121234567"


@pytest.mark.parametrize(
    "raw",
    ["0212345678", "0912123456", "091212345678", "not-a-phone", "", "  "],
)
def test_phone_rejects_invalid_values(raw):
    assert normalize_phone(raw) is None


# --------------------------------------------------------------------------- #
# National ID
# --------------------------------------------------------------------------- #


def test_national_id_accepts_valid_checksum():
    value = new_national_id()
    assert normalize_national_id(value) == value
    assert normalize_national_id("۰۴۹۹۳۷۰۸۹۹") == "0499370899"


@pytest.mark.parametrize(
    "value",
    ["123456789", "12345678901", "0000000000", "abcdefghij", ""],
)
def test_national_id_rejects_invalid_values(value):
    assert normalize_national_id(value) is None


def test_national_id_rejects_bad_checksum():
    valid = "0499370899"
    invalid = valid[:9] + str((int(valid[9]) + 1) % 10)
    assert normalize_national_id(invalid) is None


# --------------------------------------------------------------------------- #
# Other field normalizers
# --------------------------------------------------------------------------- #


def test_license_normalizes_and_validates():
    assert normalize_license_number(" ab-12345 ") == "AB-12345"
    assert normalize_license_number("۱۲۳۴۵") == "12345"
    assert normalize_license_number("abc") is None
    assert normalize_license_number("A" * 31) is None


def test_plate_normalizes_persian_digits_and_validates_length():
    assert normalize_plate_number("۱۲ ب ۳۴۵ ایران ۶۷") == "12 ب 345 ایران 67"
    assert normalize_plate_number("1234") is None
    assert normalize_plate_number("x" * 21) is None


def test_name_trims_collapses_and_validates():
    assert normalize_name("  Ali   Rezaei  ") == "Ali Rezaei"
    assert normalize_name("  ab  ") is None
    assert normalize_name("x" * 101) is None


def test_username_lowercases_and_validates():
    assert normalize_username("  Admin.User  ") == "admin.user"
    assert normalize_username("ab") is None
    assert normalize_username("admin user") is None
    assert normalize_username("admin@example") is None


def test_password_length_and_bcrypt_limit():
    assert password_error("secret123") is None
    assert password_error("short") is not None
    assert password_error(" " * 10) is not None
    assert password_error("a" * 72) is None
    assert password_error("a" * 73) is not None


def test_allowlists_are_non_empty_and_lowercase():
    assert "truck" in TRUCK_TYPES
    assert "general" in CARGO_TYPES
    assert all(item == item.lower() for item in TRUCK_TYPES | CARGO_TYPES)


# --------------------------------------------------------------------------- #
# Role validators
# --------------------------------------------------------------------------- #


def test_validate_driver_returns_normalized_payload():
    payload = driver_payload(full_name="  Ali   Driver  ", phone="09121234567")
    result = validate_driver(payload)
    assert result["name"] == "Ali Driver"
    assert result["phone"] == "+989121234567"
    assert result["national_id"] == payload["national_id"]
    assert result["license_number"] == payload["license_number"].upper()
    assert result["truck_type"] == "truck"
    assert result["plate_number"]
    assert result["password"] == payload["password"]


def test_validate_driver_reports_all_missing_fields():
    with pytest.raises(AuthValidationError) as excinfo:
        validate_driver({})
    errors = excinfo.value.errors
    for field in (
        "full_name",
        "phone",
        "national_id",
        "license_number",
        "truck_type",
        "plate_number",
        "password",
    ):
        assert field in errors


def test_validate_driver_rejects_unknown_truck_type():
    with pytest.raises(AuthValidationError) as excinfo:
        validate_driver(driver_payload(truck_type="spaceship"))
    assert "truck_type" in excinfo.value.errors


def test_validate_shipper_returns_normalized_payload():
    payload = shipper_payload(full_name="  Sara  ", phone="+989121234567")
    result = validate_shipper(payload)
    assert result["name"] == "Sara"
    assert result["phone"] == "+989121234567"
    assert result["cargo_type_preference"] == "general"


def test_validate_shipper_rejects_unknown_cargo_type():
    with pytest.raises(AuthValidationError) as excinfo:
        validate_shipper(shipper_payload(cargo_type_preference="spaceship"))
    assert "cargo_type_preference" in excinfo.value.errors


def test_validate_admin_normalizes_username_and_password():
    result = validate_admin(admin_payload("code", username="  Admin.User  "))
    assert result["username"] == "admin.user"
    assert result["password"] == "secret123"


def test_validate_admin_rejects_invalid_username():
    with pytest.raises(AuthValidationError) as excinfo:
        validate_admin(admin_payload("code", username="a b"))
    assert "username" in excinfo.value.errors
