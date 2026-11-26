# ADR 005: Cargo Booking Concurrency Strategy

## Status
Accepted — 2026-11-26.

## Date
2026-11-26

## Context

Phase 1 lets a driver book a **cargo**, not a warehouse time slot. The existing strategy
(ADR 002) locks a `TimeSlot` row and compares the number of confirmed bookings with
`TimeSlot.capacity`. That does not apply here:

- A cargo has no capacity; the rule is exactly **one** confirmed booking per cargo.
- `Booking.time_slot_id` is currently `NOT NULL`, so a cargo booking cannot be inserted.
- `uq_slot_driver` does not prevent two drivers from booking the same cargo.
- Two requests can read `Cargo.status == "available"` at the same time and both try to insert.

We need a guarantee that survives multiple Uvicorn workers/processes and database restarts, and
that can be proven on PostgreSQL.

## Decision

### 1. Data model

- Make `bookings.time_slot_id` **nullable** so a cargo booking can store `NULL`.
- Keep `bookings.cargo_id` and `bookings.status`.
- Add a **partial unique index**:

  ```sql
  CREATE UNIQUE INDEX uq_bookings_cargo_confirmed
      ON bookings (cargo_id)
      WHERE status = 'confirmed';
  ```

  SQLAlchemy declares it with both `postgresql_where=text("status = 'confirmed'")` and
  `sqlite_where=text("status = 'confirmed'")` so `create_all` behaves the same in tests.
- `uq_slot_driver` (ADR 001) is unchanged. Legacy slot bookings keep `cargo_id = NULL`; standard
  unique-index NULL semantics allow many such rows, so the new index does not affect them.

### 2. Endpoint

- `POST /api/cargos/{cargo_id}/book`, no body.
- The driver identity comes from the session (`access_token` cookie / Bearer token), never from the
  request body.
- Success **201** with the booking DTO; missing cargo **404**; unverified driver **403**;
  already booked **409**.
- The legacy `POST /api/bookings` slot endpoint and its behavior are untouched.

### 3. Transaction (three layers)

```
BEGIN
  SELECT * FROM cargos WHERE id = :id FOR UPDATE;        -- 1. serialize (PostgreSQL)
  if not found                      -> 404, ROLLBACK
  if driver not verified            -> 403, ROLLBACK
  UPDATE cargos SET status='booked'
    WHERE id = :id AND status='available';               -- 2. atomic transition
  if rowcount != 1                  -> 409, ROLLBACK
  INSERT INTO bookings (cargo_id, driver_id, time_slot_id, status)
    VALUES (:id, :driver, NULL, 'confirmed');            -- 3. backstop index
  COMMIT
```

- **Layer 1** is the primary serializer on PostgreSQL. `FOR UPDATE` blocks the second contender
  until the first commits, so it re-reads `status='booked'`.
- **Layer 2** makes the state transition itself atomic. It also protects single-process SQLite
  development, where `FOR UPDATE` is ignored.
- **Layer 3** is a database invariant independent of application code. Any `IntegrityError` on
  commit is rolled back and translated to **409** (`cargo_unavailable`), never a 500.
- The cargo update and the booking insert commit together; a failure leaves the cargo
  `available` and creates no booking.

### 4. Verification

`tests/test_cargo_concurrency.py` is PostgreSQL-gated (same `DATABASE_URL` guard as
`tests/test_booking_concurrency.py`):

- two threads, barrier-released, each with its own `TestClient` and driver cookie;
- assert sorted statuses `[201, 409]`;
- assert exactly one `confirmed` booking for the cargo and `Cargo.status == "booked"`;
- a separate test inserts a second confirmed booking directly and expects the unique index to
  reject it.

SQLite is never accepted as proof of row locking.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Check `status` without a lock | Classic TOCTOU; two requests both see `available`. |
| Unique index only | Correct invariant, but every race becomes an `IntegrityError` and the cargo status transition is not atomic with the insert; poorer 404/403 semantics and error messages. |
| PostgreSQL advisory lock | Works, but adds a lock namespace/lifecycle and is PostgreSQL-only for no extra benefit over a row lock. |
| Serializable isolation + retry loop | Correct but higher complexity, more aborted transactions, and retry/backoff logic for little gain on one row. |
| Application-level `threading.Lock` | Fails across multiple workers/processes and after restart. |
| Separate `cargo_bookings` table | Duplicates booking lifecycle/BoL relations that ADR 001 and future phases rely on. |
| Conditional `UPDATE` only | Atomic per statement, but on PostgreSQL the explicit row lock gives a clear, testable serialization point and keeps the verification check inside the same transaction. |

## Consequences

- PostgreSQL remains mandatory for production and for concurrency verification; SQLite is
  development-only.
- A future cancellation flow must set `Booking.status != 'confirmed'`; the partial index then
  allows a new confirmed booking for the same cargo without a schema change.
- A future "multiple drivers per cargo" or capacity feature requires dropping/replacing
  `uq_bookings_cargo_confirmed` and a new ADR.
- Migration downgrade must set `time_slot_id` back to `NOT NULL`; it will fail if cargo bookings
  exist, so downgrade is only for empty/scratch databases.
- The service rolls back explicitly on every domain error to release the row lock promptly.

## References

- `docs/adr/001-data-model.md` — base tables and `uq_slot_driver`.
- `docs/adr/002-booking-endpoint.md` — slot booking and `SELECT … FOR UPDATE`.
- `docs/SPEC-core.md` §5.3, §11, §13 (AC-11–AC-14).
