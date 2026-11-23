# Software Requirements Specification (SRS) — Smart Freight (باربر هوشمند)

| Field | Value |
|---|---|
| Document | `docs/SRS.md` |
| Version | 1.0 |
| Date | 2026-11-23 |
| Status | Draft — pending review |
| Product | Smart Freight (باربر هوشمند) |
| Standard | IEEE 830–style SRS structure |

---

## 1. Introduction

### 1.1 Purpose

Smart Freight (باربر هوشمند) is a logistics platform that connects truck **drivers**, **shippers /
warehouse owners**, **carrier companies**, and **platform admins**. It lets them manage cargo
announcements and acceptance, reserve warehouse loading time slots without double booking, exchange
a digital bill of lading, track trips, and run carrier fleet operations.

This document specifies the functional and non-functional requirements of the system. It is the
requirements baseline for design, implementation and verification, and it must be read together with
the approved specs and ADRs listed in §1.4.

### 1.2 Scope

**In scope**

- Self-service registration and login for three public roles (driver, shipper, carrier); admins are
  provisioned out of band.
- Cargo announcement by shippers and discovery/acceptance by drivers.
- Warehouse loading time-slot definition and reservation, with hard protection against double booking.
- A digital bill of lading (BoL) per booking, with status tracking across the trip.
- Carrier fleet management and cargo assignment to the carrier's drivers.
- Admin oversight of all users, cargos and bookings.
- Persian (RTL) server-rendered web UI and a JSON API documented with OpenAPI/Swagger.

**Out of scope for the current baseline**

- Payments, invoicing and settlement.
- Route optimisation, live GPS telemetry and map rendering.
- Native mobile applications.
- Email/SMS delivery, password reset and multi-factor authentication.
- Multi-tenancy beyond the single platform instance.
- Timezone conversion of slot times (times are stored as given).

### 1.3 Definitions and Acronyms

| Term | Meaning |
|---|---|
| **ADR** | Architecture Decision Record; required for data-model or public-API changes. |
| **API** | Application Programming Interface (here: FastAPI JSON endpoints under `/api`). |
| **bcrypt** | Adaptive password-hashing function used for credential storage. |
| **BoL** | Bill of Lading; the digital transport document created per booking. |
| **Capacity** | Maximum number of confirmed bookings a single time slot may hold. |
| **Cargo** | A shipment offered by a shipper (title, weight, origin, destination, price). |
| **Carrier** | Company that owns a fleet and employs drivers. |
| **Double booking** | Two confirmed bookings competing for the same capacity-limited slot; forbidden. |
| **Driver** | Person who transports cargo and reserves loading slots. |
| **FR / NFR** | Functional Requirement / Non-Functional Requirement. |
| **HttpOnly** | Cookie attribute that hides the cookie from page JavaScript. |
| **JWT** | JSON Web Token; signed session credential carried in an HttpOnly cookie. |
| **Modular Monolith** | One deployable application organised into internal modules (auth, bookings, templates). |
| **ORM** | Object–Relational Mapper (SQLAlchemy 2.0). |
| **RBAC** | Role-Based Access Control. |
| **RTL** | Right-to-left text direction (Persian UI). |
| **Shipper** | Cargo owner or warehouse owner who publishes cargos and defines slots. |
| **Slot** | A loading time window belonging to a warehouse, with a capacity. |
| **Swagger / OpenAPI** | Machine-readable API description served interactively at `/docs`. |
| **TDD** | Test-Driven Development; tests are written before production code. |

### 1.4 References

| Ref | Document | Purpose |
|---|---|---|
| [R1] | `AGENTS.md` | Engineering rules: spec/plan gate, TDD, ADR requirement, PostgreSQL concurrency testing. |
| [R2] | `docs/SPEC.md` | Approved booking feature spec (capacity, `SELECT … FOR UPDATE`, 200/409 semantics). |
| [R3] | `docs/SPEC-auth.md` | Approved authentication spec (roles, status codes, JWT cookie). |
| [R4] | `docs/SPEC-ui.md` | Approved UI redesign spec (Tailwind CDN, RTL glassmorphism, error alerts). |
| [R5] | `docs/PLAN.md` | Implementation plan for the booking feature. |
| [R6] | `docs/PLAN-auth.md` | Implementation plan for authentication. |
| [R7] | `docs/PLAN-ui.md` | Implementation plan and QA record for the UI. |
| [R8] | `docs/adr/001-data-model.md` | Initial data model (`users`, `warehouses`, `time_slots`, `cargos`, `bookings`). |
| [R9] | `docs/adr/002-booking-endpoint.md` | Booking endpoint and concurrency strategy. |
| [R10] | `docs/adr/003-auth-jwt-cookie.md` | JWT-in-HttpOnly-cookie authentication decision. |

