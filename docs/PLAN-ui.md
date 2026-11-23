# PLAN: Login / Registration UI Redesign (Tailwind + RTL Glassmorphism)

## Status
Approved — implementation in progress (2026-11-22). **D1 = Option A** (re-render the same template
with a styled error, same 401/409 status). Confirmed defaults: shared `templates/base.html`, brand row
with truck icon, Tailwind Play CDN `3.4.17`.

## Dependencies
- `docs/SPEC-ui.md` — approved spec (required before coding).
- `docs/SPEC-auth.md` — behaviour that must not change (status codes, redirects, cookie flags).
- `docs/adr/003-auth-jwt-cookie.md` — in force; this plan does not alter it.
- `AGENTS.md` — spec/plan gate, TDD-first rule.
- Runnable PostgreSQL (`DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test`)
  for the existing auth tests; template-only GET tests run without a database.

## Change-control position — no ADR required
This work requires **no data-model change and no public-API change**, therefore **no new ADR**:

- No model, column, index or Alembic revision is touched.
- Paths, methods, form field names (`phone`, `name`, `password`, `role`), status codes (401/409),
  redirect targets (`/auth/login`, `/dashboard`) and cookie flags (`HttpOnly`, `SameSite=Lax`,
  `max_age`) stay exactly as they are.
- The only server-side change permitted is, under SPEC D1 Option A, re-rendering the *same* template
  with an `error` message and the *same* status code on 401/409. These endpoints serve HTML forms
  only and have no JSON consumers, so this is a UI response-body change, not an API contract change.
- If implementation ever needs a status-code, field-name, endpoint or cookie change, that is a
  separate task and needs an ADR first (AGENTS.md). Do not fold it into this work.

## Files
| File | Action | Notes |
|---|---|---|
| `templates/base.html` | create | Font links, Tailwind CDN + config, gradient shell, card slot, submit guard. |
| `templates/auth/login.html` | rewrite | Extends base; phone/password; error alert; footer link. |
| `templates/auth/register.html` | rewrite | Extends base; phone/name/password/role; error alert; footer link. |
| `templates/dashboard.html` | rewrite | Extends base; welcome; logout button restyled. |
| `app/auth/routes.py` | edit (D1 = A only) | Pass `error` + preserved values; re-render with 401/409. ~15 lines. |
| `tests/test_ui_templates.py` | create | TDD: contract + markup assertions. |
| `tests/test_auth.py` | unchanged | Must stay green; it asserts status codes only. |

## Steps (TDD; check off as completed)

### Phase 1 — RED
1. [x] Confirm SPEC approval and record the D1 answer at the top of this file.
2. [x] **RED:** create `tests/test_ui_templates.py` with the AC-1…AC-11 markup/contract tests and the
   AC-5/AC-6/AC-13 error-rendering tests. Run it; it must fail (no `base.html`, old markup, JSON errors).
3. [x] Run `pytest tests/test_auth.py -v` first to record the green baseline before touching anything.

### Phase 2 — Shell
4. [x] Create `templates/base.html` per SPEC §10.1:
   - `<html lang="fa" dir="rtl">`, viewport, `<meta name="color-scheme" content="dark">`.
   - preconnects + Vazirmatn `css2?family=Vazirmatn:wght@400;500;700&display=swap`.
   - `<script src="https://cdn.tailwindcss.com/3.4.17"></script>` then inline `tailwind.config`
     with `fontFamily.vazir` only.
   - 4-line inline `<style>` FOUC guard (`html{background:#4338ca}` + font fallback) — nothing else.
   - gradient `body`, `overflow-hidden` orb wrapper with 2 static `blur-3xl` orbs, centered `<main
     class="w-full max-w-md">`, glass `<section>`.
   - blocks: `title`, `card`, `footer`, `head`.
   - the 6-line submit guard script from SPEC §11 (targets `form[data-guard]` only).
5. [x] Verify no other `<script src>`, no external CSS besides Google Fonts, no `@apply`.

### Phase 3 — Login
6. [x] Rewrite `templates/auth/login.html` to `{% extends "base.html" %}` per SPEC §10.2:
   - `data-guard` on the form; `method="post" action="/auth/login"` unchanged.
   - optional brand row; `h1` «ورود».
   - `{% if error %}` alert (§7.3) with warning icon, `role="alert"`, `aria-live="assertive"`.
   - `phone`: `type="tel" inputmode="tel" dir="ltr" class="text-left" autocomplete="username"`
     `value="{{ phone|default('', true) }}"` `required`; `aria-invalid` when `error`.
   - `password`: `type="password" dir="ltr" class="text-left" autocomplete="current-password"` `required`; never prefilled.
   - gradient submit «وارد شوید»; footer «حساب ندارید؟ ثبت نام کنید».

