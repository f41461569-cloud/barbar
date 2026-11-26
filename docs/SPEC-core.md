# SPEC: Phase 1 — Core Flow

## Status
Approved — 2026-11-26. Implementation follows `docs/PLAN-core.md` under AGENTS.md (spec/plan gate +
ADR for data-model/public-API changes).

## 1. Context

The platform already has registration/login (ADR 003), a role-aware dashboard, and a slot-based
booking API (ADR 002). Phase 1 connects those pieces into the first end-to-end logistics flow:

1. A **driver** uploads a license and a national ID; an **admin** verifies them.
2. A **shipper** publishes a cargo.
3. A **driver** finds available cargos and books one.
4. The cargo can never be booked twice, including under simultaneous requests.

Current gaps in the repository:

- `Cargo` exists in the model but has no create/list endpoint or page.
- `Booking.time_slot_id` is `NOT NULL`, so a cargo booking cannot exist without a time slot.
- There is no driver-document model, storage, or verification state.
- `POST /api/bookings` is slot-oriented and unauthenticated; it is **not** modified by this phase.

## 2. Goals

| ID | Goal |
|---|---|
| G1 | Drivers upload exactly one active license and one active national ID; admins review them. |
| G2 | A driver is `verified` only when both document types are approved. |
| G3 | Shippers create cargos with title, origin, destination, weight and price. |
| G4 | Drivers list available cargos with basic filters and book one. |
| G5 | A cargo gets at most one confirmed booking, enforced by the database and verified on PostgreSQL under concurrency. |

## 3. Non-goals

- Slot booking changes, slot creation, BoL, trip tracking, carrier fleet, admin user management.
- Cargo cancellation, booking cancellation, driver un-booking, re-booking after cancellation.
- Assignment of a cargo to a specific vehicle, carrier fleet driver, or time slot.
- Payments, invoices, SMS/email notifications, maps, GPS.
- Virus scanning, image resizing, OCR, object storage (S3), CDN.
- CSRF tokens (the session cookie is `SameSite=Lax`; see §17).
- Adding authentication to the legacy `POST /api/bookings` endpoint (follow-up).

## 4. Roles and permissions

| Capability | Anonymous | Driver | Shipper | Carrier | Admin |
|---|---|---|---|---|---|
| Open `/cargos` and list available cargos | redirect to login | ✓ | ✓ (read) | ✓ (read) | ✓ (read; may list all statuses) |
| Create a cargo | ✗ | ✗ | ✓ | ✗ | ✗ |
| Book a cargo | ✗ | ✓ only if `verified` | ✗ | ✗ | ✗ |
| Upload own driver documents | ✗ | ✓ | ✗ | ✗ | ✗ |
| View own document status | ✗ | ✓ | ✗ | ✗ | ✓ (all) |
| Download a document file | ✗ | own only | ✗ | ✗ | ✓ |
| List/review documents | ✗ | ✗ | ✗ | ✗ | ✓ |
| `/dashboard` | ✓ | ✓ | ✓ | ✓ | ✓ |

Role checks are server-side on every route; hiding a button is never sufficient. Carrier fleet is
unchanged and remains a future card.

## 5. Domain rules

### 5.1 Driver verification

- Document types: `license` (گواهینامه) and `national_id` (کارت ملی).
- A driver has at most **one active row per type** (`UNIQUE(driver_id, doc_type)`).
- A re-upload replaces the active row in place, increments `version`, resets `status` to
  `pending`, and clears `reviewed_at`, `reviewed_by_id`, `rejection_reason`.
- Verification state is **derived**, never stored as a flag on `User`:
  - both types present and `approved` → `verified`
  - otherwise, any type `rejected` → `rejected`
  - otherwise, any type present and `pending` → `pending`
  - otherwise → `unverified`
- Only `verified` drivers may book a cargo.
- Admins may approve or reject at any time. Rejection requires a reason (3–500 chars after trim).
- Review is optimistic: the client sends the `version` it saw; a mismatch returns **409**
  (`document_version_conflict`), so an admin cannot approve a file that was replaced meanwhile.

### 5.2 Cargo lifecycle

- `status` is server-controlled: `available` → `booked`. There is no other transition in Phase 1.
- `shipper_id` always comes from the session, never from the request body.
- A booked cargo disappears from the default driver listing but remains readable by id.
- Cargos are not deleted in Phase 1.

