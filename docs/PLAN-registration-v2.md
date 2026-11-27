# PLAN: Registration v2 — Landing, Role-Specific Forms, Admin Code, and Test Migration

## Status
Implemented — 2026-11-27 (see “Implementation record” at the end). Approved:

1. `docs/SPEC-registration-v2.md` (including decisions D1–D10),
2. `docs/adr/007-registration-v2-user-model.md`,
3. this plan.

The plan follows TDD: every new behavior gets a failing test first, and the RED reason is recorded
before implementation.

## Dependencies

- `docs/SPEC-registration-v2.md` — proposed authoritative requirements.
- `docs/adr/007-registration-v2-user-model.md` — proposed data-model/API/admin-code decisions.
- `docs/adr/003-auth-jwt-cookie.md` — accepted; cookie session unchanged.
- `docs/adr/004-login-redirect-303.md` — accepted; login still `303` → `/dashboard`.
- `docs/SPEC-auth.md` and `docs/SPEC-ui.md` — current auth docs; their registration/login page sections
  are superseded after approval.
- PostgreSQL for the full suite and all DB/concurrency tests:
  `postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test`.
- `ADMIN_CODE` environment variable for admin tests. Tests set it explicitly; production must set a
  long random value.
- Python dependencies already present: FastAPI, SQLAlchemy, Alembic, passlib/bcrypt, python-jose,
  Jinja2, python-multipart. **No new dependency is planned.**
- Dev server: `venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000`.

## Scope summary

1. Expand `users` and add one Alembic revision (ADR 007).
2. Add normalization/validation and a registration/auth service.
3. Replace the single registration route with a landing page + three role-specific forms.
4. Add a separate admin login with an admin code.
5. Add a role-aware success page.
6. Rebuild `base.html` as a navy/yellow/white shell with the «باربر هوشمند» brand.
7. Update the existing test suite for the new required fields and page contracts; add new tests.
8. Regression-test every page that extends `base.html`.

## Files

### New

| File | Purpose |
|---|---|
| `app/auth/normalization.py` | Digit/phone/national-ID/username/license/plate normalization. |
| `app/auth/service.py` | Role-specific registration, authentication, admin-code check, duplicate handling. |
| `app/auth/errors.py` | `AuthValidationError`, `RegistrationConflict`, `InvalidCredentials`, `AdminDisabled` with field/message data. |
| `templates/auth/landing.html` | Role selection page (`GET /auth/register`). |
| `templates/auth/register_driver.html` | Driver form. |
| `templates/auth/register_shipper.html` | Shipper form. |
| `templates/auth/register_admin.html` | Admin form. |
| `templates/auth/success.html` | Role-aware registration success page. |
| `templates/auth/admin_login.html` | Separate admin login. |
| `templates/macros/forms.html` | Input/select/button/alert macros with icons and error states (recommended; avoids four copies of the same markup). |
| `tests/test_registration_validation.py` | Pure unit tests for normalization/validation; runs without PostgreSQL. |
| `tests/test_registration_ui.py` | Landing/forms/login/admin-login/success markup and error-path tests. |
| `tests/test_registration_concurrency.py` | PostgreSQL-gated duplicate-registration race. |
| `alembic/versions/<rev>_registration_v2_user_model.py` | One revision for the new columns/indexes and nullable phone. |

### Modified

