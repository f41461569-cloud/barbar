# PLAN: Implement Login and Registration

## Dependencies
- `docs/SPEC-auth.md` (approved) and this plan — required before coding per AGENTS.md.
- `docs/adr/003-auth-jwt-cookie.md` (accepted) — required before changing the `users` table
  and before introducing the JWT-cookie public API.
- Existing ADR 001 (data model) and ADR 002 (booking API) remain in force.
- PostgreSQL is running at `postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test`.

## Steps
1. [x] Create and approve `docs/SPEC-auth.md`.
2. [x] Create and accept `docs/adr/003-auth-jwt-cookie.md`.
3. [x] Create and approve `docs/PLAN-auth.md`.
4. [ ] Add dependencies to `requirements.txt`: `passlib[bcrypt]`, `python-jose[cryptography]`, `jinja2`.
5. [ ] Install them into the venv: `venv\Scripts\python.exe -m pip install -r requirements.txt`.
6. [ ] Add `password_hash` (nullable initially) to the `User` model in `app/models.py`.
7. [ ] Generate and apply a new Alembic migration for the column:
   `alembic revision --autogenerate -m "add password hash to users"` then `alembic upgrade head`.
8. [ ] **TDD (RED):** write failing tests first in `tests/test_auth.py` covering all acceptance criteria.
9. [ ] Create `app/auth/` with:
   - `security.py` — bcrypt hashing/verification, JWT create/decode, cookie helpers
   - `routes.py` — the five endpoints from the SPEC
10. [ ] Create Jinja2 templates `templates/auth/login.html` and `templates/auth/register.html`.
11. [ ] Configure FastAPI `Jinja2Templates` and mount the auth router in `app/main.py`.
12. [ ] Run `pytest tests/test_auth.py -v` against PostgreSQL until GREEN.
13. [ ] Run the full suite to confirm no regression in booking tests.

## Test Strategy (TDD)
- **RED first:** create `tests/test_auth.py` before any production auth code; tests must fail.
- Duplicate phone registration -> 409.
- Wrong password login -> 401 (unknown phone also 401).
- Successful login -> 307 redirect to `/dashboard` plus `Set-Cookie` with `HttpOnly`; parse JWT and
  verify the `sub` claim.
- Query the DB directly after registration and assert `password_hash != "password"` and that bcrypt
  verifies the plaintext against the stored hash.
- Logout clears the cookie.
- Use UUID-suffixed phone numbers and clean up users in `finally` blocks.
- Run with `DATABASE_URL` pointing at the PostgreSQL container/cluster so behavior matches production.

## Commands
```powershell
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m alembic revision --autogenerate -m "add password hash to users"
venv\Scripts\python.exe -m alembic upgrade head
venv\Scripts\python.exe -m pytest tests/test_auth.py -v
venv\Scripts\python.exe -m pytest tests/ -v
```
