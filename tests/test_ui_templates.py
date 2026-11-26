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

from app.auth.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User, UserRole

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


def _client(follow_redirects: bool = True) -> TestClient:
    from app.main import app

    return TestClient(app, follow_redirects=follow_redirects)


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
def test_light_theme_shell(path):
    body = _client().get(path).text
    for token in (
        "bg-white",
        "border-gray-200",
        "rounded-2xl",
        "shadow-",
        "from-pink-50",
        "via-white",
        "to-violet-100",
        "text-gray-800",
    ):
        assert token in body, token
    assert 'color-scheme" content="light"' in body
    for token in (
        "backdrop-blur",
        "bg-white/10",
        "text-white/",
        "from-blue-700",
        "via-indigo-700",
        "to-purple-700",
        "#4338ca",
    ):
        assert token not in body, token


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
    for token in (
        "from-violet-600",
        "to-pink-600",
        "hover:-translate-y-0.5",
        "hover:shadow-xl",
        "focus-visible:ring-2",
        "focus-visible:ring-violet-600",
    ):
        assert token in classes, token
    for token in ("from-blue-500", "to-purple-500"):
        assert token not in classes, token


def test_dashboard_uses_same_shell_and_destructive_logout():
    body = _client().get("/dashboard").text
    assert "bg-white" in body
    assert "backdrop-blur" not in body
    assert "داشبورد" in body
    assert 'action="/auth/logout"' in body
    buttons = _tags(body, "button")
    assert buttons
    logout_classes = buttons[0][0].get("class", "").split()
    for token in ("bg-red-50", "text-red-700", "border-red-200"):
        assert token in logout_classes, token


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
        for token in ("bg-red-50", "text-red-700", "border-red-200"):
            assert token in response.text, token
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
        for token in ("bg-red-50", "text-red-700", "border-red-200"):
            assert token in second.text, token
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


# --------------------------------------------------------------------------- #
# Dashboard redesign (docs/SPEC-dashboard.md, AC-1 … AC-6, AC-10)
# --------------------------------------------------------------------------- #

CARD_TITLES = ("لیست بارهای موجود", "نوبت‌دهی بارگیری", "بارنامه دیجیتال")
CARD_ROUTES = ("/cargos", "/time-slots", "/bol")
FLEET_TITLE = "مدیریت ناوگان"

ROLE_LABELS = {
    "driver": "راننده",
    "shipper": "صاحب کالا / انبار",
    "carrier": "شرکت حمل و نقل",
    "admin": "مدیر سیستم",
}
ROLE_PILL_TOKENS = {
    "driver": ("bg-blue-50", "text-blue-700"),
    "shipper": ("bg-emerald-50", "text-emerald-700"),
    "carrier": ("bg-purple-50", "text-purple-700"),
    "admin": ("bg-orange-50", "text-orange-700"),
}
FLEET_ROLES = ("carrier", "admin")

GENERIC_GREETING = "به باربری هوشمند خوش آمدید."


def _articles(html: str):
    """Every <article>…</article> block (cards are not nested)."""
    return re.findall(r"<article\b.*?</article>", html, re.DOTALL)


def _dashboard_card(html: str, title: str) -> str | None:
    return next((a for a in _articles(html) if title in a), None)


def _create_user(phone: str, name: str, role: str) -> None:
    """Insert a user directly: the register form intentionally refuses `admin`."""
    db = SessionLocal()
    try:
        db.add(
            User(
                phone=phone,
                name=name,
                password_hash=hash_password(PASSWORD),
                role=UserRole(role),
            )
        )
        db.commit()
    finally:
        db.close()


def test_dashboard_shows_three_cards_anonymously():
    body = _client().get("/dashboard").text
    articles = _articles(body)
    assert len(articles) == 3, articles

    for title, route in zip(CARD_TITLES, CARD_ROUTES):
        article = next((a for a in articles if title in a), None)
        assert article is not None, title
        assert re.search(r'<svg\b[^>]*aria-hidden="true"', article), title
        assert re.search(rf"<h2\b[^>]*>\s*{re.escape(title)}\s*</h2>", article), title
        assert re.search(r"<p\b[^>]*>[^<]+</p>", article), title
        if route == "/cargos":
            # The cargo card is now a real route (SPEC-core §8).
            assert re.search(r'<a\b[^>]*href="/cargos"', article), title
            assert f'data-future-route="{route}"' not in article, title
        else:
            assert re.search(rf'<a\b[^>]*data-future-route="{re.escape(route)}"', article), title
        # Light theme: pure white cards, subtle border/shadow, no glassmorphism.
        for token in ("bg-white", "rounded-2xl", "border-gray-200", "shadow-"):
            assert token in article, (title, token)
        assert "backdrop-blur" not in article, title

    # The Fleet card is not merely hidden: it must not be in the DOM.
    assert FLEET_TITLE not in body


def test_dashboard_grid_and_container():
    body = _client().get("/dashboard").text
    for token in ("grid-cols-1", "sm:grid-cols-2", "lg:grid-cols-4"):
        assert token in body, token
    # D2 = A: the dashboard overrides the default shell width.
    assert "max-w-6xl" in body

    # Auth pages must keep the narrow default.
    for path in ("/auth/login", "/auth/register"):
        auth_body = _client().get(path).text
        assert "max-w-md" in auth_body, path
        assert "max-w-6xl" not in auth_body, path


def test_dashboard_header_single_h1_generic_greeting_and_logout():
    body = _client().get("/dashboard").text
    assert len(re.findall(r"<h1\b", body)) == 1, "dashboard must have exactly one h1"
    assert GENERIC_GREETING in body
    assert 'action="/auth/logout"' in body

    buttons = _tags(body, "button")
    assert buttons, "dashboard has no button"
    assert "bg-red-50" in buttons[0][0].get("class", "").split()
    # Anonymous visitors get no role badge.
    assert "data-role-badge" not in body


def test_dashboard_ignores_invalid_cookie():
    client = _client()
    client.cookies.set("access_token", "not-a-jwt")
    response = client.get("/dashboard")
    body = response.text
    assert response.status_code == 200, body
    assert GENERIC_GREETING in body
    assert "data-role-badge" not in body
    assert FLEET_TITLE not in body


@requires_postgres
@pytest.mark.parametrize("role", ["driver", "shipper", "carrier", "admin"])
def test_dashboard_role_identity(role):
    Base.metadata.create_all(bind=engine)
    phone = _new_phone()
    name = f"کاربر {role}"
    _create_user(phone, name, role)
    try:
        client = _client(follow_redirects=False)
        login = client.post("/auth/login", data={"phone": phone, "password": PASSWORD})
        assert login.status_code == 303, login.text

        body = client.get("/dashboard").text
        assert name in body, role
        assert ROLE_LABELS[role] in body, role

        badge = re.search(r"<span\b[^>]*data-role-badge[^>]*>", body)
        assert badge is not None, role
        badge_classes = _attrs(badge.group(0)).get("class", "")
        for token in ROLE_PILL_TOKENS[role]:
            assert token in badge_classes, (role, token)

        # Identity is rendered, but the phone number must never reach the page.
        assert phone not in body, role
        # Fleet: carrier and admin see it; driver and shipper never do.
        assert (FLEET_TITLE in body) is (role in FLEET_ROLES), role
    finally:
        _cleanup(phone)