| File | Change |
|---|---|
| `app/models.py` | Add `username`, `national_id`, `license_number`, `truck_type`, `plate_number`, `cargo_type_preference`; make `phone` nullable; add indexes. Use `Mapped[str]` + `nullable=True` (no `Optional[...]`). |
| `app/auth/routes.py` | Landing/driver/shipper/admin/success/admin-login routes; `Form("")` defaults; service calls; `303` registration redirects; generic `401`s; `503` when admin code is unset. |
| `app/config.py` | Add `ADMIN_CODE: str = os.getenv("ADMIN_CODE", "")`. |
| `templates/base.html` | New navy header, white truck SVG, «باربر هوشمند», white card shell, yellow focus/links. Keep the one inline double-submit guard. |
| `templates/auth/login.html` | Rewrite for the new shell; phone/password only; links to registration and admin login. |
| `templates/auth/register.html` | **Delete** (replaced by `landing.html` + three role templates). |
| `templates/dashboard.html` | Brand/greeting «باربر هوشمند»; navy/yellow palette for CTAs; preserve cards, grid, role badges, logout. |
| `templates/partials/quick_links.html` | Replace violet quick-link styling with navy/yellow. |
| `templates/errors/403.html` | Replace violet gradient CTA with yellow/navy. |
| `templates/cargos/list.html` | Palette-only sweep for shared buttons/links. Behavior/markup contract unchanged. |
| `templates/shipper/cargos.html` | Palette-only sweep. |
| `templates/shipper/cargo_new.html` | Palette-only sweep. |
| `templates/driver/documents.html` | Palette-only sweep. |
| `templates/admin/documents.html` | Palette-only sweep. |
| `tests/test_auth.py` | Rewrite for role-specific forms, admin code, separate admin login, new fields/status codes. |
| `tests/test_ui_templates.py` | Remove old single-form auth tests; keep/update shared-shell and dashboard tests for the new brand/palette; admin login test. |
| `tests/support.py` | Valid numeric phones, national-ID/license/username generators, registration/login helpers. |
| `tests/conftest.py` | Add an `admin_code` fixture that sets `settings.ADMIN_CODE` and restores it; keep the guarded PostgreSQL reset. |
| `docs/SPEC-auth.md` | After approval, add a one-line supersession note pointing to this SPEC. Do not rewrite history. |
| `docs/SPEC-ui.md` | Same supersession note for auth pages. |

Not changed: `app/api/bookings.py`, `app/services/booking_service.py`, cargo/booking/document services,
`tests/test_booking_concurrency.py` (direct DB inserts, no form validation), and ADR 001–006.

## Test harness changes

### `tests/conftest.py`

- Keep the session-scoped PostgreSQL `_test` schema reset. It already recreates the `users` table from
  the updated model, so new columns/indexes are present for DB tests.
- Add:

  ```python
  @pytest.fixture
  def admin_code(monkeypatch):
      code = "test-admin-code-0123456789"
      monkeypatch.setattr(settings, "ADMIN_CODE", code)
      return code
  ```

  Tests that need the disabled state monkeypatch `settings.ADMIN_CODE` to `""`.
- Keep SQLite untouched (dev DB relies on `alembic upgrade head`). Pure unit/UI GET tests run on SQLite.

### `tests/support.py`

- `new_phone()` → canonical `+989` + 9 random digits (no hex letters).
- `new_national_id()` → 10 digits with a valid Iranian checksum (reject all-identical values).
- `new_license_number()` → unique `[0-9A-Z]{5,30}` value.
- `new_username()` → unique lowercase `[a-z0-9._-]` value, 3–50 chars.
- `make_user(role, name=None, **profile)`:
  - use `new_phone()`;
  - for `admin`, set a `username` so admin-login tests can use the account;
  - keep new profile columns nullable so existing direct-insert tests keep working.
- `driver_payload(**overrides)`, `shipper_payload(**overrides)`, `admin_payload(**overrides)`.
- `register_driver(client, **overrides)`, `register_shipper(...)`, `register_admin(...)`.
- `login_user(client, phone, password)`, `login_admin(client, username, password, admin_code)`.
- Keep `auth_headers` and `client_for` behavior unchanged; include `username` in the token payload only
  when present.

### Gating

- `tests/test_auth.py`, `test_registration_concurrency.py`, and DB-backed service/model tests:
  PostgreSQL-gated, matching the existing `DATABASE_URL` guard.
- `tests/test_registration_validation.py`: no DB; runs on SQLite.
- `tests/test_registration_ui.py`: GET/markup tests run anywhere; POST error-path tests are
  PostgreSQL-gated.
- `tests/test_ui_templates.py`: shared-shell/dashboard GET tests run anywhere; DB login tests stay
  PostgreSQL-gated.

## TDD cycles

Each cycle: write the test first, run it, record the RED reason, implement only enough to pass, run
GREEN, then refactor.

### Phase 0 — Governance

