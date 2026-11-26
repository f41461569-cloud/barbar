# PLAN: Phase 1 — Core Flow

## Status
Approved — 2026-11-26 (SPEC-core approved; ADR 005 and ADR 006 accepted; defaults D1–D8 confirmed).
Implementation in progress under AGENTS.md.

## Dependencies

- `docs/SPEC-core.md` — approved spec.
- `docs/adr/005-cargo-booking-concurrency.md` — accepted (booking transaction, nullable
  `time_slot_id`, partial unique index).
- `docs/adr/006-driver-documents-and-cargo-api.md` — accepted (document table/storage, cargo API).
- ADR 001 (data model), ADR 002 (slot booking), ADR 003 (JWT cookie), ADR 004 (login 303) remain
  in force. **No new auth ADR** is needed; Phase 1 only adds role dependencies.
- PostgreSQL for the full suite and all concurrency tests:
  `postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test`.
- Python deps already present: `python-multipart` (uploads), `passlib`, `python-jose`, `jinja2`.
  No new dependency is planned.
- Dev server: `venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000`.

## Files

### New

| File | Purpose |
|---|---|
| `app/auth/guards.py` | `get_current_user`, `require_roles`, `require_verified_driver`, page guards |
| `app/services/errors.py` | Domain exceptions (`CargoNotFound`, `CargoUnavailable`, `DriverNotVerified`, `DocumentNotFound`, `DocumentVersionConflict`, `FileTooLarge`, `UnsupportedFileType`) |
| `app/services/document_storage.py` | magic-byte sniff, size/type validation, UUID paths, save/delete |
| `app/services/document_service.py` | upload/replace, verification state, admin list, review, download lookup |
| `app/services/cargo_service.py` | create/list/detail with validation and filters |
| `app/services/cargo_booking_service.py` | locked cargo claim + booking insert (ADR 005) |
| `app/api/cargos.py` | cargo JSON endpoints |
| `app/api/documents.py` | driver/admin document JSON endpoints + file download |
| `app/pages/cargos.py` | `/cargos`, book action |
| `app/pages/shipper.py` | `/shipper/cargos`, `/shipper/cargos/new` |
| `app/pages/documents.py` | `/driver/documents` |
| `app/pages/admin.py` | `/admin/documents`, review action |
| `templates/cargos/list.html` | filter form + cargo cards |
| `templates/shipper/cargos.html` | shipper's own cargos |
| `templates/shipper/cargo_new.html` | create form |
| `templates/driver/documents.html` | verification summary + upload form |
| `templates/admin/documents.html` | review queue |
| `templates/errors/403.html` | role-denied page |
| `templates/partials/quick_links.html` | role-gated dashboard shortcuts |
| `app/pages/__init__.py` | page router package |
| `tests/conftest.py` | guarded schema reset + shared helpers |
| `tests/test_documents.py` | document upload/verification/review/download |
| `tests/test_cargos.py` | cargo create/list/permissions |
| `tests/test_cargo_booking.py` | booking success and error paths |
| `tests/test_cargo_concurrency.py` | PostgreSQL two-thread race + DB backstop |
| `tests/test_core_ui.py` | Phase 1 pages and forms |
| `alembic/versions/<rev>_phase1_core.py` | one revision for all schema changes |

### Modified

| File | Change |
|---|---|
| `app/models.py` | add `DriverDocument`; make `Booking.time_slot_id` nullable; add partial unique index |
| `app/schemas.py` | cargo/document/review/list DTOs; keep `BookingResponse` untouched |
| `app/config.py` | add `UPLOAD_DIR` (default `./uploads`) |
| `app/main.py` | include the two API routers and four page routers; ensure upload dir exists |
| `templates/dashboard.html` | `/cargos` becomes a real link; add quick-link row; keep cards/Fleet |
| `tests/test_ui_templates.py` | update the dashboard `/cargos` linkage assertion only |
| `.gitignore` | add `uploads/` |

Not changed: `app/api/bookings.py`, `app/services/booking_service.py`,
`tests/test_booking_concurrency.py`, `tests/test_auth.py`, ADR 001–004, auth templates.

## Test harness change

`tests/conftest.py`:

- Session-scoped autouse fixture that runs `Base.metadata.drop_all()` + `create_all()` **only** for
  a PostgreSQL database whose name ends with `_test`. A PostgreSQL URL without that suffix raises a
  clear safety error; SQLite skips the reset (local dev relies on `alembic upgrade head`).
  This is required because `create_all()` cannot alter an existing `bookings.time_slot_id` or add
  a new index to an existing table.
