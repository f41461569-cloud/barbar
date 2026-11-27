# ADR 007: Registration v2 — Expanded User Model, Role-Specific Registration, and Admin Code

## Status
Accepted — 2026-11-27. Approved with `docs/SPEC-registration-v2.md` and `docs/PLAN-registration-v2.md`.

## Date
2026-11-27

## Context

The current registration flow is a single form that posts `phone`, `name`, `password`, and `role` to
`POST /auth/register`. The `users` table only has `id`, `phone`, `name`, `password_hash`, `role`, and
`created_at`. Login is a shared phone/password form, and admins cannot self-register.

The new registration design needs:

- a landing page that sends the visitor to a **driver**, **shipper**, or **admin** registration form;
- driver-specific data (`national_id`, `license_number`, `truck_type`, `plate_number`);
- shipper-specific data (`national_id`, `cargo_type_preference`);
- an admin account identified by `username` and protected by an `admin_code`;
- a separate admin login that also requires the admin code;
- a success page between registration and login.

This is both a data-model change and a change to the public HTML form contract. AGENTS.md requires an
ADR for a data-model or public-API change, and `docs/SPEC-ui.md` §13 requires an ADR before changing a
form endpoint's status code. ADR 003 (JWT cookie) and ADR 004 (303 after login) remain in force.

## Decision

### 1. Expand `users` instead of adding profile tables

Add the following nullable columns to `users`. `nullable=True` is intentional: existing users predate
these fields, and admins/carriers do not use most of them.

| Column | Type | Null | Constraint / use |
|---|---|---|---|
| `username` | `varchar(50)` | yes | unique index; lowercase; admin login identifier |
| `national_id` | `varchar(10)` | yes | unique index; driver and shipper |
| `license_number` | `varchar(30)` | yes | unique index; driver |
| `truck_type` | `varchar(30)` | yes | application allowlist; driver |
| `plate_number` | `varchar(20)` | yes | non-unique index; driver |
| `cargo_type_preference` | `varchar(30)` | yes | application allowlist; shipper |

Also:

- Make `users.phone` **nullable**. Admins are created with a username and no phone. PostgreSQL and
  SQLite both allow multiple `NULL`s in a unique index, so the existing unique phone index remains
  valid.
- Keep `users.name` as the display/full name. The registration form field is `full_name`, and the
  route stores it in `name`. No redundant `full_name` column is added.
- Keep `users.role` as the existing `UserRole` enum (`driver`, `shipper`, `carrier`, `admin`).
- Keep `users.password_hash` as the bcrypt hash.
- Do **not** add `admin_code` to `users`. The admin code is a deployment secret, not per-user data.

Role-specific required fields are enforced in the application layer, not by a database `CHECK`. Existing
drivers/shippers legitimately have `NULL` in the new columns, and a role-conditional constraint would
make the migration brittle. Unique and length rules are still backed by database indexes/column types.

### 2. Role-specific registration routes

| Method | Path | Purpose | Success |
|---|---|---|---|
| GET | `/auth/register` | landing page with three role choices | `200` |
| GET | `/auth/register/driver` | driver registration form | `200` |
| POST | `/auth/register/driver` | create driver | `303` → `/auth/register/success?role=driver` |
| GET | `/auth/register/shipper` | shipper registration form | `200` |
| POST | `/auth/register/shipper` | create shipper | `303` → `/auth/register/success?role=shipper` |
| GET | `/auth/register/admin` | admin registration form | `200` |
| POST | `/auth/register/admin` | create admin | `303` → `/auth/register/success?role=admin` |
| GET | `/auth/register/success` | role-aware success page (`role` query parameter) | `200` |
| GET | `/auth/login` | non-admin login form | `200` |
| POST | `/auth/login` | authenticate driver/shipper/carrier | `303` → `/dashboard` |
| GET | `/auth/admin/login` | separate admin login form | `200` |
| POST | `/auth/admin/login` | authenticate admin with code | `303` → `/dashboard` |
| POST | `/auth/logout` | clear the cookie (unchanged) | `302` → `/auth/login` |

The legacy `POST /auth/register` is **removed**; `GET /auth/register` now serves the landing page, so a
POST to that path returns `405`. This is an HTML form contract change, not a JSON API change, but it is
still recorded here.

Registration success uses `303 See Other` (POST → Redirect → GET), matching the reasoning of ADR 004.
The success page is a plain GET and does not carry user data.

### 3. Fields and ownership

| Role | Form fields |
|---|---|
| Driver | `full_name`, `phone`, `national_id`, `license_number`, `truck_type`, `plate_number`, `password` |
| Shipper | `full_name`, `phone`, `cargo_type_preference`, `national_id`, `password` |
| Admin | `username`, `password`, `admin_code` |
| User login | `phone`, `password` |
| Admin login | `username`, `password`, `admin_code` |

