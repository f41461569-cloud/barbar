# ADR 004: 303 See Other for the Post-Login Redirect

## Status
Accepted — 2026-11-23

## Context
`POST /auth/login` authenticates the user and returns a redirect to `/dashboard`. The endpoint
previously returned **302 Found**. Both 302 and 303 cause browsers to re-issue the request as a GET
in practice, but 302 leaves the method ambiguous ("may change to GET"), while 303 unambiguously
requires the client to follow with a GET (RFC 9110 §15.4.4).

The login response also sets the session cookie. The cookie must be attached to the same
`RedirectResponse` instance that is returned, under the same `HTTPException`-free code path, and must
carry `HttpOnly` and `SameSite=Lax` so it is sent on the subsequent top-level navigation.

`docs/SPEC-ui.md` §13 states that a status-code change to the form endpoints needs an ADR first;
this record satisfies that rule.

## Decision
1. `POST /auth/login` returns **303 See Other** with `Location: /dashboard`.
2. The `access_token` cookie is set on that same `RedirectResponse` object
   (`redirect_response.set_cookie(...)`), never on a separate response object.
3. Cookie attributes remain `HttpOnly`, `SameSite=Lax`, `Path=/`, `max_age=3600`; `Secure` in
   production.
4. Registration (`302` → `/auth/login`) and logout (`302` → `/auth/login`) are unchanged.

## Consequences
- Browsers deterministically follow the login redirect with a GET, so refreshing `/dashboard` cannot
  re-submit credentials.
- Clients that hard-coded 302 must accept 303; `tests/test_auth.py` accepts 302, 303 and 307.
- Endpoints, form field names, cookie name/flags, error statuses (401/409/422) and redirect targets
  are otherwise unchanged.
- No data-model, migration or dependency change.

## Alternatives considered
- **Keep 302** — works in browsers but leaves POST-to-GET conversion implicit; rejected for clarity.
- **307 Temporary Redirect** — preserves the method, which would re-POST to `/dashboard` (or fail);
  wrong semantics for a post-login navigation.
- **Return 200 and navigate client-side** — requires JavaScript and breaks the no-JS path.