---

## 2. Overall Description

### 2.1 Product Perspective

Smart Freight is a greenfield **Modular Monolith**:

- **Runtime:** Python 3.11+, FastAPI, Uvicorn.
- **Persistence:** SQLAlchemy 2.0 typed ORM; PostgreSQL in production and for all concurrency tests;
  SQLite is tolerated only for local development and never proves locking correctness.
- **Migrations:** Alembic, one revision per schema change.
- **Delivery:** Server-rendered Jinja2 templates (Tailwind Play CDN, Vazirmatn, RTL Persian) plus a
  JSON API. No SPA framework and no frontend build step.
- **Modules:** `app/auth` (registration, login, JWT cookie), `app/api` (bookings), `app/services`
  (booking reservation logic), `templates/` (UI), `tests/` (verification).
- **External integration:** browsers only. No third-party payment, mapping or messaging provider is
  integrated in this baseline.

### 2.2 User Roles

| Role | Code | Description | Primary capabilities |
|---|---|---|---|
| Driver | `driver` | Independent or carrier-employed truck driver. | Browse available cargos, reserve loading slots, carry cargo, update trip/BoL status. |
| Shipper / Warehouse Owner | `shipper` | Owns cargo and/or warehouse space. | Publish cargos, define slots per warehouse, hand over cargo against the BoL. |
| Carrier Company | `carrier` | Company operating a fleet of drivers. | Manage fleet, assign cargos to its drivers, monitor its bookings. |
| Admin | `admin` | Platform operator. | View all users, cargos and bookings; support and oversight. Admins are not selectable at registration. |

### 2.3 Main Features

1. **Cargo announcement and acceptance** — shippers publish a cargo (title, weight, origin,
   destination, price); drivers see available cargos and accept one, creating or attaching to a booking.
2. **Loading time-slot scheduling** — shippers define slots per warehouse with start/end times and a
   capacity; drivers reserve a slot; capacity is enforced atomically.
3. **Digital bill of lading and trip tracking** — each booking yields a BoL with a lifecycle status
   (e.g. issued → loaded → in transit → delivered/cancelled) that both parties can follow.
4. **Carrier fleet management** — carriers register their vehicles/drivers and assign accepted cargos
   to specific drivers, keeping fleet utilisation visible.

### 2.4 Constraints

- **C1** — Concurrency correctness must be verified against **PostgreSQL**; SQLite results are never
  accepted as proof. The concurrency suite is skipped unless `DATABASE_URL` is a PostgreSQL URL.
- **C2** — Passwords are hashed with **bcrypt**; plaintext passwords are never stored or logged.
- **C3** — Authentication uses a **JWT in an HttpOnly, SameSite=Lax cookie**; no tokens in
  `localStorage` or URLs.
- **C4** — No double booking: confirmed bookings for a slot must never exceed its capacity, including
  under simultaneous requests.
- **C5** — Any data-model or public-API change requires a new **ADR** before implementation.
- **C6** — Tests are written before production code (**TDD**); all existing tests must stay green.
- **C7** — UI is Persian RTL; Tailwind is delivered via CDN with **no build step**, and no JS framework
  is introduced.
- **C8** — `SECRET_KEY` and `DATABASE_URL` come from configuration/environment, never hard-coded in
  production.

---

## 3. Functional Requirements

Priority: **M** = must (baseline), **S** = should (next milestone), **C** = could.
Status reflects the repository at the date of this document and does not weaken the requirement.