1. [x] Approve `docs/SPEC-registration-v2.md` (including D1–D10).
2. [x] Accept `docs/adr/007-registration-v2-user-model.md`.
3. [x] Approve this plan.
4. [x] Record the approvals at the top of this plan.

### Phase 1 — Normalization and validation (no DB)

5. [ ] Write `tests/test_registration_validation.py`:
   - Persian/Arabic digits normalize to Latin digits;
   - phone accepts `09...`, `+989...`, `00989...`, `989...`, and rejects landlines/short values;
   - national ID accepts a valid checksum, rejects <10/>10 digits, all-identical, and a bad checksum;
   - license normalization/uppercase and length/charset rules;
   - plate normalization (Persian digits/letters, spaces/hyphens) and length;
   - `full_name` trim/length; password length and 72-byte bcrypt guard;
   - username lowercase and regex;
   - truck/cargo allowlists reject unknown values.
6. [ ] Run `pytest tests/test_registration_validation.py -v` → RED (module missing).
7. [ ] Implement `app/auth/normalization.py` and the validator functions in `app/auth/service.py`
   (or a small `validators.py` if the service grows too large).
8. [ ] Run → GREEN.

### Phase 2 — User model and constraints

9. [ ] Write model/constraint tests (PostgreSQL-gated, in `tests/test_auth.py` or
   `tests/test_registration_validation.py` behind the PostgreSQL guard):
   - `User` has `username`, `national_id`, `license_number`, `truck_type`, `plate_number`,
     `cargo_type_preference`;
   - `phone` is nullable; an admin can be inserted with `phone=None`, `name=username`,
     `username="admin..."`;
   - unique indexes reject duplicate `username`, `national_id`, and `license_number`;
   - duplicate `NULL`s are allowed (two admins with `phone=None`, two drivers without a license number
     if legacy);
   - a duplicate `plate_number` is allowed (non-unique index).
10. [ ] Run → RED (`AttributeError` / missing column / missing index).
11. [ ] Add the columns/indexes to `User` in `app/models.py`; make `phone` nullable.
12. [ ] Run the PostgreSQL model tests → GREEN. (`create_all` from the reset fixture creates the new
    schema.)

### Phase 3 — Registration/auth service

13. [ ] Write service tests (PostgreSQL-gated):
    - `register_driver` persists normalized values, role `driver`, `name=full_name`, bcrypt hash;
    - `register_shipper` persists normalized values, role `shipper`;
    - `register_admin` requires the code, stores lowercase username, `name=username`, `phone=None`;
    - wrong admin code → `InvalidCredentials`/401-equivalent and no row;
    - empty `settings.ADMIN_CODE` → `AdminDisabled`/503-equivalent;
    - duplicate phone/national ID/license/username → `RegistrationConflict`/409-equivalent;
    - `authenticate_user` accepts driver/shipper/carrier, rejects wrong password, unknown phone, and
      admin role (generic failure);
    - `authenticate_admin` accepts username + code, legacy phone fallback, rejects wrong
      password/code, non-admin, and unset code.
14. [ ] Run → RED.
15. [ ] Implement `app/auth/errors.py` and `app/auth/service.py`; catch `IntegrityError`, rollback, and
    map to conflicts.
16. [ ] Run → GREEN.

### Phase 4 — Routes and behavior (rewrite `tests/test_auth.py`)

17. [ ] Rewrite `tests/test_auth.py` around role-specific endpoints and fields:
    - `GET /auth/register` landing 200; `POST /auth/register` 405;
    - driver registration `303` → success, DB row, normalized phone/national ID/license/plate, role,
      hash; password not plaintext;
    - shipper registration `303` → success, DB row;
    - admin registration with correct code `303` → success, `phone is None`, `name == username`;
    - wrong admin code `401`, no row; unset code `503`;
    - duplicate phone/national ID/license/username `409`, one row;
    - invalid/missing fields `422` HTML, `role="alert"`, `aria-invalid`, values preserved, password
      not echoed;
    - user login success for driver/shipper/carrier `303` `/dashboard`, HttpOnly cookie;
    - wrong password/unknown phone `401`, no cookie; admin on user login `401`, no cookie;
    - admin login success `303` `/dashboard`, cookie; wrong password/code/unknown/non-admin `401`, no
      cookie; legacy phone fallback works;
    - logout `302` and cookie deleted;
    - success page role messages/links; unknown role `404`.
