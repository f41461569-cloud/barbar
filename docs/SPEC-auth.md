# SPEC: Authentication (Login and Registration)

## Status
Approved

## Context
The platform currently has a `users` table with `phone`, `name`, `role`, and `created_at`, but no way to
authenticate. We need HTML forms served by FastAPI/Jinja2 for registration and login, with a JWT
returned in an HttpOnly cookie so the browser sends it automatically without exposing it to JS.

## Scope
- Registration and login for three self-service roles: **driver**, **shipper**, **carrier**.
  The **admin** role is created manually (out of band) and is not selectable in the registration form.
- Server-rendered Jinja2 templates for the forms.
- Password hashing with bcrypt; no plaintext passwords anywhere.
- JWT session token stored in an **HttpOnly** cookie.
- Logout clears the cookie.

## Pages and Endpoints
- `GET /auth/register` — registration form
- `GET /auth/login` — login form
- `POST /auth/register` — create a user, then redirect to `/auth/login`
- `POST /auth/login` — verify credentials, set JWT cookie, redirect to `/dashboard`
- `POST /auth/logout` — clear the JWT cookie, redirect to `/auth/login`

## Registration Requirements
- Fields: `phone` (unique), `name`, `password`, `role`.
- `role` must be one of `driver`, `shipper`, `carrier`; admin cannot be selected.
- Password must be hashed with bcrypt before persistence.
- Duplicate `phone` returns **409**.

## Login Requirements
- Fields: `phone`, `password`.
- Verify submitted password against the stored bcrypt hash.
- Wrong password (or unknown phone) returns **401**.
- On success, create a JWT and set it in an **HttpOnly** cookie, then **redirect to `/dashboard`**.

## Acceptance Criteria
1. Duplicate phone on register returns 409.
2. Wrong password on login returns 401.
3. Successful login sets an HttpOnly cookie and redirects to `/dashboard`.
4. Password is never stored in plain text (verify hash in DB).

## Edge Cases
- Empty/missing form fields return a form error (422 or re-rendered form with error message).
- Invalid `role` value is rejected (422).
- Unknown phone on login returns 401 (same as wrong password, to avoid user enumeration).
- Expired or tampered JWT is treated as unauthenticated.
- Logout clears the cookie even if no valid token is present.
- Very long passwords are handled by bcrypt's 72-byte limit (reject or truncate consistently).

## Out of Scope
- Password reset / email verification.
- OAuth / social login.
- Role-based authorization rules for `/dashboard` and booking endpoints.
- Refresh tokens.

## Non-Functional
- JWT signed with a server-side secret from configuration; never hard-coded.
- Cookie flags: `HttpOnly=True`, `SameSite=Lax`; `Secure` enabled in production.
- Any change to the `users` table requires an ADR (see ADR 003).
