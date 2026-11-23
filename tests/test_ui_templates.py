"""TDD tests for the login / registration UI redesign (docs/SPEC-ui.md).

Two groups:

* Markup/contract tests (AC-1 … AC-4, AC-7 … AC-11, AC-13) — no database needed; they only GET pages.
* Failure-path tests (AC-5, AC-6, AC-13) — need PostgreSQL because they register/login a real user.
  They are skipped unless DATABASE_URL is a PostgreSQL URL, matching tests/test_auth.py.

Run against PostgreSQL:

    $env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
    pytest tests/test_ui_templates.py -v
"""

import os
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.models import User

DATABASE_URL = os.getenv("DATABASE_URL", "")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL.lower().startswith(("postgres", "postgresql")),
    reason="Auth failure tests require PostgreSQL (set DATABASE_URL to a postgres URL).",
)

PAGES = ("/auth/login", "/auth/register", "/dashboard")
PASSWORD = "secret123"

LOGIN_ERROR = "شماره تلفن یا رمز عبور نادرست است."
REGISTER_ERROR = "این شماره تلفن قبلاً ثبت شده است."

TAG_RE = re.compile(
    r"""<(input|select|option|label|button|script)\b((?:"[^"]*"|'[^']*'|[^>"'])*)>""",
    re.IGNORECASE | re.DOTALL,
)
ATTR_RE = re.compile(r'([\w:@.\-]+)="([^"]*)"')


def _attrs(tag_attrs: str) -> dict:
    return {k.lower(): v for k, v in ATTR_RE.findall(tag_attrs)}


def _tags(html: str, name: str):
    """All (attrs, raw) pairs for a tag name, e.g. every <input ...>."""
    found = []
    for match in TAG_RE.finditer(html):
        if match.group(1).lower() == name:
            found.append((_attrs(match.group(2)), match.group(0)))
    return found


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def _new_phone() -> str:
    return "+9891" + uuid.uuid4().hex[:9]