18. [ ] Run `pytest tests/test_auth.py -v` with PostgreSQL → RED (routes/templates missing).
19. [ ] Implement `app/auth/routes.py` (landing/forms/POSTs/success/admin login), using `Form("")`
    defaults and the service; update `app/config.py` with `ADMIN_CODE`.
20. [ ] Run → GREEN.
21. [ ] Write `tests/test_registration_concurrency.py`:
    - two barrier-released threads, separate `TestClient`s, identical driver payload (same phone and
      national ID) → one `303`, one `409`;
    - exactly one `users` row;
    - no `500`, no unhandled `IntegrityError`.
22. [ ] Run with PostgreSQL → RED or flaky; ensure the service's `IntegrityError` handling is correct;
    run → GREEN repeatedly (at least 10 iterations locally) to confirm stability.

### Phase 5 — UI: shell, landing, forms, login, success

23. [ ] Write `tests/test_registration_ui.py` (GET/markup, no DB):
    - landing: 200, `lang="fa" dir="rtl"`, Vazirmatn, Tailwind `3.4.17`, navy/yellow tokens, white
      truck SVG, «باربر هوشمند», exactly three role links, no carrier link, no `<select name="role">`;
    - driver form: exact field names/order, labels, `required`, right-aligned icon wrappers, LTR
      numeric/secret fields, password no `value`, truck options;
    - shipper form: exact field names/order, labels, cargo options;
    - admin form: exact fields, `admin_code` type=password, no phone;
    - user login: phone/password only, no admin code, link to `/auth/admin/login`;
    - admin login: username/password/admin_code, no phone, link back;
    - success page for each role: message and correct login link; unknown role 404;
    - no framework, exactly one external `<script src>` (Tailwind), reduced-motion classes, focus
      classes, white cards, yellow buttons.
24. [ ] Add PostgreSQL-gated error-path cases in the same module:
    - duplicate phone/national ID/license/username → 409 alert, values preserved;
    - invalid national ID/phone/password → 422 alert/field messages, `aria-invalid`, no password echo;
    - wrong user login → 401 alert, phone preserved, no password echo, no `Set-Cookie`;
    - wrong admin login/code → 401 generic alert, username preserved, no password/code echo;
    - admin code unset → 503.
25. [ ] Run `pytest tests/test_registration_ui.py -v` → RED (404/templates missing).
26. [ ] Implement:
    - `templates/base.html` new shell;
    - `templates/macros/forms.html` and `templates/partials/alert.html` (if used);
    - `templates/auth/landing.html`, `register_driver.html`, `register_shipper.html`,
      `register_admin.html`, `success.html`, `admin_login.html`;
    - rewrite `templates/auth/login.html`; delete `templates/auth/register.html`.
27. [ ] Run → GREEN on SQLite (GET) and PostgreSQL (error paths).

### Phase 6 — Existing-suite migration and regression

28. [ ] Update `tests/test_ui_templates.py` **before** changing the shared shell:
    - replace the old light/violet shell expectations with navy/yellow/white tokens;
    - brand «باربر هوشمند»; greeting «به باربر هوشمند خوش آمدید.»;
    - remove old `test_login_field_contract` / `test_register_field_contract` / old failure paths
      (moved to `test_registration_ui.py`);
    - keep dashboard card/grid/role-badge tests, with updated visual tokens;
    - change `test_dashboard_role_identity[admin]` to log in via `/auth/admin/login` with a username
      and the `admin_code` fixture;
    - keep `max-w-md` for login/role forms, `max-w-5xl` for the landing page, `max-w-6xl` for
      dashboard.
29. [ ] Run `pytest tests/test_ui_templates.py -v` → RED for the intended shell/brand changes.
30. [ ] Update `templates/dashboard.html`, `partials/quick_links.html`, `errors/403.html`, and the
    cargo/document templates for the palette/brand. Do not change page behavior or data.
31. [ ] Run `pytest tests/test_ui_templates.py -v` → GREEN.
32. [ ] Run the rest of the suite unchanged:
    `pytest tests/test_documents.py tests/test_cargos.py tests/test_cargo_booking.py
    tests/test_cargo_concurrency.py tests/test_core_ui.py -v` → GREEN.
