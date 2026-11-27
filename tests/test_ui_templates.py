"""Tests for the shared navy/yellow shell, dashboard, and login error states.

Markup tests need no database; the failure paths register/login real users and
are therefore PostgreSQL-gated, matching ``tests/test_auth.py``.

Role-form contracts and registration error paths live in
``tests/test_registration_ui.py``.
"""

import os
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User, UserRole
from tests.support import PASSWORD, driver_payload, new_phone, new_username

DATABASE_URL = os.getenv("DATABASE_URL", "")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL.lower().startswith(("postgres", "postgresql")),
    reason="Auth failure tests require PostgreSQL (set DATABASE_URL to a postgres URL).",
)

PAGES = (
    "/auth/login",
    "/auth/register",
    "/auth/register/driver",
    "/auth/register/shipper",
    "/auth/register/admin",
    "/auth/admin/login",
    "/dashboard",
)

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


def _main_class(body: str) -> str:
    match = re.search(r"<main[^>]*class=\"([^\"]*)\"", body)
    assert match is not None, "no <main> element"
    return match.group(1)


def _cleanup(*phones, usernames=()):
    db = SessionLocal()
    try:
        if phones:
            db.query(User).filter(User.phone.in_(phones)).delete(
                synchronize_session=False
            )
        if usernames:
            db.query(User).filter(User.username.in_(usernames)).delete(
                synchronize_session=False
            )
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Markup / contract
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
def test_navy_yellow_white_shell(path):
    body = _client().get(path).text
    for token in (
        "bg-[#0a192f]",
        "bg-[#fbbf24]",
        "bg-white",
        "text-white",
        'color-scheme" content="light"',
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
def test_brand_row_with_truck_icon(path):
    body = _client().get(path).text
    assert 'data-brand="smart-freight"' in body
    assert "باربر هوشمند" in body
    assert "truck" not in body.lower() or "<svg" in body.lower()
    assert "<svg" in body.lower()


@pytest.mark.parametrize("path", PAGES)
def test_no_alert_on_clean_get(path):
    assert 'role="alert"' not in _client().get(path).text


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #


def test_dashboard_grid_and_container():
    body = _client().get("/dashboard").text
    for token in ("grid-cols-1", "sm:grid-cols-2", "lg:grid-cols-4"):
        assert token in body, token
    # D2 = A: the dashboard overrides the default shell width.
    assert "max-w-6xl" in _main_class(body)

    # Auth forms keep the narrow default; the landing page is wider.
    for path in (
        "/auth/login",
        "/auth/register/driver",
        "/auth/register/shipper",
        "/auth/register/admin",
        "/auth/admin/login",
    ):
        assert "max-w-md" in _main_class(_client().get(path).text), path
    assert "max-w-5xl" in _main_class(_client().get("/auth/register").text)


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
# Failure paths
# --------------------------------------------------------------------------- #


@requires_postgres
def test_wrong_password_renders_styled_alert():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload()
    try:
        assert (
            _client()
            .post("/auth/register/driver", data=payload, follow_redirects=False)
            .status_code
            == 303
        )

        response = _client().post(
            "/auth/login",
            data={"phone": payload["phone"], "password": "definitely-wrong"},
        )
        assert response.status_code == 401, response.text
        assert 'role="alert"' in response.text
        assert 'aria-live="assertive"' in response.text
        for token in ("bg-red-50", "text-red-700", "border-red-200"):
            assert token in response.text, token
        assert LOGIN_ERROR in response.text
        assert "set-cookie" not in response.headers
    finally:
        _cleanup(payload["phone"])


@requires_postgres
def test_duplicate_phone_renders_styled_alert():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload()
    try:
        first = _client(follow_redirects=False).post(
            "/auth/register/driver", data=payload
        )
        assert first.status_code == 303, first.text

        second = _client().post(
            "/auth/register/driver", data=driver_payload(phone=payload["phone"])
        )
        assert second.status_code == 409, second.text
        assert 'role="alert"' in second.text
        for token in ("bg-red-50", "text-red-700", "border-red-200"):
            assert token in second.text, token
        assert REGISTER_ERROR in second.text

        db = SessionLocal()
        try:
            assert db.query(User).filter(User.phone == payload["phone"]).count() == 1
        finally:
            db.close()
    finally:
        _cleanup(payload["phone"])


@requires_postgres
def test_error_preserves_phone_and_never_echoes_password():
    Base.metadata.create_all(bind=engine)
    payload = driver_payload()
    submitted_password = "never-echo-this-password"
    try:
        assert (
            _client(follow_redirects=False)
            .post("/auth/register/driver", data=payload)
            .status_code
            == 303
        )

        response = _client().post(
            "/auth/login",
            data={"phone": payload["phone"], "password": submitted_password},
        )
        assert response.status_code == 401
        assert payload["phone"] in response.text
        assert submitted_password not in response.text
    finally:
        _cleanup(payload["phone"])


@requires_postgres
def test_unknown_phone_uses_same_login_error():
    response = _client().post(
        "/auth/login", data={"phone": new_phone(), "password": PASSWORD}
    )
    assert response.status_code == 401
    assert LOGIN_ERROR in response.text


@requires_postgres
def test_register_error_preserves_full_name():
    Base.metadata.create_all(bind=engine)
    first = driver_payload()
    try:
        assert (
            _client(follow_redirects=False)
            .post("/auth/register/driver", data=first)
            .status_code
            == 303
        )

        response = _client().post(
            "/auth/register/driver",
            data=driver_payload(phone=first["phone"], full_name="Second Person"),
        )
        assert response.status_code == 409
        assert 'value="Second Person"' in response.text
    finally:
        _cleanup(first["phone"])


# --------------------------------------------------------------------------- #
# Dashboard redesign
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

GENERIC_GREETING = "به باربر هوشمند خوش آمدید."


def _articles(html: str):
    """Every <article>…</article> block (cards are not nested)."""
    return re.findall(r"<article\b.*?</article>", html, re.DOTALL)


def _create_user(phone: str, name: str, role: str) -> str | None:
    """Insert a user directly: admins need a username for the admin login."""
    username = new_username() if role == "admin" else None
    db = SessionLocal()
    try:
        db.add(
            User(
                phone=phone,
                name=name,
                password_hash=hash_password(PASSWORD),
                role=UserRole(role),
                username=username,
            )
        )
        db.commit()
    finally:
        db.close()
    return username


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
        # White cards, subtle border/shadow, no glassmorphism.
        for token in ("bg-white", "rounded-2xl", "border-gray-200", "shadow-"):
            assert token in article, (title, token)
        assert "backdrop-blur" not in article, title

    # The Fleet card is not merely hidden: it must not be in the DOM.
    assert FLEET_TITLE not in body


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
def test_dashboard_role_identity(role, admin_code):
    Base.metadata.create_all(bind=engine)
    phone = new_phone()
    name = f"کاربر {role}"
    username = _create_user(phone, name, role)
    try:
        client = _client(follow_redirects=False)
        if role == "admin":
            login = client.post(
                "/auth/admin/login",
                data={
                    "username": username,
                    "password": PASSWORD,
                    "admin_code": admin_code,
                },
            )
        else:
            login = client.post(
                "/auth/login", data={"phone": phone, "password": PASSWORD}
            )
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
        _cleanup(phone, usernames=(username,) if username else ())