### 5.3 Booking lifecycle

- A booking is `confirmed` on creation; there is no cancellation in Phase 1.
- A cargo booking has `time_slot_id = NULL` and a non-null `cargo_id`.
- Exactly one `confirmed` booking may exist per cargo.
- Repeating the request (same or different driver) returns **409**; the endpoint is not idempotent
  in Phase 1.
- On success the cargo becomes `booked` in the same transaction as the booking insert.
- The driver is taken from the session; a `driver_id` in the body is ignored/rejected.

## 6. Data model changes

### 6.1 New table `driver_documents`

| Column | Type | Rules |
|---|---|---|
| `id` | int PK | |
| `driver_id` | FK `users.id`, indexed | must reference a `driver` user |
| `doc_type` | varchar(20) | `license` \| `national_id`; `CHECK` constraint |
| `stored_path` | varchar(500) | relative POSIX path under `UPLOAD_DIR`; never returned by the API |
| `original_filename` | varchar(255) | sanitized client name, display only |
| `content_type` | varchar(100) | normalized `application/pdf` \| `image/jpeg` \| `image/png` |
| `size_bytes` | int | `> 0`, `<= 5 MiB` |
| `status` | varchar(20), indexed | `pending` \| `approved` \| `rejected`; `CHECK` constraint |
| `rejection_reason` | varchar(500), nullable | required iff `status = rejected` (service rule) |
| `version` | int, default 1 | incremented on every upload |
| `uploaded_at` | datetime | UTC, default now |
| `reviewed_at` | datetime, nullable | set on approve/reject |
| `reviewed_by_id` | FK `users.id`, nullable | admin who reviewed |

Constraints: `UNIQUE(driver_id, doc_type)` named `uq_driver_document_type`; index on
`(status, uploaded_at)` for the admin queue.

### 6.2 `bookings` changes

- `time_slot_id` becomes **nullable** (cargo bookings set it to `NULL`).
- New **partial unique index** `uq_bookings_cargo_confirmed` on `cargo_id` where
  `status = 'confirmed'` (both `postgresql_where` and `sqlite_where`).
- `uq_slot_driver` is unchanged.
- `cargo_id` remains nullable so legacy slot bookings keep working.

### 6.3 `cargos`

No column changes. `status` already defaults to `available`. Validation limits are enforced in the
schema/service (§9).

## 7. API contract

### 7.1 Conventions

- All routes in §7.2 require a valid `access_token` cookie or `Authorization: Bearer` token
  (ADR 003). Missing/invalid → **401**. The legacy slot endpoint is the only exception.
- Errors from new routes use `{"detail": {"code": "<snake_case>", "message": "<Persian>"}}`.
  Pydantic validation errors keep FastAPI's default `{"detail": [...]}` shape.
- JSON responses and FastAPI's `{"detail": …}` error shape; the only non-JSON route is the
  document file download, which returns the stored PDF/JPEG/PNG.
- Dates are ISO-8601 UTC.
- The legacy `POST /api/bookings` keeps its current contract (ADR 002) and is untouched.

### 7.2 Endpoints

| Method | Path | Role | Request | Success | Notes |
|---|---|---|---|---|---|
| POST | `/api/drivers/me/documents` | driver | multipart: `doc_type`, `file` | **201** new / **200** replaced, document DTO | 403 non-driver; 413/415 file errors |
| GET | `/api/drivers/me/documents` | driver | — | **200** `{verification_status, documents[]}` | own docs only |
| GET | `/api/documents/{id}/file` | owner or admin | — | **200** file attachment | also used by HTML links |
| GET | `/api/admin/documents` | admin | `status` (default `pending`; `pending\|approved\|rejected\|all`), `driver_id?`, `limit`, `offset` | **200** `{items[], total, limit, offset}` | includes `driver_name`, never phone |
| POST | `/api/admin/documents/{id}/review` | admin | `{decision, reason?, version?}` | **200** document DTO | 409 on version mismatch |
| POST | `/api/cargos` | shipper | cargo payload | **201** cargo DTO + `Location` | `shipper_id` from session |
| GET | `/api/cargos` | any authenticated | `origin?`, `destination?`, `min_weight?`, `max_weight?`, `min_price?`, `max_price?`, `status?`, `limit?`, `offset?` | **200** `{items[], total, limit, offset}` | default `status=available` |
| GET | `/api/cargos/{id}` | any authenticated | — | **200** cargo DTO | 404 if missing |
| POST | `/api/cargos/{id}/book` | verified driver | empty body | **201** booking DTO | 403 unverified; 404; 409 already booked |