33. [ ] Run `pytest tests/test_booking_concurrency.py -v` → GREEN (unchanged direct-insert test).
34. [ ] Run the full PostgreSQL suite → all collected tests pass. Record the new count and note that the
    pre-v2 139 tests were preserved or intentionally migrated (no silently weakened assertions).
35. [ ] Defer the full SQLite suite until after the Phase 7 migration (step 42a). Before the migration,
    the dev SQLite schema lacks the new `users` columns, so DB-backed SQLite tests would fail for the
    expected reason.

### Phase 7 — Migration

36. [ ] Bring a scratch PostgreSQL DB to the current head:
    `alembic upgrade head` on `smart_freight_migration_test`.
37. [ ] Run pre-migration duplicate checks:
    - `SELECT phone, count(*) FROM users WHERE phone IS NOT NULL GROUP BY phone HAVING count(*) > 1;`
      must return zero rows;
    - the new columns do not exist yet, so no new duplicate check is needed.
38. [ ] Generate the revision:
    `alembic revision --autogenerate -m "registration v2 user model"`.
39. [ ] Hand-edit the revision:
    - add the six nullable columns;
    - `batch_alter_table("users")` → `alter_column("phone", nullable=True)`;
    - create unique indexes `ix_users_username`, `ix_users_national_id`,
      `ix_users_license_number`, and non-unique `ix_users_plate_number`;
    - downgrade drops indexes/columns and restores `phone NOT NULL` (batch for SQLite);
    - add a comment about the null-phone downgrade caveat.
40. [ ] Run `alembic upgrade head` → `alembic check` (no pending changes) → `alembic downgrade -1` →
    `alembic upgrade head` on the scratch DB.
41. [ ] Apply to the dev SQLite DB:
    `$env:DATABASE_URL = "sqlite:///./barbar_smart.db"; alembic upgrade head`.
42. [ ] Verify `alembic check` is clean on the dev SQLite DB.
42a. [ ] Run the full SQLite suite (`DATABASE_URL` unset) → PostgreSQL-only modules skip, no failures.
43. [ ] Re-run the full PostgreSQL suite against the migrated schema (the reset fixture recreates it,
    but the migration must still be proven independently).

### Phase 8 — Manual QA and close-out

44. [ ] Run the dev server against the migrated SQLite DB.
45. [ ] Execute the manual QA matrix below; record date/browser/results here.
46. [ ] Clean up QA users, admin accounts, cargos, bookings, documents, uploaded files, screenshots;
    close tabs.
47. [ ] Mark this plan Implemented with RED/GREEN counts, migration results, and QA results.
48. [ ] Add the supersession note to `docs/SPEC-auth.md` and `docs/SPEC-ui.md`.

## Test migration table

