# PLAN: Dashboard Redesign (Role-Aware Feature Cards)

## Status
Implemented — 2026-11-24. **D1 = A**, **D2 = A**, admin sees the Fleet card (only driver and shipper
are excluded). Red → green completed; `tests/test_ui_templates.py` 38 passed, full suite 45 passed.

## Dependencies
- `docs/SPEC-dashboard.md` — approved spec (required before coding).
- `docs/SPEC-ui.md` — design system and base shell already in place.
- `docs/adr/003-auth-jwt-cookie.md` — the HttpOnly session cookie used by D1 Option A.
- `docs/SRS.md` — FR-3…FR-9 describe the features behind the cards.
- `AGENTS.md` — spec/plan gate and TDD rule.
- PostgreSQL for the identity/role tests (`DATABASE_URL`); the markup tests run on SQLite.
- Dev server: `venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000`.

## Change-control position — no ADR required
No data-model change and no API change:

- No model, column, index or Alembic revision is touched.
- No endpoint is added, removed or renamed. `GET /dashboard` keeps its path, method and 200 response;
  under D1 = A it only receives an extra `current_user` template context.
- No form field, status code, redirect target or cookie flag changes. The login/registration flow is
  untouched.
- There is no new public API surface to document in `/docs`.

Therefore **no new ADR is required** (ADR 001/003 remain in force). If implementation starts adding an
auth gate, a new endpoint, or changes any status code/field/cookie, stop and write an ADR first.

**Scope note:** the brief says "files to update: `templates/dashboard.html` only". That is not
achievable for name/role, carrier-only Fleet, and 4 desktop columns — see SPEC §1 (C1–C3). This plan
assumes the recommended **D1 = A** and **D2 = A**, which adds:
`app/auth/security.py`, `app/main.py`, one block in `templates/base.html`, plus tests.

## Files
| File | Action | Needed for |
|---|---|---|
| `templates/dashboard.html` | rewrite | always |
| `templates/base.html` | add `{% block main_class %}max-w-md{% endblock %}` (1 line + wrap) | D2 = A |
| `app/auth/security.py` | add `get_optional_current_user(request, db)` | D1 = A |
| `app/main.py` | `GET /dashboard` depends on resolver, passes `current_user` | D1 = A |
| `tests/test_ui_templates.py` | add dashboard tests (TDD) | always |

Not changed: `app/models.py`, `alembic/`, `requirements.txt`, `app/auth/routes.py`,
`templates/auth/*`, `tests/test_auth.py`, `tests/test_booking_concurrency.py`.

## Steps (TDD; check off as completed)

### Phase 1 — RED
1. [x] Record D1/D2 answers at the top of this file; confirm approval.
2. [x] **RED:** extend `tests/test_ui_templates.py` with the dashboard tests in §Test strategy. Run:
   - without `DATABASE_URL` → markup tests fail (no cards, no grid, no wide container);
   - with PostgreSQL → identity/role tests fail (no `current_user`).
   Observed: 6 failed, 32 passed.
3. [x] Confirm the existing 37-test baseline stays green before editing production files.

### Phase 2 — Shell (D2 = A)
4. [x] In `base.html`, change `<main class="relative w-full max-w-md">` to
   `<main class="relative w-full {% block main_class %}max-w-md{% endblock %}">`. No other change;
   login/register keep `max-w-md`; dashboard overrides with `max-w-6xl`.

### Phase 3 — Identity resolver (D1 = A)
5. [x] In `app/auth/security.py`, add `get_optional_current_user(request: Request, db: Session) -> User | None`:
   - read `request.cookies.get("access_token")` (cookie first; it is the browser path);
   - if absent, fall back to `Authorization: Bearer <token>` (API clients), never required;
   - `decode_access_token`, read `sub`, load the `User`; any decode/parse/missing-user case returns
     `None` instead of raising;
   - do not log the token; do not expose `phone` or the hash.
6. [x] In `app/main.py`, make `GET /dashboard` depend on the resolver and pass
   `context={"request": request, "current_user": current_user}`. Keep the route path, name and 200
   behaviour; anonymous requests still render.

### Phase 4 — Template
7. [x] Rewrite `templates/dashboard.html` per SPEC §3–§6:
   - header: «خوش آمدید» + `current_user.name` (or generic line) + role badge + logout form;
   - role label map for `driver` / `shipper` / `carrier` / `admin`;
   - grid `mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4`;
   - three base cards (cargos, slots, BoL) with icon, `h2`, description, gradient link button and
     `data-future-route`;
   - Fleet card inside `{% if current_user and current_user.role.value in ("carrier", "admin") %}`
     (not CSS-hidden);
   - keep the submit-guard out of the logout form (`data-guard` only on auth forms);
   - no new `<style>`, no new JS.
8. [x] Spot-check that the existing dashboard tests' expectations still hold (brand row, glass tokens,
   first button is logout with `bg-red-500/20`, `action="/auth/logout"`).

### Phase 5 — GREEN
9. [x] `pytest tests/test_ui_templates.py -v` → GREEN (existing + new): **38 passed**.
10. [x] `pytest tests/ -v` with PostgreSQL → GREEN; `tests/test_auth.py` and
    `tests/test_booking_concurrency.py` unmodified: **45 passed**.
11. [x] Visual QA per §Manual QA and record results in this plan.
12. [x] Confirm AC-8/AC-9: only the files in §Files changed; `git diff --stat` shows no model,
    migration, endpoint or template-auth change.