### 7.3 DTOs

```json
Cargo:      { "id", "shipper_id", "title", "origin", "destination",
              "weight_kg", "price", "status" }

Document:   { "id", "driver_id", "doc_type", "original_filename", "content_type",
              "size_bytes", "status", "rejection_reason", "version",
              "uploaded_at", "reviewed_at" }

Booking:    { "id", "cargo_id", "driver_id", "time_slot_id": null,
              "status": "confirmed", "created_at" }

List:       { "items": [...], "total": <int>, "limit": <int>, "offset": <int> }
```

`stored_path` is **never** serialized. `driver_name` appears only in the admin document list.

### 7.4 Query rules

- `GET /api/cargos` is readable by all authenticated roles; only drivers see a booking action in
  the UI.
- `status` accepts `available` (default), `booked`, `all`. `booked` and `all` are admin-only;
  another role receives **403**.
- Filters are case-insensitive substring matches for `origin`/`destination` (trimmed, min 1 char
  when present).
- `min_*` / `max_*` are inclusive; `min > max` returns **422**.
- `limit` default 20, `1..100`; `offset >= 0`; violation → **422**.
- Sort is newest first (`id DESC`).

## 8. HTML pages (Persian, RTL, existing light theme)

Reuse `templates/base.html`; all pages are `max-w-6xl` white-card layouts, 320–1440 px, no new
frontend dependency.

| Method | Path | Role | Behaviour |
|---|---|---|---|
| GET | `/cargos` | authenticated | filter form + available cargo cards; verified drivers see «رزرو», unverified drivers see a notice + link to documents |
| POST | `/cargos/{id}/book` | verified driver | success → **303** `/cargos?ok=booked`; conflict → **409** re-render with alert; unverified → **403** re-render |
| GET | `/shipper/cargos` | shipper | own cargos with status |
| GET | `/shipper/cargos/new` | shipper | create form |
| POST | `/shipper/cargos/new` | shipper | success → **303** `/shipper/cargos?ok=created`; invalid → **422** re-render with values |
| GET | `/driver/documents` | driver | verification summary + both document statuses + upload form |
| POST | `/driver/documents` | driver | multipart upload; success → **303** `/driver/documents?ok=uploaded`; errors re-render 4xx with alert |
| GET | `/admin/documents` | admin | review queue with status filter, file link, approve/reject forms |
| POST | `/admin/documents/{id}/review` | admin | success → **303** `/admin/documents?ok=reviewed`; invalid reason → **422**; version conflict → **409** |

Rules:

- Anonymous page request → **303** to `/auth/login` (no `next` support in Phase 1).
- Wrong role → **403** rendered with `templates/errors/403.html` (Persian message, link to
  dashboard). API requests under `/api/**` still get JSON 403.
- Flash feedback uses fixed query tokens mapped to server-side strings; query values are never
  echoed raw.
- Upload form: `enctype="multipart/form-data"`, fields named `doc_type` and `file`,
  `accept=".pdf,.jpg,.jpeg,.png"`.
- Cargo form field names are part of the contract: `title`, `origin`, `destination`,
  `weight_kg`, `price`.
- Error containers keep `role="alert"` + `aria-live="assertive"`; invalid inputs get
  `aria-invalid="true"`.
- Dashboard: the «لیست بارهای موجود» card links to the real `/cargos`; `/time-slots` and `/bol`
  stay `data-future-route`. A role-gated quick-link row is added (driver → documents, shipper →
  my cargos/new cargo, admin → document review). Card count and Fleet rules are unchanged.

## 9. Validation

| Field | Rule | Failure |
|---|---|---|
| `title` | trim; 3–200 chars | 422 |
| `origin`, `destination` | trim; 2–200 chars | 422 |
| `weight_kg` | finite number; `1 <= w <= 40_000` | 422 |
| `price` | finite number; `1 <= p <= 1_000_000_000_000` | 422 |
| `status` (create) | ignored if sent; always `available` | — |
| `doc_type` | `license` \| `national_id` | 422 |
| `file` | required, non-empty | 422 |
| file size | `<= 5 MiB` | 413 |
| file type | declared and sniffed type match `pdf`/`jpeg`/`png` | 415 |
| `decision` | `approved` \| `rejected` | 422 |
| `reason` | required for `rejected`; trim; 3–500 chars | 422 |
| `version` (review) | optional int; must equal current | 409 |