- `full_name` maps to `users.name`; `phone` to `users.phone`; `national_id` to `users.national_id`;
  `license_number` to `users.license_number`; `truck_type` to `users.truck_type`; `plate_number` to
  `users.plate_number`; `cargo_type_preference` to `users.cargo_type_preference`.
- Admin `name` is set to the username because `name` is `NOT NULL` and admins do not provide a full name.
- Admin accounts have `phone = NULL`.
- `national_id` is used for both drivers and shippers. A separate `company_id` column is **not** added in
  v2; legal-entity/company registration is a follow-up.
- Carrier registration is retired from the public UI. `UserRole.CARRIER` remains, existing carrier
  accounts keep working, and carriers may use the normal phone/password login. New carrier accounts are
  provisioned out of band until admin user management exists.

### 4. Admin code policy

- Add `ADMIN_CODE` to `app/config.py`, read from the environment, with an empty default.
- The code is **never stored in the database**, never rendered back, and never logged.
- Admin registration and admin login both require the code. Compare it with
  `secrets.compare_digest`.
- If `ADMIN_CODE` is empty, both admin routes return `503` with a generic "admin login is not
  configured" page. This avoids shipping a known default secret.
- A wrong code returns `401` with a generic message. Do not reveal whether the username exists.
- Rotating the code does not invalidate already-issued JWTs; they expire after the existing 60-minute
  lifetime. This is acceptable for v2 and documented as a consequence.

### 5. Separate login and compatibility

- `/auth/login` accepts non-admin users only (`driver`, `shipper`, `carrier`). If an admin account is
  used there, return the same generic `401` as a wrong password; do not reveal the role.
- `/auth/admin/login` accepts admin users only. If a non-admin account is used there, return the same
  generic admin error.
- Admin login resolves the identifier by `users.username` first. For legacy admin rows created before
  v2 (which have a phone and no username), fall back to a normalized phone lookup. This bridge avoids a
  destructive backfill and can be removed once every admin has a username.
- Login success keeps ADR 004: `303` → `/dashboard` and an HttpOnly, SameSite=Lax `access_token`
  cookie. The JWT payload keeps `sub` and `role`; `phone`/`username` are included only when present.

### 6. Validation, normalization, and uniqueness

- **Phone**: normalize Persian/Arabic digits and `+98` / `0098` / `98` / `0` prefixes; store the
  canonical `+989xxxxxxxxx` form. Accept Iranian mobile numbers only.
- **National ID**: normalize digits, require exactly 10 digits, reject all-identical values, and verify
  the standard Iranian national-ID checksum. Store as a 10-character string (leading zero preserved).
- **License number**: trim, normalize digits/letters to uppercase, require 5–30 characters from
  `[0-9A-Za-z-]`; unique.
- **Plate number**: trim, normalize Persian/Arabic digits and letters, require 5–20 characters; indexed
  but not unique (a truck may be shared by more than one driver).
- **Username**: trim, lowercase, require 3–50 characters matching
  `^[a-z0-9][a-z0-9._-]{2,49}$`; unique.
- **Password**: 8–72 characters, not all whitespace, and at most 72 UTF-8 bytes because bcrypt
  truncates beyond that. Passwords are hashed with bcrypt and never logged or echoed.
- **Truck type** allowlist (v2): `pickup` (وانت), `khavar` (خاور), `truck` (کامیون), `trailer`
  (تریلی), `refrigerated` (یخچالدار), `tanker` (تانکر).
- **Cargo type preference** allowlist (v2): `general` (عمومی), `perishable` (فاسدشدنی), `fragile`
  (شکستنی), `bulk` (فله), `hazardous` (خطرناک), `heavy` (ماشین‌آلات / سنگین).
- Uniqueness is enforced by database indexes **and** mapped to `409` on `IntegrityError`, so a
  query-then-insert race cannot create a duplicate or a 500.

### 7. Status codes

| Condition | Status |
|---|---|
| Successful registration | `303` → success page |
| Missing/invalid form field (HTML form) | `422`, re-rendered form |
| Duplicate phone/national ID/license/username | `409`, re-rendered form |
| Wrong user credentials | `401`, no cookie |
| Wrong admin credentials or admin code | `401`, no cookie |
| Admin code not configured | `503` |
| Successful login | `303` → `/dashboard`, cookie set |
| Removed legacy `POST /auth/register` | `405` |

Form handlers use `Form("")` defaults and validate in the service so missing fields render the styled
HTML form instead of FastAPI's JSON `422` response.

### 8. UI shell and brand

- `templates/base.html` becomes a shared shell with a dark-navy (`#0a192f`) header, a white inline SVG
  truck logo, and the brand text «باربر هوشمند» (the current UI says «باربری هوشمند»; v2 corrects it).
- Page background is dark navy; content sits in white rounded cards. Primary actions are bright yellow
  (`#fbbf24`) with dark navy/black text.
