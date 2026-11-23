# AGENTS.md — Smart Freight (Barbar Houshmand)

## Absolute Rules
- Never start coding without an approved SPEC.md and PLAN.md.
- Never write production code without writing tests first (TDD).
- Double booking of loading time slots is forbidden. Every implementation must be verified with a concurrency test on PostgreSQL.
- Any change to the data model or public API requires a new ADR.

## Tech Stack
- Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic
- Development: SQLite / Production and concurrency tests: PostgreSQL

## Roles
1. Driver
2. Shipper / Warehouse Owner
3. Carrier Company
4. Admin

## Commands
- Install: pip install -r requirements.txt
- Run: uvicorn app.main:app --reload
- Test: pytest
- Migration: alembic revision --autogenerate -m "msg" then alembic upgrade head