Magic-byte sniffing (no new dependency): `%PDF-` → pdf, `FF D8 FF` → jpeg,
`89 50 4E 47 0D 0A 1A 0A` → png. A declared type that disagrees with the bytes is rejected.
`image/jpg` is normalized to `image/jpeg`. The stored filename is a UUID plus an extension derived
from the sniffed type; the client filename is never used as a path.

## 10. File storage and access

- `UPLOAD_DIR` setting, default `./uploads`; files under `{UPLOAD_DIR}/documents/{driver_id}/{uuid}.{ext}`.
- `stored_path` is relative and resolved against `UPLOAD_DIR`; no path traversal.
- The directory is **not** mounted statically. Files are served only by
  `GET /api/documents/{id}/file` with an authorization check.
- Download response: `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`,
  `Cache-Control: private, no-store`. Missing file on disk → **404** `document_file_missing`.
- Replacing a document writes the new file first, commits the DB row, then deletes the old file
  best-effort. A failed commit deletes the new file.
- `uploads/` is added to `.gitignore`.

## 11. Concurrency design (summary)

Full decision in `docs/adr/005-cargo-booking-concurrency.md`. Three independent layers:

1. **Row lock:** `SELECT ... FOR UPDATE` on the cargo row (PostgreSQL serializes contenders).
2. **Guarded transition:** `UPDATE cargos SET status='booked' WHERE id=:id AND status='available'`;
   `rowcount != 1` → 409. This also protects single-process SQLite development.
3. **Database backstop:** partial unique index `uq_bookings_cargo_confirmed`; an `IntegrityError`
   on commit is rolled back and mapped to 409.

All three run in one transaction; the cargo update and booking insert commit together or not at
all. The concurrency test runs only against PostgreSQL and is skipped on SQLite, matching
`tests/test_booking_concurrency.py`.

## 12. Error contract

| Status | `code` | When |
|---|---|---|
| 401 | `unauthorized` | missing/invalid session |
| 403 | `forbidden` | wrong role or non-admin listing `booked/all` |
| 403 | `driver_not_verified` | booking with unverified/missing documents |
| 404 | `cargo_not_found` | book/detail for a missing cargo |
| 404 | `document_not_found` | review/download for a missing document |
| 404 | `document_file_missing` | DB row exists, file removed from disk |
| 409 | `cargo_unavailable` | cargo already booked (including the losing concurrent request) |
| 409 | `document_version_conflict` | review sent for an older document version |
| 409 | `document_upload_conflict` | simultaneous replacement upload for the same driver/type |
| 413 | `file_too_large` | upload over 5 MiB |
| 415 | `unsupported_file_type` | declared type or magic bytes not PDF/JPEG/PNG |
| 422 | Pydantic default shape | malformed/missing fields, bad limits, `min > max` |
| 422 | `invalid_rejection_reason` | rejection without a valid reason |
| 422 | `invalid_doc_type` | upload with an unknown document type |
| 201 | — | cargo created, booking created, new document uploaded |
| 200 | — | list/detail/review, document replaced |

User-facing messages (also used as the API `message`):

| Key | Persian |
|---|---|
| `cargo_booked` | بار با موفقیت رزرو شد. |
| `cargo_unavailable` | این بار در همین لحظه توسط راننده دیگری رزرو شد. |
| `driver_not_verified` | برای رزرو بار، ابتدا مدارک شما باید تأیید شود. |
| `cargo_created` | بار جدید ثبت شد. |
| `doc_uploaded` | مدرک بارگذاری شد و در انتظار بررسی است. |
| `doc_reviewed` | وضعیت مدرک به‌روزرسانی شد. |
| `file_too_large` | حجم فایل نباید بیشتر از ۵ مگابایت باشد. |
| `unsupported_file_type` | فقط PDF، JPG و PNG مجاز است. |
| `rejection_reason_required` | برای رد مدرک، دلیل را وارد کنید. |
| `forbidden` | شما به این بخش دسترسی ندارید. |

## 13. Acceptance criteria