- All auth pages use Vazirmatn and the pinned Tailwind Play CDN (`3.4.17`). No CSS framework, no build
  step, no new image asset (the truck is inline SVG).
- Existing pages inherit the new header and card shell. Their content/layout stays intact; violet/pink
  accents are replaced with the navy/yellow palette where they are part of the shared visual system.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Separate `driver_profiles`, `shipper_profiles`, `admin_profiles` tables | Cleaner normalization long-term, but adds three tables/joins and a larger migration for a v2 form redesign. The brief explicitly asks to update `User`; profile tables can be a future refactor if these fields grow. |
| One `full_name` column plus the existing `name` | Redundant data and a second source of truth. The form alias is enough. |
| Require a phone for admins | The requested admin fields are `username`, `password`, `admin_code`; forcing a phone adds a field the design does not have. |
| Store a per-user `admin_code_hash` | Onboarding/rotation becomes a data migration, and the code is a deployment secret rather than user data. A single `ADMIN_CODE` env var is simpler and safer to rotate. |
| Keep one shared login with a role dropdown | The requirement is a separate admin login. A role dropdown also invites admins to authenticate through the wrong path. |
| Use a `company_id` column instead of `national_id` for shippers | The brief allows either. `national_id` covers individuals and is consistent with drivers; legal-entity IDs are a separate feature. |
| Backfill `username` for existing admins in the migration | The migration cannot know the desired username, and generating one would lock admins out until they discover it. The phone fallback is reversible and non-destructive. |
| Registration success rendered directly from the POST response | A refresh would re-submit the form. POST → 303 → GET is the standard safe pattern and matches ADR 004. |
| Client-side validation only | Bypassable and inconsistent with server-side rules. Server validation is authoritative; browser hints are supplementary. |
| Keep carrier registration in the landing page | The requested landing page has exactly three choices. Carrier accounts remain supported but are provisioned separately. |

## Consequences

- `users` gains six nullable columns and `phone` becomes nullable. Existing rows are untouched; old
  drivers/shippers can still log in because their phone remains present.
- New required registration fields are **not** retroactively required for existing accounts. A future
  profile-completion flow may fill them.
- Admin accounts created in v2 have `phone = NULL`; the old phone-based login cannot authenticate them.
  They must use `/auth/admin/login`.
- Downgrading the migration sets `phone` back to `NOT NULL`; it fails if any v2 admin with a null phone
  exists. Downgrade is for scratch/empty databases or after deleting/updating those admins.
- The admin code is a single shared secret. It must be long, random, stored only in the environment, and
  rotated if leaked. There is no per-admin code or audit trail in v2.
- Existing HTML form consumers of `POST /auth/register` break. This is intentional and covered by the
  new spec/tests; there are no JSON API consumers of that path.
- CSRF tokens, rate limiting, and per-admin audit logging remain out of scope; see the SPEC follow-ups.
- The shared header/brand change touches every page that extends `base.html`, so the regression suite
  must cover dashboard, cargo, document, and 403 pages, not just auth pages.

## Migration notes

One new revision after `cc9ac3ac14f8_phase_1_core_flow.py`:

1. Add nullable columns: `username`, `national_id`, `license_number`, `truck_type`, `plate_number`,
   `cargo_type_preference`.
2. `with op.batch_alter_table("users") as batch: batch.alter_column("phone", existing_type=sa.String(20), nullable=True)`
   so the revision works on SQLite as well as PostgreSQL.
3. Create unique indexes `ix_users_username`, `ix_users_national_id`, `ix_users_license_number` and a
   non-unique index `ix_users_plate_number`.
4. Do not backfill usernames; legacy admins use the phone fallback.
5. Before creating the unique indexes, check for duplicates in the target database. The new columns are
   all `NULL` at that point, so only the existing phone uniqueness matters.
6. Downgrade drops the indexes and columns and restores `phone NOT NULL`. Use `batch_alter_table` for
   SQLite. Document the null-phone caveat.

The SQLAlchemy model must declare the same indexes in `User.__table_args__` so `create_all` and Alembic
agree. Use `Mapped[str]` with `nullable=True` (not `Optional[...]`) because the repository's SQLAlchemy
2.0.35 / Python 3.14 combination cannot parse optional mapped annotations (see `Booking.time_slot_id`).

## References

- `docs/SPEC-registration-v2.md` — authoritative requirements and acceptance criteria.
- `docs/PLAN-registration-v2.md` — TDD and test-migration plan.
- `docs/adr/003-auth-jwt-cookie.md` — JWT cookie.
- `docs/adr/004-login-redirect-303.md` — 303 after login.
- `docs/SPEC-auth.md` — current auth behavior (registration routes superseded by this ADR).
- `docs/SPEC-ui.md` — current auth UI (superseded for auth pages by the registration-v2 spec).
- `AGENTS.md` — spec/plan/TDD/ADR rules.