### Phase 4 — Register
7. [x] Rewrite `templates/auth/register.html` per SPEC §10.3 — same shell, `data-guard`, `h1` «ثبت نام».
   - `phone` (`autocomplete="tel"`), `name` (`autocomplete="name"`, RTL), `password`
     (`autocomplete="new-password"`), `role` select with the **exact** values/labels from SPEC §6.3.
   - Re-populate `phone`, `name`, `role` (selected) on error; never `password`.
   - Gradient submit «ثبت نام»; footer «حساب دارید؟ وارد شوید».

### Phase 5 — Dashboard
8. [x] Rewrite `templates/dashboard.html` per SPEC §10.4: same shell/card, `h1` «داشبورد», welcome
   line, logout form unchanged, destructive button style.

### Phase 6 — Error rendering (D1 = Option A; only if approved)
9. [x] In `app/auth/routes.py`:
   - `register`: on duplicate phone, return `templates.TemplateResponse(request=request,
     name="auth/register.html", context={"request": request, "error": "این شماره تلفن قبلاً ثبت شده است.",
     "phone": phone, "name": name, "role": role}, status_code=409)`.
   - `login`: on bad credentials, return the login template with
     `error="شماره تلفن یا رمز عبور نادرست است."`, `phone=phone`, `status_code=401`.
   - No change to signatures, field names, success paths, cookies or redirects.
   - Add `request: Request` to the POST handlers only as needed for the response.
10. [x] If D1 resolving is **B** instead: keep routes untouched and add the `fetch` interceptor to
    `base.html`; then AC-8 (works without JS) is waived for error display and must be noted in the spec.
    If **C**: remove AC-5/AC-6/AC-13 and log the requirement as unmet. — *Not applicable: A chosen.*

### Phase 7 — GREEN and verification
11. [x] Run `pytest tests/test_ui_templates.py -v` → GREEN.
12. [x] Run `pytest tests/test_auth.py -v` with PostgreSQL → GREEN, unmodified.
13. [x] Run full suite `pytest tests/ -v` → no regressions (booking concurrency untouched).
14. [x] Manual visual QA (§ below) and contrast/focus checks.
15. [x] Confirm AC-12: no changes to models/migrations; only the intended files were touched.

## Implementation record (2026-11-22)
- **Tests:** `pytest tests/ -q` → **37 passed** (5 auth, 2 booking concurrency, 30 UI), exit code 0.
  `tests/test_auth.py` and `tests/test_booking_concurrency.py` were not modified.
- **TDD:** UI suite was confirmed RED first (old markup, missing Tailwind/font/alert), then GREEN after
  implementation.
- **Visual QA (real Chrome, `browse`):** login/register/dashboard at 1366×633, 390×844, 360×800 and
  320×568 — card 16 px from each edge, `scrollWidth == clientWidth` at every width (no horizontal scroll).
- **Login error state:** click submit with a wrong password → status 401, `role="alert"` +
  `aria-live="assertive"`, Persian message, phone preserved, password empty, `aria-invalid="true"`
  (verified visually and via the accessibility snapshot).
- **Focus/keyboard:** computed focus ring is a 2 px white shadow + lightened border + `bg-white/15`;
  Tab order is phone → name → password → role → submit → footer link (no traps).
- **Contrast:** white labels ≈ 6.98:1 and `white/80` subtitles ≈ 5.47:1 against the lightest gradient
  stop (purple-700); AA for body text.
- **No-JS path:** the POST → 302 flow and the 401/409 HTML responses are exercised by `TestClient`
  (which runs no JavaScript), so the no-JS requirement is covered server-side.
- **Autofill note:** the user's Chrome autofilled saved values into the phone/password fields during
  QA; the templates themselves render no `value` on `password` (asserted by test).

## Test strategy (TDD)

`tests/test_ui_templates.py` — GET tests need no database; failure-path tests are skipped unless
`DATABASE_URL` is a PostgreSQL URL (same guard as `tests/test_auth.py`).

**Markup / contract (no DB)**
- `test_pages_are_rtl_persian`: GET each of `/auth/login`, `/auth/register`, `/dashboard` → 200,
  contains `dir="rtl"`, `lang="fa"`, `fonts.googleapis.com/css2?family=Vazirmatn`, `cdn.tailwindcss.com`.
- `test_no_legacy_stylesheet_or_framework`: response does not contain `#f4f6f8`, `Tahoma, Arial` as
  primary, `react`, `vue`, `alpine`, `jquery`; exactly one external `<script src>` (Tailwind).
- `test_glass_and_gradient_classes`: contains `backdrop-blur-xl`, `bg-white/10`, `rounded-3xl`,
  `max-w-md`, `from-blue-700`, `to-purple-700`.