- Shared helpers: `make_user(role)`, `auth_cookie(user)`, `make_verified_driver()`,
  `make_cargo()`, `seed_document()`. Helpers use UUID-suffixed phones/names and per-test cleanup,
  matching `tests/test_auth.py` and `tests/test_booking_concurrency.py`.
- Verify the reset against a database that already has the old schema: `drop_all/create_all` must
  also recreate the PostgreSQL `userrole` enum type. If the type survives, drop it explicitly in
  the fixture before `create_all`.
- `UPLOAD_DIR` is repointed to `tmp_path` per test via `monkeypatch.setattr(settings, "UPLOAD_DIR", ...)`;
  storage must read `settings.UPLOAD_DIR` at call time (not at import). The temp directory is
  removed automatically.

Existing tests keep their own `create_all()` calls; they become no-ops after the reset. No existing
assertion is weakened.

## TDD cycles

Each cycle writes its tests first and confirms RED for the right reason before any production code
in that area.

### Phase 0 — Governance
1. [x] Approve `docs/SPEC-core.md` (including defaults D1–D8).
2. [x] Accept ADR 005 and ADR 006.
3. [x] Record the approvals at the top of this plan.

### Phase 1 — Documents (RED → GREEN)
4. [ ] Write `tests/conftest.py` and `tests/test_documents.py`:
   - upload new PDF → 201, `pending`, UUID path, original filename preserved;
   - replace → 200, `version+1`, `pending`, old file deleted;
   - 413 oversized, 415 wrong type/magic mismatch, 422 empty, 403 non-driver, 401 anonymous;
   - verification derived: `unverified` / `pending` / `verified` / `rejected`;
   - admin list (name, no phone), non-admin 403;
   - approve/reject, reason required, reviewer fields, stale `version` → 409;
   - download owner/admin 200, other driver 403, missing file 404, `nosniff` header;
   - page cases in `tests/test_core_ui.py`: `/driver/documents` and `/admin/documents` render,
     field names, role gates, status badges, accessible alerts.
5. [ ] Run `pytest tests/test_documents.py -v` → RED (import/route failures). Record the output.
6. [ ] Add `DriverDocument` to `app/models.py` (the single migration is generated in Phase 5, after
   all model changes; tests use `create_all`).
7. [ ] Implement `app/services/document_storage.py` + `document_service.py` + `errors.py`.
8. [ ] Implement `app/auth/guards.py` and the `/api/drivers`, `/api/admin/documents`,
   `/api/documents/{id}/file` routes.
9. [ ] Implement `/driver/documents` and `/admin/documents` pages + templates.
10. [ ] `pytest tests/test_documents.py -v` → GREEN.

### Phase 2 — Cargo create/list (RED → GREEN)
11. [ ] Write `tests/test_cargos.py`: create 201, session-derived `shipper_id`, `status=available`,
    validation 422 (title/origin/destination/weight/price), role 403, anonymous 401;
    list defaults to `available`, filters (origin/destination/min-max weight/price), pagination,
    invalid limits, `booked`/`all` admin-only, detail 404, booked cargo hidden.
12. [ ] Run `pytest tests/test_cargos.py -v` → RED. Record.
13. [ ] Add `app/schemas.py` DTOs + `cargo_service.py` + `app/api/cargos.py`.
14. [ ] `pytest tests/test_cargos.py -v` → GREEN.

### Phase 3 — Cargo UI (shipper + driver list)
15. [ ] Write the cargo-page cases in `tests/test_core_ui.py` (rendering, field names, filters,
    role gates, dashboard quick links, 403 page, 320-px markup contract).
16. [ ] Implement `/shipper/cargos`, `/shipper/cargos/new`, `/cargos` routes/templates and the
    dashboard quick links; update `tests/test_ui_templates.py` for the now-live `/cargos` link.
17. [ ] `pytest tests/test_core_ui.py tests/test_ui_templates.py -v` → GREEN.

### Phase 4 — Booking (RED → GREEN, including concurrency)
18. [ ] Write `tests/test_cargo_booking.py`:
    - verified driver books available cargo → 201, `confirmed`, cargo `booked`, `time_slot_id` null;
    - missing cargo 404; already booked 409; unverified 403 (cargo stays available); shipper 403;
    - body `driver_id` ignored; duplicate request 409;
    - page cases in `tests/test_core_ui.py`: success flash, conflict alert, unverified notice.