| ID | Criterion |
|---|---|
| AC-1 | A driver uploads a PDF license → 201, row `pending`, file stored under `UPLOAD_DIR` with a UUID name; the original filename is preserved for display. |
| AC-2 | Upload rejects >5 MiB (413), unsupported declared type (415), magic-byte mismatch (415), empty file (422), non-driver (403), anonymous (401). |
| AC-3 | A second upload of the same type replaces the row, increments `version`, resets to `pending`, clears review fields, and removes the previous file. |
| AC-4 | An admin lists pending documents; a non-admin gets 403; the list includes driver name and never the phone. |
| AC-5 | Approving both types makes the driver `verified`; rejecting one makes `rejected`; a missing type keeps `unverified`. |
| AC-6 | Rejection without a reason is rejected; approve/reject set `reviewed_at` and `reviewed_by_id`. |
| AC-7 | Reviewing an old `version` returns 409 and leaves the document unchanged. |
| AC-8 | A shipper creates a cargo → 201/redirect, `shipper_id` from session, `status=available`; invalid payloads return 422. |
| AC-9 | A non-shipper creating a cargo → 403; anonymous → 401/redirect. |
| AC-10 | Driver listing returns only `available` cargos by default and supports origin/destination/weight/price filters, pagination, and newest-first order. |
| AC-11 | A verified driver books an available cargo → 201, booking `confirmed`, cargo `booked`, `time_slot_id` null. |
| AC-12 | Two concurrent bookings for one cargo on PostgreSQL: exactly one 201 and one 409; exactly one confirmed booking row; cargo `booked`. |
| AC-13 | Booking a missing cargo → 404; an already booked cargo → 409; an unverified driver → 403 and the cargo stays `available`; a shipper booking → 403. |
| AC-14 | Inserting a second `confirmed` booking for the same cargo directly is rejected by `uq_bookings_cargo_confirmed`. |
| AC-15 | `/cargos`, `/shipper/cargos`, `/shipper/cargos/new`, `/driver/documents`, `/admin/documents` render RTL Persian pages, enforce roles, and show accessible alerts; the dashboard `/cargos` link is live. |
| AC-16 | A document file is downloadable only by its owner or an admin; others get 403; the response is an attachment with `nosniff`. |
| AC-17 | The full suite is green on PostgreSQL (existing 45 tests + new tests), with the SQLite run skipping the PostgreSQL-only tests. |
| AC-18 | `alembic upgrade head` applies the new table/index/nullable change; `alembic downgrade -1` restores the previous schema on a scratch database. |
| AC-19 | No plaintext password, `stored_path`, or user phone is exposed in any new response or page. |

## 14. ADR gate

| ADR | Covers | Status required before code |
|---|---|---|
| `005-cargo-booking-concurrency.md` | Cargo booking strategy, nullable `time_slot_id`, partial unique index, 404/403/409 mapping | Proposed in this change |
| `006-driver-documents-and-cargo-api.md` | `driver_documents` schema, file storage/access, verification rule, cargo API surface, error contract | Proposed in this change |

No new **auth** ADR: Phase 1 reuses ADR 003 (JWT HttpOnly cookie) and adds only role dependencies.
The legacy slot-booking endpoint keeps ADR 002 and is not re-authenticated in this phase; hardening
it is a follow-up requiring its own ADR/test update.

## 15. Testing strategy

| File | Scope | PostgreSQL required |
|---|---|---|
| `tests/test_documents.py` | upload/replace/validation, verification state, admin list/review, version conflict, download auth | yes |
| `tests/test_cargos.py` | create + validation, role/anonymous gates, list filters/pagination, detail, status visibility | yes |
| `tests/test_cargo_booking.py` | booking success, 404/409/403 paths, cargo status transition, response DTO | yes |
| `tests/test_cargo_concurrency.py` | two-thread race, DB backstop, no partial state | yes (module-gated, like the slot test) |
| `tests/test_core_ui.py` | page rendering, forms/field names, role gates, flash alerts, dashboard link | yes for data-backed cases |
| `tests/test_ui_templates.py` | update dashboard `/cargos` assertion; keep theme contract | existing |

