# ADR 002: Booking Endpoint and Concurrency Strategy

## Status
Accepted

## Context
We need a POST /api/bookings endpoint that prevents double booking of loading time slots under concurrent requests.

## Decision
- Use SELECT ... FOR UPDATE on the TimeSlot row inside a transaction.
- After locking, re-check the number of confirmed bookings against slot.capacity.
- Commit only after both the lock and the capacity check pass.
- Run concurrency tests only against PostgreSQL, since SQLite ignores FOR UPDATE.

## Consequences
- The service is not concurrency-safe on SQLite; SQLite is for local development only.
- Production must run on PostgreSQL.
- Any change to this locking strategy requires a new ADR.