19. [ ] Write `tests/test_cargo_concurrency.py` (PostgreSQL-gated):
    - two barrier-released threads with separate `TestClient`s and driver cookies → `[201, 409]`;
    - exactly one confirmed booking row; cargo `booked`;
    - direct second confirmed insert → `IntegrityError` (partial index proof);
    - two unverified drivers race → both 403 and the cargo stays `available`.
20. [ ] Run both files → RED. Record.
21. [ ] Make `Booking.time_slot_id` nullable and add `uq_bookings_cargo_confirmed` to the model
    (migration is generated once in Phase 5; hand-check the partial index because autogenerate may
    omit the `WHERE` clause).
22. [ ] Implement `app/services/cargo_booking_service.py` (lock → verify → guarded update →
    insert → commit; rollback on domain errors; `IntegrityError` → 409) and
    `POST /api/cargos/{id}/book`.
23. [ ] Implement the booking action on `/cargos` + flash/alert rendering.
24. [ ] `pytest tests/test_cargo_booking.py tests/test_cargo_concurrency.py -v` with PostgreSQL →
    GREEN.

### Phase 5 — Polish and regression
25. [ ] Coverage check: every Phase 1 page/action has a test written **before** its template/route
    (documents in Phase 1, cargo pages in Phase 3, booking/flash/403/quick links in Phase 4).
    No new behavior without a test.
26. [ ] Run `pytest tests/ -v` with PostgreSQL → **all collected tests pass**, including the
    original 45. Record the new count.
27. [ ] Run `pytest tests/ -q` without PostgreSQL → PostgreSQL-only modules skip, no failures.
28. [ ] `alembic upgrade head` on a scratch PostgreSQL DB; run `alembic check` (no pending
    changes); `alembic downgrade -1`; re-upgrade.
29. [ ] Pre-migration data check **on the target DB**:
    `SELECT cargo_id, count(*) FROM bookings WHERE status='confirmed' AND cargo_id IS NOT NULL GROUP BY cargo_id HAVING count(*) > 1;`
    must return zero rows before the unique index is created.
30. [ ] Grep for forbidden leaks: `stored_path` in templates/JSON, phone numbers in admin list,
    raw query echoing, `|safe` on user input.

### Phase 6 — Manual QA (Chrome)
31. [ ] Run the dev server against the migrated SQLite DB.
32. [ ] Execute the matrix below; record date/browser/results here.
33. [ ] Clean up QA users, cargo, bookings, documents, uploaded files, screenshots; close tabs.

## Migration notes

One revision, in this order:

1. `op.create_table("driver_documents", ...)` with `CHECK` constraints, unique
   `uq_driver_document_type`, indexes on `driver_id` and `(status, uploaded_at)`.
2. `op.alter_column("bookings", "time_slot_id", nullable=True)` — but express it as
   `with op.batch_alter_table("bookings") as batch: batch.alter_column("time_slot_id", nullable=True)`
   so the same revision works on SQLite (ALTER COLUMN is not supported there) and PostgreSQL.
3. `op.create_index("uq_bookings_cargo_confirmed", "bookings", ["cargo_id"], unique=True,
   postgresql_where=sa.text("status = 'confirmed'"),
   sqlite_where=sa.text("status = 'confirmed'"))`.

- Autogenerate first, then hand-edit: Alembic often drops dialect-specific `where` clauses.
- `SQLAlchemy` metadata must declare the same index in `Booking.__table_args__` so `create_all`
  and Alembic agree.
- Downgrade drops the index/table and restores `NOT NULL`; it fails if cargo bookings exist, which
  is expected on a scratch DB only.
- Deploy order: migration first (additive), then app. Old code ignores the new table/index.

## Commands

