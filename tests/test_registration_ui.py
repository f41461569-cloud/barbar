"""RED/GREEN markup and error-path tests for registration v2.

Markup tests need no database. Error-path tests are PostgreSQL-gated because
they register/login real users.
"""

import os
import re

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.support import (
    PASSWORD,
    admin_payload,
    driver_payload,
    login_admin,
    login_user,
    new_phone,
    new_username,
    register_admin,
    register_driver,
)

DATABASE_URL = os.getenv("DATABASE_URL", "")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL.lower().startswith(("postgres", "postgresql")),
    reason="Registration error tests require PostgreSQL.",
)

PAGES = (
    "/auth/register",
    "/auth/register/driver",
    "/auth/register/shipper",
    "/auth/register/admin",
    "/auth/login",
    "/auth/admin/login",
    "/auth/register/success?role=driver",
    "/auth/register/success?role=shipper",
    "/auth/register/success?role=admin",
)

TAG_RE = re.compile(
    r"""<(input|select|option|label|button|script)\b((?:"[^"]*"|'[^']*'|[^>"'])*)>""",
    re.IGNORECASE | re.DOTALL,
)
ATTR_RE = re.compile(r'([\w:@.\-]+)="([^"]*)"')


def _attrs(tag_attrs: str) -> dict:
    return {k.lower(): v for k, v in ATTR_RE.findall(tag_attrs)}


def _tags(html: str, name: str):
    return [
        (_attrs(match.group(2)), match.group(0))
        for match in TAG_RE.finditer(html)
        if match.group(1).lower() == name
    ]


def _client(follow_redirects: bool = True) -> TestClient:
    return TestClient(app, follow_redirects=follow_redirects)


def _body(path: str) -> str:
    response = _client().get(path)
    assert response.status_code == 200, (path, response.text)
    return response.text


# --------------------------------------------------------------------------- #
# Shared shell and platform
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("path", PAGES)
def test_pages_are_rtl_persian_with_vazirmatn(path):
    body = _body(path)
    assert 'dir="rtl"' in body
    assert 'lang="fa"' in body
    assert "fonts.googleapis.com/css2?family=Vazirmatn" in body
    assert "fonts.gstatic.com" in body


@pytest.mark.parametrize("path", PAGES)
def test_tailwind_is_pinned_and_only_external_script(path):
    body = _body(path)
    assert "https://cdn.tailwindcss.com/3.4.17" in body
    assert "tailwind.config" in body
    scripts_with_src = re.findall(r"<script[^>]+src=", body, re.IGNORECASE)
    assert len(scripts_with_src) == 1, scripts_with_src


@pytest.mark.parametrize("path", PAGES)
def test_navy_yellow_white_shell(path):
    body = _body(path)
    for token in (
        "bg-[#0a192f]",
        "bg-[#fbbf24]",
        "bg-white",
        "text-white",
        "باربر هوشمند",
    ):
        assert token in body, (path, token)
    for token in (
        "from-violet-600",
        "to-pink-600",
        "from-pink-50",
        "to-violet-100",
        "backdrop-blur",
    ):
        assert token not in body, (path, token)


@pytest.mark.parametrize("path", PAGES)
def test_brand_header_has_truck_logo(path):
    body = _body(path)
    assert 'data-brand="smart-freight"' in body
    assert "باربر هوشمند" in body
    assert "<svg" in body.lower()


@pytest.mark.parametrize("path", PAGES)
def test_no_alert_on_clean_get(path):
    assert 'role="alert"' not in _body(path)


# --------------------------------------------------------------------------- #
# Landing
# --------------------------------------------------------------------------- #


def test_landing_has_three_role_cards_and_no_role_select():
    body = _body("/auth/register")
    for role, label, href in (
        ("driver", "راننده", "/auth/register/driver"),
        ("shipper", "صاحب کالا / انبار", "/auth/register/shipper"),
        ("admin", "مدیر سیستم", "/auth/register/admin"),
    ):
        assert f'data-role-card="{role}"' in body, role
        assert label in body, role
        assert f'href="{href}"' in body, role
    assert "شرکت حمل و نقل" not in body
    assert 'name="role"' not in body
    assert "<form" not in body


# --------------------------------------------------------------------------- #
# Role forms
# --------------------------------------------------------------------------- #