Harness change: `tests/conftest.py` adds a session-scoped schema reset (`drop_all` + `create_all`)
**only** for a PostgreSQL database whose name ends with `_test`. A PostgreSQL URL without that
suffix raises (safety guard against wiping a real database). SQLite skips the reset and relies on
`create_all` + `alembic upgrade head` for local development. This makes model changes visible
without manually migrating the test DB and cannot wipe a non-test database.

## 16. Edge cases

- Cargo booked between listing and clicking → 409, page re-renders with the Persian conflict alert.
- Same driver double-clicks book → one 201 and one 409; no duplicate rows.
- Driver uploads a `.pdf` that is actually a PNG → 415.
- Zero-byte file → 422; 5 MiB + 1 byte → 413; exactly 5 MiB → accepted.
- Uppercase `FILE.PDF` → extension derived from sniffed bytes, accepted.
- Client filename containing `..\` or control characters → sanitized, never used in the path.
- Re-upload while an admin reviews → admin's stale `version` gets 409; the driver's upload wins.
- Booking with `driver_id` in the body → the body is ignored; the session identity is used.
- Cargo with `weight_kg = 0` or negative price → 422.
- `limit=0`, `limit=101`, `offset=-1`, `min_price > max_price` → 422.
- Unverified driver opens `/cargos` → page renders with a notice; the server still rejects a
  direct POST with 403.
- Admin downloads a document whose file was deleted → 404 `document_file_missing` (row is kept).
- SQLite dev DB not migrated → cargo booking fails at the NOT NULL constraint; documented fix is
  `alembic upgrade head`.

## 17. Non-functional

- **Security:** role checks on every route; session-derived ownership; no PII in list payloads;
  files served only through an authorized endpoint; `nosniff`; `SameSite=Lax` cookie (ADR 003)
  mitigates cross-site form POSTs; CSRF tokens are out of scope for Phase 1.
- **Privacy:** document files and statuses are visible to the owner and admins only; the admin
  queue shows name + document type, not phone.
- **Performance:** list endpoints paginate (max 100); admin queue is indexed by status; document
  reads stream from disk; no N+1 for the admin list (single join).
- **Accessibility:** labelled inputs, visible focus, `role="alert"`, `aria-invalid`, Persian RTL,
  320–1440 px, no horizontal scroll.
- **Portability:** PostgreSQL is authoritative for concurrency; SQLite remains dev-only.
- **Operability:** `UPLOAD_DIR` is configurable; the directory must be backed up together with the
  database; the app must be able to create it at startup or on first upload.
- **Maintainability:** SQLAlchemy 2.0 typed models; one Alembic revision; services own
  transactions; routes map domain errors to HTTP.

## 18. Assumptions / defaults to confirm at approval

| ID | Default chosen in this draft |
|---|---|
| D1 | Reuse `bookings` with a nullable `time_slot_id` instead of a separate `cargo_bookings` table. |
| D2 | New endpoint `POST /api/cargos/{id}/book`; the legacy slot endpoint is untouched. |
| D3 | "Verified" means both license and national ID approved; booking is gated on it. |
| D4 | One active row per document type, replaced in place with a `version` for optimistic review. |
| D5 | Local disk storage under `UPLOAD_DIR`; no S3/static mount in Phase 1. |
| D6 | New API errors use `{"detail": {code, message}}`; Pydantic keeps its default shape. |
| D7 | `/api/cargos` is readable by every authenticated role; booking is driver-only. |
| D8 | Cargo price is a positive number in the UI's تومان unit; no currency column in Phase 1. |

Approval of this SPEC confirms D1–D8. Any change after approval requires a SPEC update and, where
§6 or §7 changes, an ADR amendment or a new ADR.

## 19. Traceability to `docs/SRS.md`

| SRS requirement | Phase 1 coverage | Remaining work |
|---|---|---|
| FR-3 (drivers view available cargos) | AC-10, AC-15 | — |
| FR-4 (shippers create cargos) | AC-8, AC-9, AC-15 | — |
| FR-6 (no double booking) | AC-11–AC-14; cargo claim on PostgreSQL | Legacy slot endpoint unchanged; cancellation not included |
| FR-9 (admins oversee) | AC-4–AC-7 (document review) | Full user/cargo/booking admin views remain future |
| NFR-2 (PostgreSQL concurrency proof) | AC-12, AC-14 | — |
| NFR-5 (accessible errors) | AC-15, §8 | — |

The SRS status column is updated after implementation; Phase 1 does not rewrite the SRS baseline.
