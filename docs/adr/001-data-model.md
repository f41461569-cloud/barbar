# ADR 001: Initial Data Model

## Status
Accepted

## Context
The platform needs to model users (driver, shipper, carrier, admin), warehouses, loading time slots, cargos, and bookings. Double booking must be prevented.

## Decision
- Use SQLAlchemy 2.0 declarative models with typed mapped_column.
- TimeSlot has a UniqueConstraint on (warehouse_id, start_time).
- Booking has a UniqueConstraint on (time_slot_id, driver_id).
- TimeSlot.capacity limits how many bookings a slot can accept.

## Consequences
- Concurrency correctness must be verified on PostgreSQL with SELECT ... FOR UPDATE.
- Any future change to these constraints requires a new ADR.