def test_driver_form_contract():
    body = _body("/auth/register/driver")
    inputs = _tags(body, "input")
    names = [attrs["name"] for attrs, _ in inputs if "name" in attrs]
    assert names == [
        "full_name",
        "phone",
        "national_id",
        "license_number",
        "plate_number",
        "password",
    ], names

    selects = _tags(body, "select")
    assert len(selects) == 1
    assert selects[0][0].get("name") == "truck_type"
    option_values = [a.get("value") for a, _ in _tags(body, "option")]
    assert option_values == [
        "",
        "pickup",
        "khavar",
        "truck",
        "trailer",
        "refrigerated",
        "tanker",
    ]

    order = [
        body.index('name="full_name"'),
        body.index('name="phone"'),
        body.index('name="national_id"'),
        body.index('name="license_number"'),
        body.index('name="truck_type"'),
        body.index('name="plate_number"'),
        body.index('name="password"'),
    ]
    assert order == sorted(order)

    for field in (
        "full_name",
        "phone",
        "national_id",
        "license_number",
        "truck_type",
        "plate_number",
        "password",
    ):
        assert re.search(rf'<label[^>]+for="{field}"', body), field
        assert re.search(rf'<[a-z]+[^>]+id="{field}"', body, re.IGNORECASE), field

    for icon in ("user", "phone", "id-card", "license", "truck", "plate", "lock"):
        assert f'data-field-icon="{icon}"' in body, icon
    assert "absolute right-3" in body

    for attrs, raw in inputs:
        assert "required" in raw, raw
    password = next(a for a, _ in inputs if a.get("name") == "password")
    assert "value" not in password
    assert password.get("type") == "password"


def test_shipper_form_contract():
    body = _body("/auth/register/shipper")
    inputs = _tags(body, "input")
    names = [attrs["name"] for attrs, _ in inputs if "name" in attrs]
    assert names == ["full_name", "phone", "national_id", "password"], names

    selects = _tags(body, "select")
    assert len(selects) == 1
    assert selects[0][0].get("name") == "cargo_type_preference"
    option_values = [a.get("value") for a, _ in _tags(body, "option")]
    assert option_values == [
        "",
        "general",
        "perishable",
        "fragile",
        "bulk",
        "hazardous",
        "heavy",
    ]
    for field in ("full_name", "phone", "cargo_type_preference", "national_id", "password"):
        assert re.search(rf'<label[^>]+for="{field}"', body), field
    for icon in ("user", "phone", "package", "id-card", "lock"):
        assert f'data-field-icon="{icon}"' in body, icon


def test_admin_form_contract():
    body = _body("/auth/register/admin")
    inputs = _tags(body, "input")
    names = [attrs["name"] for attrs, _ in inputs if "name" in attrs]
    assert names == ["username", "password", "admin_code"], names
    assert "phone" not in names

    admin_code = next(a for a, _ in inputs if a.get("name") == "admin_code")
    assert admin_code.get("type") == "password"
    assert "value" not in admin_code

    for field in ("username", "password", "admin_code"):
        assert re.search(rf'<label[^>]+for="{field}"', body), field
    for icon in ("user", "lock", "shield"):
        assert f'data-field-icon="{icon}"' in body, icon
    assert "کد مدیریت" in body


def test_forms_have_back_links():
    for path in (
        "/auth/register/driver",
        "/auth/register/shipper",
        "/auth/register/admin",
    ):
        body = _body(path)
        assert 'href="/auth/register"' in body


# --------------------------------------------------------------------------- #
# Login forms
# --------------------------------------------------------------------------- #


def test_user_login_contract():
    body = _body("/auth/login")
    inputs = _tags(body, "input")
    names = [attrs["name"] for attrs, _ in inputs if "name" in attrs]
    assert names == ["phone", "password"], names
    assert "admin_code" not in body
    assert 'href="/auth/admin/login"' in body
    assert 'href="/auth/register"' in body
    for field in ("phone", "password"):
        assert re.search(rf'<label[^>]+for="{field}"', body), field
    assert "absolute right-3" in body


def test_admin_login_contract():
    body = _body("/auth/admin/login")
    inputs = _tags(body, "input")
    names = [attrs["name"] for attrs, _ in inputs if "name" in attrs]
    assert names == ["username", "password", "admin_code"], names
    assert "phone" not in names
    assert 'href="/auth/login"' in body
    admin_code = next(a for a, _ in inputs if a.get("name") == "admin_code")
    assert admin_code.get("type") == "password"


# --------------------------------------------------------------------------- #
# Buttons, links, success
# --------------------------------------------------------------------------- #


