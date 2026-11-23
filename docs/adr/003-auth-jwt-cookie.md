# ADR 003: JWT in HttpOnly Cookie for Authentication

## Status
Accepted

## Context
The login flow needs a way to keep a user authenticated across requests from a browser. The token
must be sent automatically with each request, must not be readable by client-side JavaScript
(reducing XSS token theft), and must work with server-rendered Jinja2 pages served by FastAPI.
We also need to add a `password_hash` column to the `users` table, so an ADR is required before
that data-model change.

## Decision
- Store the JWT in a cookie with `HttpOnly=True` (and `SameSite=Lax`; `Secure` in production)
  rather than returning it in a JSON body or storing it in `localStorage`.
- The browser sends the cookie automatically on subsequent requests; the server validates the JWT
  signature and expiry before trusting the identity.
- The cookie is cleared on `POST /auth/logout`.
- Passwords are hashed with bcrypt and stored in a new `users.password_hash` column; the plaintext
  password is never persisted.
- Depends on `passlib[bcrypt]` for hashing and `python-jose[cryptography]` for JWT signing/verification.

## Consequences
- JavaScript cannot read the token, which mitigates XSS-based token exfiltration.
- Cookie-based auth is vulnerable to CSRF; `SameSite=Lax` reduces but does not eliminate this, so
  state-changing endpoints should add CSRF protection in a future ADR if needed.
- Logout is a cookie-clear operation; the JWT remains valid until expiry if copied elsewhere, so
  token lifetime should be short.
- Requires a secret key in configuration; rotating it invalidates all outstanding sessions.
- Adding `password_hash` to `users` requires a new Alembic migration; any further change to this
  scheme requires a new ADR.
