# ADR 006: Driver Documents and Phase 1 Cargo API

## Status
Accepted — 2026-11-26.

## Date
2026-11-26

## Context

Phase 1 adds two things that AGENTS.md classifies as data-model/public-API changes:

1. **Driver verification** — drivers must upload a license and a national ID, and an admin must
   review them. There is no document table, no storage policy, and no verification state.
2. **Cargo endpoints** — shippers create cargos and drivers list them. The `Cargo` table exists
   (ADR 001) but no endpoint or authorization exists.

ADR 005 covers the booking transaction and the `bookings` change. This ADR records the companion
schema, storage, authorization, and API-surface decisions.

## Decision

### 1. `driver_documents` table

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `driver_id` | FK `users.id`, indexed | must be a `driver` |
| `doc_type` | varchar(20) | `license` / `national_id`, `CHECK` |
| `stored_path` | varchar(500) | relative path under `UPLOAD_DIR`; never serialized |
| `original_filename` | varchar(255) | sanitized for display only |
| `content_type` | varchar(100) | normalized PDF/JPEG/PNG |
| `size_bytes` | int | `1 .. 5 MiB` |
| `status` | varchar(20), indexed | `pending` / `approved` / `rejected`, `CHECK` |
| `rejection_reason` | varchar(500), nullable | required when rejected |
| `version` | int, default 1 | optimistic review token |
| `uploaded_at` | datetime | UTC |
| `reviewed_at` | datetime, nullable | |
| `reviewed_by_id` | FK `users.id`, nullable | admin reviewer |

- `UNIQUE(driver_id, doc_type)` — one active row per type; re-upload updates it in place and
  increments `version`.
- Index `(status, uploaded_at)` for the admin queue.
- Verification is **derived** from the two rows; no `users.is_verified` flag, so the state cannot
  drift.

### 2. File storage

- `UPLOAD_DIR` setting (default `./uploads`); actual path
  `UPLOAD_DIR/documents/{driver_id}/{uuid4}.{ext}`.
- The extension comes from magic-byte sniffing, never from the client filename.
- Accepted: `%PDF-`, `FF D8 FF` (JPEG), `89 50 4E 47 0D 0A 1A 0A` (PNG). Declared content type
  must match; max 5 MiB; empty rejected.
- The directory is **not** mounted as static files. The only read path is
  `GET /api/documents/{id}/file`, which checks owner-or-admin, returns an attachment with
  `X-Content-Type-Options: nosniff` and `Cache-Control: private, no-store`.
- Replacement writes the new file, commits, then best-effort deletes the old one. A DB failure
  deletes the new file.
- `uploads/` is git-ignored and must be included in backups.

### 3. Verification rule

- `verified` = license **and** national ID both `approved`.
- otherwise any `rejected` → `rejected`; otherwise any `pending` → `pending`; otherwise
  `unverified`.
- Only `verified` drivers may book (enforced by the route dependency and again in the booking
  service).

### 4. Public API surface

| Method | Path | Role |
|---|---|---|
| POST | `/api/drivers/me/documents` | driver (multipart `doc_type`, `file`) |
| GET | `/api/drivers/me/documents` | driver |
| GET | `/api/documents/{id}/file` | owner or admin |
| GET | `/api/admin/documents` | admin (`status`, `driver_id`, `limit`, `offset`) |
| POST | `/api/admin/documents/{id}/review` | admin (`decision`, `reason?`, `version?`) |
| POST | `/api/cargos` | shipper |
| GET | `/api/cargos` | any authenticated role (filters/pagination) |
| GET | `/api/cargos/{id}` | any authenticated role |

Server-rendered pages reuse the same services: `/driver/documents`, `/admin/documents`,
`/shipper/cargos`, `/shipper/cargos/new`, `/cargos`.

### 5. Authorization and errors

- Reuse ADR 003 (HttpOnly JWT cookie). New dependencies: `get_current_user` (401 JSON),
  `require_roles(...)` (403 JSON), `require_verified_driver` (403 `driver_not_verified`).
- Page routes redirect anonymous users to `/auth/login` and render a 403 page for wrong roles.
- New API errors: `{"detail": {"code", "message"}}` with codes `unauthorized`, `forbidden`,
  `driver_not_verified`, `cargo_not_found`, `cargo_unavailable`, `document_not_found`,
  `document_file_missing`, `document_version_conflict`, `document_upload_conflict`,
  `file_too_large`, `unsupported_file_type`, `invalid_rejection_reason`, `invalid_doc_type`.
  Pydantic validation keeps FastAPI's default shape.
- `shipper_id` and `driver_id` are always taken from the session.
- The admin document list joins `users` for `driver_name`; the phone number is never returned.

### 6. Cargo API validation

- `title` 3–200, `origin`/`destination` 2–200 after trim.
- `weight_kg` finite, `1..40_000`; `price` finite, `1..1_000_000_000_000`.
- `status` is server-controlled (`available` on create).
- Filters: case-insensitive origin/destination, inclusive min/max weight/price,
  `status` default `available` (`booked`/`all` admin-only), `limit` 1–100 (default 20),
  `offset >= 0`, newest first.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Store uploads as DB BLOBs | Bloats backups/rows, no streaming, harder to serve. |
| Static `/uploads` mount | Exposes identity documents to anyone with a URL. |
| Base64 JSON upload | ~33% overhead and unbounded memory for multi-MB files. |
| S3/object storage | No object-storage infrastructure in the baseline; local disk is sufficient for one instance. |
| `users.is_verified` flag | Denormalized; can disagree with the documents. Derived state is the single source of truth. |
| Append-only document history | Better audit, but Phase 1 only needs the active document; `version` already guards stale reviews. A history table can be added later. |
| One table per document type | Duplicated schema/endpoints; a `doc_type` discriminator is simpler. |

## Consequences

- The deployment must persist and back up `UPLOAD_DIR` alongside PostgreSQL; losing it makes
  approved documents undownloadable (rows remain, downloads return 404).
- Local disk ties the app to a single instance; horizontal scaling requires shared storage
  (future ADR).
- No virus scanning/OCR in Phase 1; file type is validated by magic bytes only.
- Re-upload is in-place, so the audit trail is limited to `version`, `uploaded_at`,
  `reviewed_at`, `reviewed_by_id`. An append-only history is a follow-up.
- Cargo/bookings remain owned by ADR 001/005; this ADR does not change their lifecycle.

## References

- `docs/adr/001-data-model.md` — base tables.
- `docs/adr/003-auth-jwt-cookie.md` — session mechanism reused here.
- `docs/adr/005-cargo-booking-concurrency.md` — booking transaction and index.
- `docs/SPEC-core.md` §4–§10, §13–§14.