## Test strategy (TDD)

Add to `tests/test_ui_templates.py` (reuse `_client`, `_new_phone`, `_cleanup`, `_tags`). Markup tests
need no database; identity tests use the existing `requires_postgres` marker.

**Markup (no DB, anonymous visitor)**
- `test_dashboard_shows_three_cards_anonymously` — three `<article>` cards; each has an
  `svg[aria-hidden="true"]`, an `h2` with the SPEC §5.3 title, a description paragraph and an `<a>`
  with `data-future-route`; «مدیریت ناوگان» **absent** from the DOM.
- `test_dashboard_grid_and_container` — `grid-cols-1`, `sm:grid-cols-2`, `lg:grid-cols-4` present;
  dashboard has `max-w-6xl`; login/register keep `max-w-md` and have no `max-w-6xl`.
- `test_dashboard_header_single_h1_generic_greeting_and_logout` — exactly one `<h1>`, generic welcome
  text, logout form posts to `/auth/logout`, first button class contains `bg-red-500/20`, and no
  `data-role-badge` for anonymous visitors.
- `test_dashboard_ignores_invalid_cookie` — a malformed `access_token` cookie yields 200 with the
  anonymous view (no badge, no Fleet card): the resolver never raises.

**Identity / role (PostgreSQL)**
- `test_dashboard_role_identity[driver/shipper/carrier/admin]` — insert a user directly for each role
  (the register form refuses `admin`), log in (303 + cookie), `GET /dashboard`, then assert the name,
  the Persian label from SPEC §4, the role badge, that the phone number is **not** rendered, and
  Fleet visibility (present for carrier/admin, absent for driver/shipper).

Actual totals: 30 → **38** UI tests; suite 37 → **45**.

## Manual QA
Run against the dev server (`--reload`), in Chrome, as a **carrier** and as a **driver**:

| Check | Expected |
|---|---|
| 320 / 360 / 390 px | 1 column, stacked header, full-width logout, no horizontal scroll |
| 768 px | 2 columns, header in one row |
| 1024 / 1440 px | 4 columns, content capped at `max-w-6xl`, centered |
| Carrier | 4 cards; name + «شرکت حمل و نقل» badge |
| Driver | 3 cards; no Fleet in DOM; name + «راننده» |
| Anonymous | 200, generic greeting, 3 cards, no badge |
| Keyboard | Tab: logout → card links; visible white focus ring |
| JS disabled | page renders and logout submits |
| Console | no errors; Tailwind compiled (computed grid-template-columns = 4 at 1440) |

### Recorded results (2026-11-24, Chrome, dev server)

| Check | Result |
|---|---|
| Carrier @ 1366/1440 px | 4 cards; `grid-template-columns` = 4 columns (~259.5 px each); `main` max-width 1152 px; name + «شرکت حمل و نقل» badge |
| Carrier @ 768 px | 4 cards; 2 columns (327 px each); no horizontal overflow |
| Carrier @ 390 px | 4 cards; 1 column (308 px); stacked header; full-width logout; `scrollWidth == clientWidth` |
| Driver @ 1440 px | 3 cards (no Fleet in DOM); «راننده» badge; 4-column grid with one free track |
| Anonymous | 200; generic greeting; 3 cards; no badge; no Fleet |
| Invalid cookie | 200 anonymous view, no exception |
| Console errors | none |
| Automated | UI 38 passed; full suite 45 passed (PostgreSQL) |

## Commands
```powershell
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
venv\Scripts\python.exe -m pytest tests/test_ui_templates.py -v
venv\Scripts\python.exe -m pytest tests/ -v
venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

## Rollback
Presentation-only except the resolver: `git checkout -- templates/ app/main.py app/auth/security.py
tests/test_ui_templates.py`. No migration, no data change, so nothing to undo in the database. The
`base.html` block is additive and safe to keep independently.

## Risks and mitigations
| Risk | Mitigation |
|---|---|
| Invalid/expired/tampered cookie on a public page | Resolver returns `None`; never raises, never leaks. Tested by the anonymous case. |
| Name/role rendering opens an injection path | Jinja autoescaping; no `\|safe`; name comes from the DB via the model. |
| Wide layout breaks login/register | `main_class` block defaults to `max-w-md`; those templates are untouched. |
| Role gating by CSS only | Fleet card is excluded from the DOM server-side; test asserts absence. |
| Existing dashboard test expectations (`buttons[0]`, `bg-red-500/20`) | Logout stays the first `<button>`; card CTAs are `<a>`. Verified in Phase 4. |
| Placeholder links mislead users | `href="#"` + `data-future-route`; clearly listed as follow-ups, no fake success states. |
| Four gradient buttons look heavy | Compact buttons, one per card; verify visually at 4 columns and soften if needed without changing tokens. |

## Definition of done
- [x] SPEC approved; D1/D2 recorded; no open questions blocking work.
- [x] New dashboard tests GREEN; existing 37 tests GREEN unmodified; suite 45 passed.
- [x] All AC-1…AC-10 verified; AC-8/AC-9 confirmed by the diff.
- [x] Manual QA table passed at 320/390/768/1024/1440 px, carrier + driver + anonymous, keyboard, no-JS.
- [x] No ADR needed (no data-model/API change) — stated in the commit message or PR description.

## Follow-ups (not in this plan)
Real routes for the four cards; dashboard auth gate; live counts (open cargos, free slots); admin view;
role-specific card variants; notifications.
