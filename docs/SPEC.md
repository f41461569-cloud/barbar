# SPEC: Booking Feature (Smart Freight)

## Status
Approved

## Context
Drivers reserve loading time slots at warehouses. A slot has a `capacity` and must never be
over-booked, including when two requests arrive at the same instant. The current data model
(ADR 001) defines `TimeSlot`, `Booking`, and the `uq_slot_driver` constraint, but no public
booking API exists yet.

## Scope
- Public endpoint: `POST /api/bookings` accepting `{time_slot_id, driver_id, cargo_id?}`.
- Service-level reservation using `SELECT ... FOR UPDATE` on the target `TimeSlot` row.
- Capacity check over bookings with `status == "confirmed"`.
- Deterministic error mapping to HTTP status codes.
- PostgreSQL-backed concurrency verification.

## Acceptance Criteria
1. Two concurrent requests for the same `time_slot_id`: exactly one returns **200**, the other returns **409**.
2. A request for a nonexistent `time_slot_id` returns **404 or 409 (not 200)**.
3. The test must run against **PostgreSQL** (`DATABASE_URL` set to a postgres URL), not SQLite, to validate row locking.
4. A booking response contains `id`, `time_slot_id`, `driver_id`, `status`, and `created_at`.
5. Capacity is never exceeded: the number of `confirmed` bookings for a slot never exceeds `TimeSlot.capacity`.
6. Cancelled/non-confirmed bookings do not consume capacity.
7. Invalid payloads (missing `time_slot_id` or `driver_id`) return 422 via Pydantic validation.

## Edge Cases
- `capacity == 0`: every reservation attempt returns 409.
- Same driver booking the same slot twice: 409 (enforced by `uq_slot_driver` and the service check).
- Slot exists but belongs to a different warehouse/tenant context: still governed by capacity only for v1.
- Concurrent requests where the loser arrives after the winner commits: loser must observe the committed count and return 409 (the row lock serializes this).
- Unique-constraint violation raised at insert time (race under a different isolation level): must be translated to 409 rather than 500.
- Database configured with SQLite: concurrency test is skipped, never treated as proof of correctness.

## Out of Scope
- Authentication/authorization and role enforcement.
- Payment, cargo assignment workflows, cancellation endpoint.
- Timezone conversion of slot times.

## Non-Functional
- Use SQLAlchemy 2.0 typed models and `select(...).with_for_update()`.
- All new public API surface requires a new ADR before implementation (per AGENTS.md).
