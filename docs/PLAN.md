# PLAN: Implement Booking Feature

## Dependencies
- `docs/SPEC.md` (approved) and this plan — required before coding per AGENTS.md.
- ADR 001 (Initial Data Model) — already accepted.
- **ADR 002 (new)** — required before adding the public API endpoint `POST /api/bookings`, because a public API change needs an ADR.
- A reachable PostgreSQL instance and `DATABASE_URL=postgresql+psycopg2://...` for the concurrency test.

## Steps
1. [x] Write and approve `docs/SPEC.md`.
2. [x] Write and approve `docs/PLAN.md`.
3. [x] Add the **failing** test `tests/test_booking_concurrency.py` (RED). Do not touch `app/services/booking_service.py` yet.
4. [x] Create `docs/adr/002-booking-endpoint.md` describing `POST /api/bookings` and its error contract.
5. [ ] Implement `app/main.py` with `POST /api/bookings`, wired to `BookingService.create_booking` and `get_db`.
6. [ ] Map failure modes in the API layer:
   - missing slot -> 404 (or 409)
   - slot full / duplicate driver / `IntegrityError` -> 409
   - validation errors -> 422 (Pydantic default)
7. [ ] Harden `app/services/booking_service.py` only if the RED -> GREEN cycle requires it
   (keep `SELECT ... FOR UPDATE`, verify the count is read after the lock is acquired).
8. [ ] Generate and apply the Alembic migration for the initial schema.
9. [ ] Run the full suite against PostgreSQL and confirm GREEN.

## Test Strategy
- **RED (current state):** `pytest tests/test_booking_concurrency.py -v` with a PostgreSQL
  `DATABASE_URL` fails because `app.main` / `POST /api/bookings` does not exist yet.
- **Guard:** the test module is skipped unless `DATABASE_URL` points at PostgreSQL, so SQLite
  can never be mistaken for a valid row-locking verification.
- **Concurrency mechanics:** two threads, released by a `threading.Barrier`, each use their own
  `TestClient` and therefore their own DB session; the row lock must serialize them.
- **Assertions:** sorted status codes equal `[200, 409]`; nonexistent slot is in `(404, 409)` and
  never 200.
- **Isolation:** fixtures use UUID-suffixed phone/name values and are deleted in `finally` blocks.
- **GREEN:** after implementation, the same command passes unchanged.

## Commands
```powershell
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
pytest tests/test_booking_concurrency.py -v
pytest
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```