```powershell
# --- Tests: dedicated PostgreSQL test DB (schema reset by tests/conftest.py) ---
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"

# RED → GREEN per cycle
venv\Scripts\python.exe -m pytest tests/test_documents.py -v
venv\Scripts\python.exe -m pytest tests/test_cargos.py -v
venv\Scripts\python.exe -m pytest tests/test_cargo_booking.py -v
venv\Scripts\python.exe -m pytest tests/test_cargo_concurrency.py -v

# Full suite
venv\Scripts\python.exe -m pytest tests/ -v

# --- Migration: scratch DB, brought to the previous head first ---
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_migration_test"
venv\Scripts\python.exe -m alembic upgrade head                 # existing revisions only
# ... apply model changes ...
venv\Scripts\python.exe -m alembic revision --autogenerate -m "phase 1 core flow"
venv\Scripts\python.exe -m alembic upgrade head                 # new revision
venv\Scripts\python.exe -m alembic check                        # no pending diff
venv\Scripts\python.exe -m alembic downgrade -1
venv\Scripts\python.exe -m alembic upgrade head

# --- Dev SQLite: apply the new revision before running the app ---
$env:DATABASE_URL = "sqlite:///./barbar_smart.db"
venv\Scripts\python.exe -m alembic upgrade head

# Dev server
venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

## Manual QA matrix

| Area | Check | Expected |
|---|---|---|
| Driver docs | Upload PDF license | 303, badge «در انتظار بررسی», file stored with UUID name |
| Driver docs | Upload JPG national ID | same; summary shows one pending per type |
| Driver docs | Upload `.exe` / 6 MiB file / empty file | alert, 415 / 413 / 422, no row created |
| Driver docs | Re-upload license | version increases, status resets to pending, old file gone |
| Admin | `/admin/documents` as admin | pending queue, driver name, document type, file link |
| Admin | Approve both | driver becomes verified; driver page shows «تأیید شده» |
| Admin | Reject without reason | 422 alert «برای رد مدرک، دلیل را وارد کنید.» |
| Admin | Two tabs, stale version | second review → 409, no overwrite |
| Access | `/admin/documents` as driver/shipper | 403 page |
| Access | `/driver/documents` as shipper | 403 page |
| Access | anonymous `/cargos` | 303 to `/auth/login` |
| Shipper | Create cargo | 303, appears in `/shipper/cargos`, status available |
| Shipper | Invalid weight/price | 422, values preserved, `aria-invalid` |
| Driver | `/cargos` filters | origin/destination/weight/price narrow the list |
| Driver | Book cargo | 303, «بار با موفقیت رزرو شد.», card disappears |
| Driver | Second driver books same cargo | 409 alert «این بار در همین لحظه …» |
| Driver | Unverified driver books | 403 notice, cargo still available |
| Download | Owner vs other driver vs admin | 200 vs 403 vs 200; attachment + `nosniff` |
| Dashboard | `/cargos` card | real link; `/time-slots` and `/bol` still future |
| Dashboard | Quick links | driver: docs; shipper: cargos/new; admin: review; carrier: none |
| Responsive | 320 / 390 / 768 / 1024 / 1440 px | no horizontal scroll; cards stack; forms usable |
| Keyboard | Tab through forms | visible focus; alerts readable |
| Console | All pages | no JS errors |

## Rollback

- Revert the app commit; run `alembic downgrade -1` on a scratch DB (delete cargo bookings first).
- Delete `uploads/documents/**` created during QA; keep production uploads only if restoring an
  older app version (the old code ignores them).
- Restore the dashboard assertion in `tests/test_ui_templates.py` if the UI change is reverted.
- No existing endpoint or table is removed, so a rollback does not break auth, the dashboard, or
  the legacy slot booking.

## Definition of done

- [ ] SPEC-core approved; ADR 005 and ADR 006 accepted; no open questions.
- [ ] Every new production module had a failing test before it was written (RED recorded per cycle).
- [ ] `tests/test_documents.py`, `test_cargos.py`, `test_cargo_booking.py`,
      `test_cargo_concurrency.py`, `test_core_ui.py` pass on PostgreSQL.
- [ ] Original 45 tests still pass; only the dashboard `/cargos` linkage assertion was updated
      (documented, not weakened).
- [ ] `tests/test_booking_concurrency.py`, `tests/test_auth.py`, and the legacy booking service are
      untouched.
- [ ] `alembic upgrade head`, `alembic check`, and `alembic downgrade -1` verified on a scratch DB.
- [ ] Concurrency proof: exactly one 201 + one 409, one booking row, cargo `booked`.
- [ ] Manual QA matrix passed; no horizontal scroll at 320–1440 px; alerts accessible.
- [ ] No `stored_path`, phone number, or plaintext password in any new response/page.
- [ ] `uploads/` ignored; `UPLOAD_DIR` documented; backup note added.
- [ ] This plan marked Implemented with recorded RED/GREEN counts and QA results.

## Follow-ups (not in this plan)

- Authenticate and session-derive the legacy `POST /api/bookings` (requires ADR 002 update and a
  test rewrite).
- Booking/cargo cancellation and re-booking (partial index already supports it).
- Append-only document history + audit log; virus scanning; object storage for multi-instance.
- Carrier fleet and cargo assignment; BoL; time slots; admin user management; Jalali dates.
- CSRF tokens if the cookie policy changes from `SameSite=Lax`.
- Update `docs/SRS.md` FR-3/FR-4/FR-9 statuses and the interface/acceptance counts after Phase 1
  ships (the SRS is the baseline, not part of this plan).