| Existing test / helper | Change | Reason |
|---|---|---|
| `tests/test_auth.py::_register` | Replace with `register_driver/shipper/admin` helpers and role-specific payloads. | `POST /auth/register` is removed; required fields differ by role. |
| `test_register_success` | Post to `/auth/register/driver`; assert `303`, role, fields, hash. | New driver contract and success redirect. |
| `test_register_duplicate_phone` | Use a valid driver payload; still assert `409`. | Phone validation/duplicates. |
| `test_login_wrong_password` | Register a valid driver first; assert `401`. | Required fields/phone normalization. |
| `test_login_success_sets_cookie` | Register a valid driver; assert `303` `/dashboard` + HttpOnly. | Unchanged contract, new fixture data. |
| `test_password_not_plaintext` | Use driver payload; assert hash. | New fields. |
| `tests/test_ui_templates.py::PAGES` | Add landing/role forms/admin login/success; keep dashboard. | New pages. |
| `test_light_theme_shell` | Replace with navy/yellow/white shell assertions. | New design system. |
| `test_brand_row_with_truck_icon` | Assert «باربر هوشمند» and the white truck SVG in the header. | Corrected brand. |
| `test_login_field_contract` | Move to `test_registration_ui.py`; phone/password only, admin link. | Split auth tests. |
| `test_register_field_contract` | Replace with three role-form contracts in `test_registration_ui.py`. | No single form/role select. |
| `test_primary_buttons_are_gradient` | Replace with yellow `#fbbf24` primary button assertions. | New palette. |
| `test_dashboard_uses_same_shell_and_destructive_logout` | Update shell tokens; keep red logout semantics. | Shared shell change. |
| `test_dashboard_grid_and_container` | Keep `max-w-6xl`; login/role forms `max-w-md`; landing `max-w-5xl`. | Layout preserved; landing is wider than a form. |
| `test_dashboard_header_single_h1...` | Update greeting to «به باربر هوشمند خوش آمدید.» | Brand correction. |
| `test_dashboard_role_identity[admin]` | Log in via `/auth/admin/login` with username + admin code; update `_create_user` to set a username for admins. | Admins are blocked from `/auth/login`. |
| `tests/support.py::make_user` | Use `new_phone()`; add `username` for admins; keep profile columns optional. | Valid phones for login tests; admin login. |
| `tests/test_ui_templates.py::_new_phone` | Replace hex suffix with numeric phone or import `support.new_phone`. | Phone validation. |
| `tests/test_ui_templates.py::_create_user` | Set `username` for the admin case and use a valid phone. | Admin login requires a username. |
| `tests/test_booking_concurrency.py` | No change (direct DB inserts, no form/login). | Not affected by form validation. |
| `tests/test_documents.py`, `test_cargos.py`, `test_cargo_booking.py`, `test_cargo_concurrency.py`, `test_core_ui.py` | No expected changes; run regression. Update only if a visual-token assertion is found. | Behavior preserved. |

No assertion may be removed merely to make it pass. If a contract genuinely changes, the new assertion
must cover the replacement behavior and be listed above.

## Migration notes

One revision after `cc9ac3ac14f8_phase_1_core_flow.py`:

1. `op.add_column("users", sa.Column("username", sa.String(50), nullable=True))` and the five other
   nullable columns.
2. `with op.batch_alter_table("users") as batch: batch.alter_column("phone", existing_type=sa.String(20), nullable=True)`
   so SQLite and PostgreSQL both work.
3. `op.create_index("ix_users_username", "users", ["username"], unique=True)`;
   same for `national_id` and `license_number`; non-unique for `plate_number`.
4. No username backfill. Legacy admins use the phone fallback at `/auth/admin/login`.
5. Downgrade:
   - drop the four indexes;
   - `batch_alter_table("users")` → drop the six columns;
   - `batch_alter_table("users")` → `alter_column("phone", nullable=False)`.
   - This fails if any v2 admin has `phone IS NULL`. Document that downgrade is for scratch/empty DBs
     or after deleting/updating those admins.
6. The model must declare the same indexes in `User.__table_args__` so `create_all` and Alembic agree.
   Use `Mapped[str]` + `nullable=True` (not `Optional[...]`) because of the repository's SQLAlchemy
   2.0.35 / Python 3.14 annotation limitation (see `Booking.time_slot_id`).
7. Alembic autogenerate may create unique constraints instead of unique indexes or may drop
   dialect-specific details. Hand-check the generated file and run `alembic check`.
8. Deploy order: migration first (additive), then app. Old code ignores the new columns and null phones.
9. Back up `users` before running the migration in any non-scratch environment.

## Commands