def test_primary_buttons_are_yellow_with_dark_text():
    for path in (
        "/auth/register/driver",
        "/auth/register/shipper",
        "/auth/register/admin",
        "/auth/login",
        "/auth/admin/login",
    ):
        body = _body(path)
        submits = [
            attrs
            for attrs, _ in _tags(body, "button")
            if attrs.get("type") == "submit"
        ]
        assert submits, path
        classes = submits[0].get("class", "")
        for token in ("bg-[#fbbf24]", "text-gray-900", "focus-visible:ring-2"):
            assert token in classes, (path, token)


@pytest.mark.parametrize(
    "role,message,link",
    [
        ("driver", "حساب راننده ساخته شد", "/auth/login"),
        ("shipper", "حساب صاحب کالا ساخته شد", "/auth/login"),
        ("admin", "حساب مدیر ساخته شد", "/auth/admin/login"),
    ],
)
def test_success_page_is_role_aware(role, message, link):
    body = _body(f"/auth/register/success?role={role}")
    assert message in body
    assert f'href="{link}"' in body
    assert 'href="/auth/register"' in body
    assert 'role="alert"' not in body


def test_unknown_success_role_is_404():
    assert _client().get("/auth/register/success?role=carrier").status_code == 404


# --------------------------------------------------------------------------- #
# Error paths (PostgreSQL)
# --------------------------------------------------------------------------- #


@requires_postgres
def test_duplicate_phone_renders_alert_and_preserves_values():
    payload = driver_payload(full_name="Preserved Driver")
    submitted_password = "never-echo-this-password"
    try:
        assert (
            _client(follow_redirects=False)
            .post("/auth/register/driver", data=payload)
            .status_code
            == 303
        )
        response = _client(follow_redirects=False).post(
            "/auth/register/driver",
            data=driver_payload(
                phone=payload["phone"],
                full_name="Preserved Driver",
                password=submitted_password,
            ),
        )
        assert response.status_code == 409, response.text
        assert 'role="alert"' in response.text
        assert "این شماره تلفن قبلاً ثبت شده است." in response.text
        assert "Preserved Driver" in response.text
        assert submitted_password not in response.text
    finally:
        from tests.test_auth import _cleanup

        _cleanup(payload["phone"])


@requires_postgres
def test_invalid_national_id_renders_field_error():
    payload = driver_payload(national_id="1234567890")
    response = _client(follow_redirects=False).post(
        "/auth/register/driver", data=payload
    )
    assert response.status_code == 422, response.text
    assert "کد ملی معتبر نیست." in response.text
    assert 'aria-invalid="true"' in response.text
    assert payload["full_name"] in response.text


@requires_postgres
def test_wrong_login_renders_alert_and_preserves_phone():
    payload = driver_payload()
    submitted_password = "definitely-wrong-password"
    try:
        assert (
            _client(follow_redirects=False)
            .post("/auth/register/driver", data=payload)
            .status_code
            == 303
        )
        response = login_user(
            _client(follow_redirects=False), payload["phone"], submitted_password
        )
        assert response.status_code == 401, response.text
        assert 'role="alert"' in response.text
        assert payload["phone"] in response.text
        assert submitted_password not in response.text
        assert "set-cookie" not in response.headers
    finally:
        from tests.test_auth import _cleanup

        _cleanup(payload["phone"])


@requires_postgres
def test_wrong_admin_code_renders_generic_alert(admin_code):
    username = new_username()
    try:
        assert (
            register_admin(_client(), admin_code, username=username).status_code
            == 303
        )
        response = login_admin(
            _client(follow_redirects=False),
            username,
            PASSWORD,
            "wrong-code",
        )
        assert response.status_code == 401, response.text
        assert 'role="alert"' in response.text
        assert username in response.text
        assert "wrong-code" not in response.text
        assert "set-cookie" not in response.headers
    finally:
        from tests.test_auth import _cleanup

        _cleanup(usernames=(username,))


@requires_postgres
def test_admin_disabled_renders_503(admin_code, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_CODE", "")
    response = _client(follow_redirects=False).get("/auth/admin/login")
    # The GET form still renders; the POST is disabled.
    assert response.status_code == 200
    response = login_admin(
        _client(follow_redirects=False), new_username(), PASSWORD, admin_code
    )
    assert response.status_code == 503, response.text
    assert "ورود مدیران در حال حاضر فعال نیست." in response.text