- `test_login_field_contract`: ids/names `phone`, `password`; both `required`; labels linked.
- `test_register_field_contract`: `phone`, `name`, `password`, `role`; option values exactly
  `driver`, `shipper`, `carrier`; admin absent; labels linked.
- `test_buttons_styled`: submit button has `from-blue-500`, `to-purple-500`, `hover:` and
  `focus-visible:ring`; dashboard logout uses `bg-red-500/20`.
- `test_focus_styles_on_controls`: every `input`/`select` class list contains `focus:ring-2`.
- `test_no_inline_value_for_password`: register/login HTML never contains a `password` `value=`
  attribute.

**Failure paths (DB)**
- `test_wrong_password_renders_alert`: register a throwaway user, POST wrong password →
  `status_code == 401`, body contains `role="alert"` and «شماره تلفن یا رمز عبور نادرست است.»;
  `set-cookie` absent.
- `test_duplicate_phone_renders_alert`: register, register again → `409`, body contains `role="alert"`
  and «این شماره تلفن قبلاً ثبت شده است.»; `SELECT count(*)` for that phone == 1.
- `test_error_preserves_phone_but_not_password`: POST bad login → body contains submitted phone and
  does not contain the submitted password.
- `test_no_enumeration`: unknown phone → 401 with the same message as wrong password.

**Reuse** `tests/test_auth.py` helpers/patterns (`_new_phone`, `_cleanup`, UUID phones), and clean up
in `finally`. Do not weaken or delete any existing auth assertion.

## Manual visual QA
Use the installed `browse` tools (or a browser) against `uvicorn app.main:app --reload`:
| Check | Expected |
|---|---|
| 320 / 360 px | card full-width, 16 px page padding, no horizontal scroll, button full-width |
| 768 / 1440 px | card centered at 28 rem, generous padding, orbs visible but not distracting |
| Login error | red glass alert above form; phone preserved; password empty; focus visible |
| Register error | alert shown; phone/name/role preserved; role still selected |
| Keyboard only | Tab order phone → name → password → role → submit; white focus ring always visible |
| JS disabled | login/register submit normally; redirects unchanged |
| Reduced motion | hover lift disabled; no animation |
| Contrast | body/labels/links ≥ 4.5:1 over the gradient; placeholders readable |
| Double-click submit | second click ignored (button disabled) |

## Commands
```powershell
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
venv\Scripts\python.exe -m pytest tests/test_auth.py -v          # baseline
venv\Scripts\python.exe -m pytest tests/test_ui_templates.py -v  # RED -> GREEN
venv\Scripts\python.exe -m pytest tests/ -v                      # no regressions
venv\Scripts\uvicorn.exe app.main:app --reload                   # manual QA at http://127.0.0.1:8000/auth/login
```

## Rollback
Presentation-only, so rollback is `git checkout -- templates/ app/auth/routes.py` (or revert the
single commit). No migration is applied and no data is changed, so there is nothing to undo in the
database. If D1 = A is rolled back alone, errors fall back to JSON while the styled pages keep working.

## Risks and mitigations
| Risk | Mitigation |
|---|---|
| Play CDN latency/offline → unstyled page | FOUC guard style; documented accepted trade-off; build migration as follow-up. |
| Tailwind class typos (CDN has no compile error) | Visual QA + class assertions in tests. |
| `backdrop-blur` cost on low-end phones | Two static orbs only, no animation; `motion-reduce` respected. |
| Styled errors require a route edit | D1 Option A limited to error responses; endpoints/status codes untouched; Option B documented. |
| Echoing user input (XSS) | Jinja autoescaping; no `|safe`; explicit test that password is never echoed. |
| RTL layout bugs with spacing utilities | Use `gap`/logical `ps`/`pe`/`start`/`end`; no `space-x`/hardcoded `left`. |
| iOS zoom on focus | `text-base` (16 px) on all controls. |
| Behaviour drift (new validation) | No `minlength`/`pattern`/`maxlength` added; AC-7 + existing tests enforce contract. |

## Definition of done
- [ ] SPEC approved; D1 recorded; no open questions left.
- [ ] `tests/test_ui_templates.py` GREEN; `tests/test_auth.py` GREEN unmodified; full suite GREEN.
- [ ] All AC-1…AC-13 verified, including AC-12 (no model/migration/API change) and no new ADR.
- [ ] Manual QA table passed at 320/360/768/1440 px, keyboard-only, and JS-disabled.
- [ ] Diff limited to `templates/base.html`, `templates/auth/login.html`,
      `templates/auth/register.html`, `templates/dashboard.html`, `app/auth/routes.py` (D1 = A only),
      `tests/test_ui_templates.py`, and this plan/spec.

## Follow-ups (not in this plan)
Tailwind build + CSP; HTML rendering for 422; CSRF tokens on auth forms; password reveal toggle;
dashboard personalisation from the JWT.