```powershell
# --- Tests: dedicated PostgreSQL test DB (schema reset by tests/conftest.py) ---
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
$env:ADMIN_CODE = "test-admin-code-0123456789"

# RED -> GREEN per cycle
venv\Scripts\python.exe -m pytest tests/test_registration_validation.py -v
venv\Scripts\python.exe -m pytest tests/test_auth.py -v
venv\Scripts\python.exe -m pytest tests/test_registration_concurrency.py -v
venv\Scripts\python.exe -m pytest tests/test_registration_ui.py -v
venv\Scripts\python.exe -m pytest tests/test_ui_templates.py -v

# Regression
venv\Scripts\python.exe -m pytest tests/test_documents.py tests/test_cargos.py tests/test_cargo_booking.py tests/test_cargo_concurrency.py tests/test_core_ui.py -v
venv\Scripts\python.exe -m pytest tests/test_booking_concurrency.py -v
venv\Scripts\python.exe -m pytest tests/ -v

# --- Migration: scratch DB, brought to the previous head first ---
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_migration_test"
venv\Scripts\python.exe -m alembic upgrade head
venv\Scripts\python.exe -m alembic revision --autogenerate -m "registration v2 user model"
venv\Scripts\python.exe -m alembic upgrade head
venv\Scripts\python.exe -m alembic check
venv\Scripts\python.exe -m alembic downgrade -1
venv\Scripts\python.exe -m alembic upgrade head

# --- Dev SQLite: apply the new revision before running the app ---
$env:DATABASE_URL = "sqlite:///./barbar_smart.db"
venv\Scripts\python.exe -m alembic upgrade head
venv\Scripts\python.exe -m alembic check

# --- Dev server ---
$env:ADMIN_CODE = "<long random value>"
venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

## Manual QA matrix

| Area | Check | Expected |
|---|---|---|
| Landing | Open `/auth/register` | Navy header, white truck, «باربر هوشمند», three role cards, no carrier |
| Landing | 320 / 390 / 768 / 1024 / 1440 px | Cards stack/expand; no horizontal scroll |
| Driver | Submit valid form | 303 → success page; row has normalized phone/ID/license/plate; hash stored |
| Driver | Invalid national ID checksum | 422 alert/field error; values preserved; no row |
| Driver | Duplicate phone / national ID / license | 409 styled alert; one row |
| Shipper | Submit valid form | 303 → success page; row has cargo preference/national ID |
| Admin | Register with correct code | 303 → success; `phone` null; username lowercase; `name = username` |
| Admin | Register with wrong code | 401 alert; no row; username preserved; code not echoed |
| Admin | Register with `ADMIN_CODE` unset | 503 generic page |
| Login | Driver/shipper/carrier correct phone/password | 303 `/dashboard`; HttpOnly cookie; dashboard shows name/role |
| Login | Wrong password / unknown phone | 401 alert; phone preserved; no cookie |
| Login | Admin on `/auth/login` | 401 generic; no cookie; no role leak |
| Admin login | Correct username/password/code | 303 `/dashboard`; cookie; dashboard shows admin |
| Admin login | Wrong password/code / non-admin | 401 generic; no cookie; username preserved |
| Admin login | Legacy admin phone fallback | Phone + password + code works |
| Success | Driver/shipper/admin role links | Correct login page per role |
| Success | Unknown `role` | 404 |
| Forms | Labels/icons/focus | Every field labeled; icons on the right; visible yellow focus ring |
| Forms | Password/admin code | Never prefilled; never echoed on error |
| Accessibility | Keyboard Tab order | Logical; no traps; alerts announced |
| Accessibility | 200% zoom / JS disabled | Usable; forms still submit |
| Regression | `/dashboard`, `/cargos`, `/shipper/cargos`, `/shipper/cargos/new`, `/driver/documents`, `/admin/documents`, `/errors/403` | Render under the new shell; behavior unchanged |
| Console | All pages | No JS errors; only the Tailwind external script |
| Privacy | Dashboard/admin queue/logs | No national ID/license/plate/password/admin code |

## Rollback

- Revert the app/template/test commit(s).
- On a scratch database, run `alembic downgrade -1`. Before downgrading a non-scratch database, delete
  or assign phones to v2 admin accounts (`phone IS NULL`), otherwise `phone NOT NULL` fails.
- Downgrade drops the new columns and their data. Existing users, phones, passwords, roles, and all
  cargo/booking/document data are untouched.
- The old app ignores the dropped columns, so a DB-first rollback is safe; an app-first rollback with
  the new columns still present is also safe for existing users, but v2 admins with null phones cannot
  use the old phone login.
- Restore the old auth templates/tests if the redesign is reverted. Do not leave a half-migrated test
  suite.
- No new external dependency or uploaded file is introduced, so there is nothing else to clean up.

## Definition of done

- [ ] SPEC-registration-v2 approved; ADR 007 accepted; this plan approved; no open decisions.
- [ ] Every new production module had a failing test before it was written; RED reasons recorded per
      cycle.
- [ ] Driver, shipper, and admin registration work end-to-end; success page and login links are correct.
- [ ] Admin registration and admin login require `ADMIN_CODE`; unset code returns `503`; no default
      secret exists.
- [ ] Duplicate phone/national ID/license/username returns `409`; the PostgreSQL concurrency test shows
      one success + one `409`, one row, no `500`.
- [ ] User login accepts driver/shipper/carrier and rejects admins; admin login accepts only admins.
- [ ] The legacy `POST /auth/register` is removed; all docs/tests/links use the new routes.
- [ ] Navy/yellow/white shell, «باربر هوشمند», Vazirmatn, right-aligned icons, yellow buttons, and
      accessible error states are implemented on all auth pages.
- [ ] Dashboard and existing pages render correctly under the new shell; no behavior regression.
- [ ] Full PostgreSQL suite green; SQLite run has no failures (PostgreSQL-only modules skip).
- [ ] Migration `upgrade head` → `alembic check` → `downgrade -1` → `upgrade head` verified on a
      scratch PostgreSQL DB; dev SQLite upgraded and `alembic check` clean.
- [ ] No password, admin code, national ID, license number, or plate number leaks into logs, JWTs,
      dashboards, or public pages.
- [ ] Manual QA matrix passed; no horizontal scroll at 320–1440 px; keyboard/JS-disabled checks pass.
- [ ] This plan is marked Implemented with recorded RED/GREEN counts, migration output, and QA results.

## Implementation record (2026-11-27)

TDD cycles and results:

| Cycle | RED reason observed | GREEN result |
|---|---|---|
| Validation + service | `ModuleNotFoundError: No module named 'app.auth.service'` | 188-line unit module passes on SQLite |
| Model/constraints | `AttributeError: Settings has no attribute 'ADMIN_CODE'`; missing `User` columns | model + index tests pass on PostgreSQL |
| Routes/behaviour | `AttributeError` on `settings.ADMIN_CODE`, 404 for `/auth/register/driver` | `tests/test_auth.py` green |
| UI/markup | 404/missing templates for the five new pages | `tests/test_registration_ui.py` green |
| Concurrency | endpoint absent | 1 success + 1 `409`, one row; 10/10 repeated runs green |

Suites:

- SQLite (`DATABASE_URL` unset): **135 passed, 142 skipped**, 0 failed. The skips are the
  PostgreSQL-gated DB/concurrency modules.
- PostgreSQL (`smart_freight_test`): **277 passed, 0 failed** (the pre-v2 139 tests are preserved or
  intentionally migrated per the table above; no assertion was dropped).
- `tests/test_registration_concurrency.py`: 10 consecutive green runs.

Migrations:

- New revision `3c0fb3fec533_registration_v2_user_model` (down from `cc9ac3ac14f8`).
- Scratch PostgreSQL DB: `upgrade head` → `alembic check` (no new operations) → `downgrade -1` →
  `upgrade head`, all successful.
- Dev SQLite `barbar_smart.db` upgraded to `3c0fb3fec533`; `alembic check` clean. A pre-migration
  copy was written to the system temp folder.

Notes and limits:

- `ADMIN_CODE` has no default; the running dev server uses a local development value only.
- The manual QA matrix (responsive widths, keyboard order, 200% zoom, JS-disabled, console error
  sweep) was **not executed**; the pages were only fetched to confirm `200` responses and the dev
  server preview was opened on `/auth/register`.
- Supersession notes added to `docs/SPEC-auth.md` and `docs/SPEC-ui.md`.

## Follow-ups (not in this plan)

- CSRF tokens for auth/admin forms; rate limiting and lockout for login/admin login.
- Per-admin codes, admin invitations, admin user management, and an admin audit log.
- Company/legal-entity registration (`company_id`, 11-digit legal ID).
- Profile-completion flow for existing drivers/shippers with missing new fields.
- Password reset/OTP/email verification and a password-strength meter.
- Tailwind build pipeline and CSP hardening.
- Replace the inline truck SVG with a designed brand asset if one is provided.
- Update `docs/SRS.md` role/FR statuses after v2 ships (the SRS is the baseline, not part of this
  plan).