| ID | Requirement | Priority | Status | Verification |
|---|---|---|---|---|
| **FR-1** | Users can register with **phone, name, password, and role**. Phone is unique; role is one of `driver`, `shipper`, `carrier` (admin not selectable). Duplicate phone returns **409**; success redirects to `/auth/login`. | M | Implemented | `tests/test_auth.py::test_register_success`, `::test_register_duplicate_phone`, `tests/test_ui_templates.py::test_duplicate_phone_renders_styled_alert` |
| **FR-2** | Users can log in with **phone and password**. Successful login sets an **HttpOnly JWT cookie** and redirects to `/dashboard`; invalid credentials return **401** without revealing whether the phone exists. | M | Implemented | `test_auth.py::test_login_success_sets_cookie`, `::test_login_wrong_password`, `test_ui_templates.py::test_unknown_phone_uses_same_login_error` |
| **FR-3** | **Drivers** can view available cargos (available status, with title, weight, origin, destination, price). | M | Planned | Pending cargo-list endpoint and tests |
| **FR-4** | **Shippers** can create cargos with **origin, destination, weight, and price** (plus title), persisted with status `available`. | M | Planned (model only) | Pending cargo-create endpoint and tests |
| **FR-5** | **Shippers** can define **loading time slots per warehouse** with start time, end time and capacity. At least one confirmed booking must remain possible when `capacity ≥ 1`. | M | Planned (model only) | Pending slot-create endpoint and tests |
| **FR-6** | **Drivers** can book a time slot. The system **must prevent double booking under concurrent requests**: for capacity-limited slots exactly one of two simultaneous requests succeeds (**200**), the other fails (**409**). Nonexistent slots return 404/409, never 200. | M | Implemented | `tests/test_booking_concurrency.py` (both tests) |
| **FR-7** | A **digital bill of lading** is created for each booking, and its status can be **tracked** through the trip lifecycle. | M | Partial (booking status only; no BoL document yet) | Pending BoL endpoint/tests |
| **FR-8** | **Carriers** can manage their **fleet** and **assign cargos to drivers** in their fleet. | S | Planned | Pending fleet model, endpoints and tests |
| **FR-9** | **Admins** can view all **users, cargos, and bookings**. | M | Planned | Pending admin endpoints/RBAC and tests |

**Cross-cutting functional rules**

- Role checks (RBAC) are enforced server-side; hiding UI controls is not sufficient.
- Booking status `confirmed` counts against capacity; cancelled/non-confirmed bookings do not.
- Every FR that changes the data model or adds public API surface requires an ADR first (C5).

---

## 4. Non-Functional Requirements

| ID | Requirement | Status | Verification |
|---|---|---|---|
| **NFR-1** | Passwords are stored **only as bcrypt hashes**, never plaintext, never in logs or responses. | Implemented | `test_auth.py::test_password_not_plaintext` |
| **NFR-2** | **Booking concurrency** must be verified on **PostgreSQL** using `SELECT … FOR UPDATE` on the target `TimeSlot` row; the suite is skipped when `DATABASE_URL` is not PostgreSQL. | Implemented | `tests/test_booking_concurrency.py` with PostgreSQL `DATABASE_URL` |
| **NFR-3** | API response time under normal load is **< 2 seconds** (server-side, excluding client network); p95 target, measured on the reference deployment. | Target (not yet benchmarked) | Load/benchmark test to be added |
| **NFR-4** | All forms are **RTL Persian** and **responsive from 320 px to 1440 px**, with no horizontal scrolling. Inputs use ≥ 16 px text to avoid mobile zoom. | Implemented (verified in Chrome at 320, 360, 390, 1366 and 1440 px) | `tests/test_ui_templates.py`; browser QA at 320/360/390/1366/1440 px (PLAN-ui record; at 1440 px the card stays 448 px wide, centered, `scrollWidth == clientWidth`) |
| **NFR-5** | Error messages are **accessible**: rendered in a container with `role="alert"` (and `aria-live="assertive"`), affected fields carry `aria-invalid="true"`, and meaning is not conveyed by colour alone. | Implemented | `test_ui_templates.py::test_wrong_password_renders_styled_alert`, `::test_duplicate_phone_renders_styled_alert`, `::test_error_preserves_phone_and_never_echoes_password` |

**Additional non-functional expectations**

- **Security:** bcrypt hashing; HttpOnly + SameSite=Lax cookie (Secure in production); JWT signed with
  a configuration secret; no `|safe` rendering of user input; no user enumeration on login.
- **Maintainability:** SQLAlchemy 2.0 typed models; Alembic migrations; modular layout; ADR per
  decision; tests precede code.
- **Operability:** health endpoint `/health`; OpenAPI at `/docs`; configuration via environment.
- **Accessibility:** keyboard-operable forms with visible focus, labelled controls, AA contrast for
  body text on the gradient background.