def _cleanup(*phones):
    db = SessionLocal()
    try:
        db.query(User).filter(User.phone.in_(phones)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Markup / contract (AC-1, AC-2, AC-3, AC-4, AC-7, AC-8, AC-9, AC-10, AC-11)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("path", PAGES)
def test_page_is_rtl_persian(path):
    response = _client().get(path)
    body = response.text
    assert response.status_code == 200, body
    assert 'dir="rtl"' in body
    assert 'lang="fa"' in body
    assert "fonts.googleapis.com/css2?family=Vazirmatn" in body
    assert "fonts.gstatic.com" in body


@pytest.mark.parametrize("path", PAGES)
def test_tailwind_is_pinned_cdn(path):
    body = _client().get(path).text
    assert "https://cdn.tailwindcss.com/3.4.17" in body
    assert "tailwind.config" in body

    scripts_with_src = re.findall(r"<script[^>]+src=", body, re.IGNORECASE)
    assert len(scripts_with_src) == 1, scripts_with_src


@pytest.mark.parametrize("path", PAGES)
def test_no_legacy_style_or_js_framework(path):
    body = _client().get(path).text
    assert "#f4f6f8" not in body
    lowered = body.lower()
    for forbidden in ("react", "vue.js", "vue@", "alpinejs", "jquery", "bootstrap"):
        assert forbidden not in lowered, forbidden


@pytest.mark.parametrize("path", PAGES)
def test_glass_card_and_gradient(path):
    body = _client().get(path).text
    for token in ("backdrop-blur-xl", "bg-white/10", "rounded-3xl", "max-w-md"):
        assert token in body, token
    for token in ("from-blue-700", "via-indigo-700", "to-purple-700"):
        assert token in body, token


@pytest.mark.parametrize("path", PAGES)
def test_brand_row_with_truck_icon(path):
    body = _client().get(path).text
    assert 'data-brand="smart-freight"' in body
    assert "باربری هوشمند" in body
    assert "truck" in body.lower() or "<svg" in body.lower()


def test_login_field_contract():
    body = _client().get("/auth/login").text
    inputs = _tags(body, "input")
    names = [attrs["name"] for attrs, _ in inputs if "name" in attrs]
    assert names == ["phone", "password"], names

    for attrs, raw in inputs:
        assert "required" in raw, raw
        assert "focus:ring-2" in attrs.get("class", ""), raw

    assert _tags(body, "select") == []


def test_register_field_contract():
    body = _client().get("/auth/register").text
    inputs = _tags(body, "input")
    names = [attrs["name"] for attrs, _ in inputs if "name" in attrs]
    assert names == ["phone", "name", "password"], names

    selects = _tags(body, "select")
    assert len(selects) == 1
    assert selects[0][0].get("name") == "role"
    assert "focus:ring-2" in selects[0][0].get("class", "")

    option_values = [a.get("value") for a, _ in _tags(body, "option")]
    assert option_values == ["driver", "shipper", "carrier"], option_values
    assert "admin" not in [v.lower() for v in option_values if v]


@pytest.mark.parametrize(
    "path,ids",
    [
        ("/auth/login", ("phone", "password")),
        ("/auth/register", ("phone", "name", "password", "role")),
    ],
)
def test_labels_are_linked(path, ids):
    body = _client().get(path).text
    for field_id in ids:
        assert re.search(rf'<label[^>]+for="{field_id}"', body), field_id
        assert re.search(rf'<[a-z]+[^>]+id="{field_id}"', body, re.IGNORECASE), field_id


def test_password_is_never_prefilled():
    for path in ("/auth/login", "/auth/register"):
        body = _client().get(path).text
        for attrs, _ in _tags(body, "input"):
            if attrs.get("name") == "password":
                assert "value" not in attrs, attrs


@pytest.mark.parametrize("path", PAGES)
def test_no_alert_on_clean_get(path):
    assert 'role="alert"' not in _client().get(path).text


def test_primary_buttons_are_gradient():
    body = _client().get("/auth/register").text
    buttons = _tags(body, "button")
    assert buttons, "register page has no button"
    submit = [a for a, _ in buttons if a.get("type") == "submit"]
    assert submit
    classes = submit[0].get("class", "")
    for token in ("from-blue-500", "to-purple-500", "hover:from-blue-400", "focus-visible:ring"):
        assert token in classes, token


def test_dashboard_uses_same_shell_and_destructive_logout():
    body = _client().get("/dashboard").text
    assert "backdrop-blur-xl" in body
    assert "داشبورد" in body
    assert 'action="/auth/logout"' in body
    buttons = _tags(body, "button")
    assert buttons
    assert "bg-red-500/20" in buttons[0][0].get("class", "")


# --------------------------------------------------------------------------- #
# Failure paths — D1 Option A (AC-5, AC-6, AC-13)
# --------------------------------------------------------------------------- #


@requires_postgres
def test_wrong_password_renders_styled_alert():
    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    try:
        assert _client().post(
            "/auth/register",
            data={"phone": phone, "name": "UI Test", "password": PASSWORD, "role": "driver"},
        ).status_code in (200, 302)

        response = _client().post(
            "/auth/login", data={"phone": phone, "password": "definitely-wrong"}
        )
        assert response.status_code == 401, response.text
        assert 'role="alert"' in response.text
        assert 'aria-live="assertive"' in response.text
        assert LOGIN_ERROR in response.text
        assert "set-cookie" not in response.headers
    finally:
        _cleanup(phone)


@requires_postgres
def test_duplicate_phone_renders_styled_alert():
    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    try:
        first = _client().post(
            "/auth/register",
            data={"phone": phone, "name": "UI Test", "password": PASSWORD, "role": "driver"},
        )
        assert first.status_code in (200, 302), first.text

        second = _client().post(
            "/auth/register",
            data={"phone": phone, "name": "UI Test", "password": PASSWORD, "role": "driver"},
        )
        assert second.status_code == 409, second.text
        assert 'role="alert"' in second.text
        assert REGISTER_ERROR in second.text

        db = SessionLocal()
        try:
            assert db.query(User).filter(User.phone == phone).count() == 1
        finally:
            db.close()
    finally:
        _cleanup(phone)


@requires_postgres
def test_error_preserves_phone_and_never_echoes_password():
    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    submitted_password = "never-echo-this-password"
    try:
        assert _client().post(
            "/auth/register",
            data={"phone": phone, "name": "UI Test", "password": PASSWORD, "role": "driver"},
        ).status_code in (200, 302)

        response = _client().post(
            "/auth/login", data={"phone": phone, "password": submitted_password}
        )
        assert response.status_code == 401
        assert phone in response.text
        assert submitted_password not in response.text
    finally:
        _cleanup(phone)


@requires_postgres
def test_unknown_phone_uses_same_login_error():
    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    try:
        response = _client().post(
            "/auth/login", data={"phone": phone, "password": PASSWORD}
        )
        assert response.status_code == 401
        assert LOGIN_ERROR in response.text
    finally:
        _cleanup(phone)


@requires_postgres
def test_register_error_preserves_name_and_role():
    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    try:
        assert _client().post(
            "/auth/register",
            data={"phone": phone, "name": "UI Test", "password": PASSWORD, "role": "driver"},
        ).status_code in (200, 302)

        response = _client().post(
            "/auth/register",
            data={"phone": phone, "name": "Second Person", "password": PASSWORD, "role": "shipper"},
        )
        assert response.status_code == 409
        assert 'value="Second Person"' in response.text
        assert re.search(r'<option[^>]*value="shipper"[^>]*selected', response.text)
    finally:
        _cleanup(phone)