---

## 5. Interface Requirements

### 5.1 Web UI (server-rendered, Persian RTL)

| Method | Path | Purpose | Success | Failure |
|---|---|---|---|---|
| GET | `/auth/register` | Registration form | 200 HTML | — |
| POST | `/auth/register` | Create user (`phone`, `name`, `password`, `role`) | 302 → `/auth/login` | 409 re-rendered form with accessible alert |
| GET | `/auth/login` | Login form | 200 HTML | — |
| POST | `/auth/login` | Authenticate (`phone`, `password`) | 302 → `/dashboard` + HttpOnly cookie | 401 re-rendered form with accessible alert |
| POST | `/auth/logout` | Clear session cookie | 302 → `/auth/login` | — |
| GET | `/dashboard` | Authenticated landing page | 200 HTML | — |

UI requirements: `lang="fa"`, `dir="rtl"`, Vazirmatn, Tailwind Play CDN (pinned), glass card,
gradient background, visible focus states, no JS framework (one small double-submit guard allowed).
Field names are part of the interface contract and must not change.

### 5.2 JSON API

| Method | Path | Request | Success | Errors |
|---|---|---|---|---|
| POST | `/api/bookings` | `{"time_slot_id": int, "driver_id": int, "cargo_id": int?}` | **200** booking (`id`, `time_slot_id`, `driver_id`, `status`, `created_at`) | 404/409 slot unavailable or over capacity; **422** validation |
| GET | `/health` | — | `{"status": "ok"}` | — |

The API is documented interactively at **`/docs` (Swagger UI)**; the OpenAPI schema is available at
`/openapi.json`. JSON error bodies follow FastAPI's `{"detail": …}` shape (the HTML auth forms instead
re-render with a styled alert).

### 5.3 Session / cookie interface

- Cookie name: `access_token`; flags `HttpOnly`, `SameSite=Lax`, `max_age=3600`; `Secure` in production.
- Payload claims: `sub` (user id), `phone`, `role`.
- Expired or tampered token is treated as unauthenticated.

---

## 6. Acceptance Criteria

The baseline is accepted when all of the following hold.

1. **Test suite green:** `pytest tests/` reports **37 passing tests**, 0 failures, on PostgreSQL:
   - `tests/test_auth.py` — **5** tests (registration, duplicate phone, wrong password, cookie + redirect, hash storage).
   - `tests/test_booking_concurrency.py` — **2** tests (concurrent double-booking prevention, nonexistent slot).
   - `tests/test_ui_templates.py` — **30** tests (RTL/Tailwind contract, field names, alerts, error preservation).
2. **Existing suites unmodified:** the auth and booking-concurrency tests pass without weakening or
   editing their assertions.
3. **Contract preserved:** endpoints, form field names (`phone`, `name`, `password`, `role`), status
   codes (401/409/422), redirects and cookie flags match §5.
4. **No double booking:** the concurrency test proves exactly one of two simultaneous bookings for a
   capacity-1 slot returns 200 and the other 409, on PostgreSQL.
5. **Credentials:** no plaintext password exists in the database; bcrypt verification succeeds.
6. **UI:** login/register/dashboard are RTL Persian, responsive at 320–1440 px, with visible focus,
   AA contrast, and `role="alert"` + `aria-invalid` on errors.
7. **Governance:** every data-model/public-API change has an accepted ADR; no ADR is required for the
   UI-only change (see SPEC-ui §13).
8. **Traceability:** every FR/NFR in §3–§4 maps to a test, a documented "Planned/Target" follow-up, or
   an explicit acceptance record.

**Verification command**

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
venv\Scripts\python.exe -m pytest tests/ -v
```

---

## 7. Assumptions and Dependencies

- PostgreSQL is available for tests and production; the reference environment runs PostgreSQL 17.
- Python 3.11+ and the pinned dependencies in `requirements.txt` are installed in the virtualenv.
- Browsers have access to the Tailwind CDN and Google Fonts at runtime (accepted for this baseline;
  a build pipeline is a follow-up, not a requirement).
- Admins are created manually by operators; no admin self-registration exists.
- Feature milestones FR-3, FR-4, FR-5, FR-7, FR-8 and FR-9 require their own SPEC/PLAN (and an ADR
  where the data model or public API changes) before implementation.
