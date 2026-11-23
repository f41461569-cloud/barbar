# SPEC: Login / Registration UI Redesign (Tailwind + RTL Glassmorphism)

## Status
Approved (2026-11-22). Decision **D1 = Option A** approved: on 401/409 the POST handlers re-render the
same template with a styled `error` and the same status code. Approved defaults: shared
`templates/base.html`, «باربری هوشمند» brand row with truck icon, Tailwind Play CDN pinned at `3.4.17`.

## Context
`templates/auth/login.html`, `templates/auth/register.html` and `templates/dashboard.html` are
standalone HTML files with inline `<style>` blocks, Tahoma font, a flat `#f4f6f8` background and
default browser form controls. They work and are covered by `tests/test_auth.py`, but they look
unfinished and nothing is shared between the three pages.

This spec redesigns those pages for a modern Persian (RTL) look using only a Tailwind CSS CDN and a
Google-hosted Vazirmatn font: gradient background, glassmorphism card, clean inputs, gradient button
and a styled error alert. It is a **presentation-only** change. Authentication behaviour, persistence
and the HTML form contract stay exactly as they are.

## Related documents
- `docs/SPEC-auth.md` (approved) — authentication behaviour and error status codes.
- `docs/adr/003-auth-jwt-cookie.md` (accepted) — JWT cookie; unaffected by this change.
- `docs/PLAN-ui.md` — implementation plan for this spec.
- `AGENTS.md` — spec/plan/TDD rules.

## Goals
1. Make login, registration and dashboard visually consistent, modern and credible.
2. Full RTL, Persian typography (Vazirmatn), correct bidi handling for phone/password fields.
3. Show form errors in a styled red alert instead of raw JSON or a blank page.
4. Work from 320 px phones up to desktop without horizontal scrolling.
5. Zero build step, zero JS framework.

## Non-goals
- No change to authentication logic, hashing, JWT, cookies or redirect targets.
- No new form fields, no renamed fields, no new validation rules (e.g. no `minlength`, no `pattern`,
  no client-side password policy). Visual-only change.
- No new pages, navigation, flash messages, i18n framework, theme switcher or dashboard data.
- No Tailwind build pipeline, PostCSS, npm, bundler or component library.
- No change to the database schema, models, migrations or public API (see §13).

## Scope — files
| File | Action |
|---|---|
| `templates/base.html` | **Create** — shared shell (head, fonts, Tailwind config, background, card slot). |
| `templates/auth/login.html` | Rewrite body to extend `base.html`; add error alert. |
| `templates/auth/register.html` | Rewrite body to extend `base.html`; add error alert. |
| `templates/dashboard.html` | Rewrite body to extend `base.html`; match style. |
| `app/auth/routes.py` | **Minimal change only if D1 = Option A** (pass `error` context / re-render). No endpoint, field or status-code change. |
| `tests/test_ui_templates.py` | **Create** — template/contract tests (TDD, see PLAN). |

Nothing else is modified. `app/main.py`, `app/models.py`, `alembic/`, `tests/test_auth.py` untouched.

## 1. Requirement traceability
| # | Requirement | Where addressed | Verified by |
|---|---|---|---|
| R1 | Tailwind via CDN, no build step | §4.1, base.html | AC-1 |
| R2 | Vazirmatn from Google Fonts | §4.2 | AC-1 |
| R3 | RTL + blue→purple gradient background | §5.1, §5.2 | AC-1, AC-10 |
| R4 | Glassmorphism card (translucent, blur, rounded) | §5.3 | AC-2, manual |
| R5 | Clean inputs with focus states | §6.2 | AC-3, AC-9 |
| R6 | Gradient button with hover effect | §6.4 | AC-4 |
| R7 | Styled red error alert | §7 | AC-5, AC-6 |
| R8 | Responsive on mobile | §9 | AC-10 |
| R9 | Same field names + POST endpoints | §8 | AC-7 |
| R10 | No JS framework; minimal inline JS only | §4.3, §11 | AC-1, AC-8 |
| R11 | Dashboard matches style | §10.3 | AC-11 |

## 2. Design direction
A single centered "auth card" floating on a deep blue→purple gradient, with two soft decorative
blurred orbs behind the glass. White-on-gradient typography, translucent inputs, one saturated
gradient primary action. Restrained: no gradients on text, no animation beyond hover/focus
transitions and an optional submit-busy state.

## 3. Layout skeleton
```
<html lang="fa" dir="rtl">
  <body class="min-h-screen flex items-center justify-center p-4 font-vazir ...gradient">
    <div aria-hidden="true"> decorative blobs (2, static) </div>
    <main class="w-full max-w-md">
      <section class="glass card"> brand row → h1 → form / content </section>
      <p class="footer link"> secondary link </p>
    </main>
  </body>
</html>
```

## 4. Platform constraints

### 4.1 Tailwind CDN
- Pin the Play CDN: `<script src="https://cdn.tailwindcss.com/3.4.17"></script>`.
- Inline config immediately after it (Play CDN requirement), adding only the font family:
  `tailwind.config = { theme: { extend: { fontFamily: { vazir: ['Vazirmatn','Tahoma','Arial','sans-serif'] } } } }`.
- No `@apply`, no external stylesheet, no build artifacts. All styling is utility classes in templates.
- Accepted trade-offs (documented, not blockers): Play CDN compiles in the browser (~100 KB JS,
  runtime style generation, brief unstyled flash, not intended for production). Migrating to a real
  build is a follow-up, out of scope here.

### 4.2 Typography
- `<link rel="preconnect" href="https://fonts.googleapis.com">`
- `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>`
- `<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700&display=swap" rel="stylesheet">`
- Weights used: 400 body, 500 labels/links, 700 headings/buttons. Fallback: `Tahoma, Arial, sans-serif`.
- Tahoma must no longer be the primary family.

### 4.3 JavaScript budget
- No framework, no `<script src>` other than the Tailwind CDN.
- Exactly one small inline script is allowed (in `base.html`, see §11), for double-submit protection.
- Every page must remain usable with JavaScript disabled (static markup + native form POST).

## 5. Visual system

### 5.1 Tokens
| Token | Value | Tailwind |
|---|---|---|
| Gradient (bg) | blue-700 → indigo-700 → purple-700 | `bg-gradient-to-br from-blue-700 via-indigo-700 to-purple-700` |
| Gradient (button) | blue-500 → purple-500 | `bg-gradient-to-r from-blue-500 to-purple-500` |
| Glass fill | white @ 10–15 % | `bg-white/10`, `hover:bg-white/15` |
| Glass border | white @ 20–25 % | `border border-white/20` |
| Blur | 24 px | `backdrop-blur-xl` |
| Radius | card 24 px, controls 12 px | `rounded-3xl`, `rounded-xl` |
| Shadow | deep, soft | `shadow-2xl`, `shadow-indigo-900/30` |
| Text | white, secondary 90 %, placeholder 60 % | `text-white`, `text-white/90`, `placeholder:text-white/60` |
| Danger | red-500 fill @ 20 %, red-300 border, red-50 text | `bg-red-500/20 border-red-300/40 text-red-50` |
| Focus ring | white, 2 px | `ring-2 ring-white/80` |
| Motion | 200 ms ease-out; disabled under reduced motion | `transition duration-200 motion-reduce:transition-none` |

Gradient stops are `*-700` (not `*-500`) to keep white body text at WCAG AA (≥ 4.5:1) across the
whole background. Verify with a contrast checker during implementation; darken stops if any pair
fails.

### 5.2 Background
- Full-viewport gradient on `<body>`; `min-h-screen` (with `min-h-dvh` as a 3.4 enhancement).
- Two decorative orbs, `aria-hidden="true"`, `pointer-events-none`, `absolute`, `blur-3xl`,
  `bg-purple-400/20` and `bg-blue-400/20`, clipped by `overflow-hidden` on a `fixed inset-0` wrapper.
- Static only: no keyframe animation, no `will-change`, so low-end mobiles are not penalised.

### 5.3 Glass card
`w-full max-w-md rounded-3xl border border-white/20 bg-white/10 p-6 shadow-2xl backdrop-blur-xl sm:p-8`
- `max-w-md` = 28 rem; card is always `w-full`, so it shrinks cleanly to 320 px.
- Browsers without `backdrop-filter` still get a legible semi-opaque card; no polyfill.
- Optional brand row above the heading: inline truck SVG (decorative, `aria-hidden`) + «باربری هوشمند»
  at `text-lg font-bold`, centered, `mb-6`.

## 6. Components

### 6.1 Card header
- `h1` once per page, `text-2xl font-bold` (login «ورود», register «ثبت نام», dashboard «داشبورد»).
- Optional one-line subtitle at `text-sm text-white/80` (presentation only, no new business text).

### 6.2 Inputs (text, tel, password, select)
Base: `w-full rounded-xl border border-white/25 bg-white/10 px-4 py-3 text-base text-white placeholder:text-white/60`
Focus: `focus:outline-none focus:border-white/60 focus:bg-white/15 focus:ring-2 focus:ring-white/70`
Invalid: `aria-invalid="true"` + `border-red-300/70` when the page was re-rendered with an error.
- `text-base` (16 px) is mandatory — prevents iOS Safari zoom-on-focus.
- Labels: `<label for>` always present, `mb-2 block text-sm font-medium text-white/90`.
- Field spacing: `space-y-4` on the form (uses `gap`, not `space-x`, to avoid RTL pitfalls).
- Bidi: `phone` and `password` get `dir="ltr" class="text-left"` so digits/secrets read naturally;
  `name` stays RTL. `phone` uses `type="tel" inputmode="tel" autocomplete="username"` (login) / `autocomplete="tel"` (register).
- `password`: `autocomplete="current-password"` (login) / `"new-password"` (register); no `maxlength`,
  no `minlength` (would change behaviour; server-side rules from SPEC-auth stay authoritative).
- No new required/optional rules: only the existing `required` attributes remain.

### 6.3 Select (role)
- Preserve exactly: `name="role"`, `required`, options `driver` / `shipper` / `carrier` with the
  existing Persian labels («راننده», «صاحب کالا / انبار», «شرکت حمل و نقل»).
- `appearance-none pr-4 pe-10` + wrapper `relative` + chevron SVG positioned `end-4 top-1/2 -translate-y-1/2
  pointer-events-none` (inline-end = left side in RTL).
- Native dropdown popup is OS-rendered; force readable options with
  `[&>option]:bg-white [&>option]:text-slate-900`.

### 6.4 Buttons
Primary (submit):
```
w-full rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 px-4 py-3 text-base font-bold text-white
shadow-lg shadow-indigo-900/30 transition-all duration-200
hover:from-blue-400 hover:to-purple-400 hover:shadow-xl hover:-translate-y-0.5
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-indigo-700
active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60
motion-reduce:transform-none motion-reduce:transition-none
```
Destructive/secondary (logout): same geometry, `border border-red-300/40 bg-red-500/20 text-red-50
hover:bg-red-500/30`, `focus-visible:ring-offset-purple-700`.
Minimum hit area 44×44 px (`py-3` satisfies it).

### 6.5 Links
`font-medium text-white underline decoration-white/50 underline-offset-4 hover:decoration-white
focus-visible:ring-2 focus-visible:ring-white/80 rounded`. Footer line: `mt-6 text-center text-sm text-white/80`.

## 7. Error display (requirement R7) — decision D1

### 7.1 Problem
`POST /auth/login` raises `HTTPException(401)` and `POST /auth/register` raises
`HTTPException(409)`; FastAPI renders those as **JSON** (`{"detail": ...}`). A template alone cannot
style a response it never renders. Styled alerts therefore require *some* server cooperation.

### 7.2 Options
| Option | Change | Pros | Cons |
|---|---|---|---|
| **A (recommended)** | In the two POST handlers, on the known failure, re-render the same template with `error=<message>` and the **same status code** (401 / 409). | No JS; works without JS; testable; no endpoint/field/status change. | ~15 lines in `app/auth/routes.py`; error body changes from JSON to HTML. |
| B | Keep templates only; add an inline `fetch` submit interceptor in `base.html` that maps 401/409 JSON to an alert. | Touches templates only. | ~30 lines of JS, breaks no-JS path, manual redirect/cookie handling, more failure modes. |
| C | Leave as is. | No changes. | Requirement R7 unmet: users see raw JSON. |

**Recommendation: A.** The contract that matters — paths, methods, field names, status codes,
redirects, cookie behaviour — is unchanged, and `tests/test_auth.py` (which asserts status codes
only) stays valid. HTML form endpoints have no JSON consumers, so the failure *body* change is not a
public-API change (§13). B is the documented fallback if `app/auth/routes.py` must not be touched; C
is rejected.

### 7.3 Alert component (used with Option A)
```
<div role="alert" aria-live="assertive"
     class="mb-5 flex items-start gap-3 rounded-xl border border-red-300/40 bg-red-500/20 p-4 text-sm text-red-50">
  <svg … aria-hidden="true" class="mt-0.5 h-5 w-5 shrink-0 text-red-200"><!-- warning triangle --></svg>
  <p class="leading-6">{{ error }}</p>
</div>
```
- Rendered only when `error` is truthy (`{% if error %}`); positioned above the form, below the `h1`.
- Meaning is carried by icon + text, not colour alone.
- Inputs referenced by the error get `aria-invalid="true"`; the alert is referenced with
  `aria-describedby` from the affected fields where practical.
- Messages (Persian, no field-level enumeration for login — see SPEC-auth §Edge Cases):
  - login 401 → «شماره تلفن یا رمز عبور نادرست است.»
  - register 409 → «این شماره تلفن قبلاً ثبت شده است.»
  - unexpected → «خطایی رخ داد. لطفاً دوباره تلاش کنید.» (500 handler not required by this spec)
- Failed submissions must **preserve** `phone` (and `name`/`role` on register) values via escaped Jinja
  (`value="{{ phone|default('', true) }}"`), and must **never** echo `password`. Jinja autoescaping
  stays on; `|safe` is forbidden for any user-provided value.
- FastAPI `422` validation errors (crafted requests; empty fields are already blocked by `required`)
  remain JSON in this iteration — documented limitation, listed under Follow-ups.

## 8. Preserved contract (must not change)
| Item | Value |
|---|---|
| GET | `/auth/login`, `/auth/register`, `/dashboard` |
| POST | `/auth/login`, `/auth/register`, `/auth/logout` |
| Register fields | `phone`, `name`, `password`, `role` (values `driver`, `shipper`, `carrier`) |
| Login fields | `phone`, `password` |
| Register success | `302` → `/auth/login` |
| Login success | `303` → `/dashboard` + `access_token` HttpOnly cookie (ADR 004) |
| Login failure | `401` (no cookie) |
| Duplicate phone | `409` (no second user) |
| Logout | `302` → `/auth/login`, cookie deleted |

## 9. Responsive behaviour
- Mobile-first. No fixed widths; card is `w-full max-w-md`.
- Breakpoints: 320 (min supported), 360, 390, 768, 1024, 1440.
- Card padding `p-6` → `sm:p-8`; page padding `p-4`; orbs stay off-canvas.
- No horizontal scroll at 320 px; long Persian strings wrap (`break-words` on the alert).
- Inputs stay 16 px+ so iOS does not zoom; form and button remain full-width on phones.

## 10. Page specifications

### 10.1 `templates/base.html` (new)
- Owns `<head>`: charset, viewport, `color-scheme: dark`, title block, preconnects, font link,
  Tailwind CDN + inline `tailwind.config`, and a **4-line inline `<style>` FOUC guard** only:
  `html{background:#4338ca}` + `font-family` fallback. No design rules in that block.
- Owns gradient body, orb wrapper, `<main>`/`<section>` shell, blocks:
  `{% block title %}`, `{% block card %}`, `{% block footer %}`, optional `{% block head %}`.
- Owns the one inline submit-guard script (§11), applied to any `form[data-guard]`.
- `login.html`, `register.html`, `dashboard.html` extend it and provide only cards + footers.

### 10.2 Login page
- `h1` «ورود»; fields in this order: `phone`, `password`; button «وارد شوید».
- Footer: «حساب ندارید؟ <a href="/auth/register">ثبت نام کنید</a>».
- Alert block above the form when `error` is set (Option A).

### 10.3 Registration page
- `h1` «ثبت نام»; fields in order: `phone`, `name`, `password`, `role`; button «ثبت نام».
- Footer: «حساب دارید؟ <a href="/auth/login">وارد شوید</a>».
- Same alert block; `phone`, `name` and selected `role` are re-populated on error.

### 10.4 Dashboard
- Same shell; `h1` «داشبورد»; welcome line «به باربری هوشمند خوش آمدید.» at `text-white/90`.
- Logout form unchanged (`method="post" action="/auth/logout"`), rendered as the destructive button.
- No new data (name/role display would need route/JWT changes — out of scope).

## 11. Double-submit guard (the only JS)
Six lines, inline in `base.html`, no framework:
```html
<script>
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('form[data-guard]');
    if (!f) return;
    var b = f.querySelector('button[type="submit"]');
    if (b) { b.disabled = true; b.setAttribute('aria-busy', 'true'); b.textContent = b.dataset.busyText || b.textContent; }
  });
</script>
```
Applied to login/register only (not logout). Rationale: a double-clicked register currently yields a
confusing 409; disabling after the first submit avoids it. Without JS the forms still work normally.

## 12. Accessibility
- `<html lang="fa" dir="rtl">`; one `h1` per page; `<main>` landmark.
- Every control has a programmatic label (`for`/`id`); no placeholder-only labels.
- Visible focus for every interactive element (`focus-visible` ring ≥ 3:1 against its surroundings).
- Error alert: `role="alert"` + `aria-live="assertive"`, reached in DOM before the form.
- Keyboard: logical tab order (phone → name → password → role → submit), Enter submits, no traps.
- Contrast: AA for body/labels/links; placeholders are supplementary (labels carry the meaning).
- `prefers-reduced-motion`: transitions/transforms disabled.
- Page usable at 200 % zoom and with JS disabled.

## 13. Change control / ADR position
- No data-model change: no model, column, index or migration is touched.
- No public-API change: endpoints, methods, field names, status codes, redirects and cookie flags are
  identical. The only difference is the **body** of 401/409 form responses (JSON → HTML) under
  Option A, on endpoints that exist solely to serve HTML forms and have no JSON consumers.
- Therefore **no new ADR is required**. ADR 001/003 remain in force. If implementation later changes
  a status code, endpoint, field name or cookie flag, stop and write an ADR first (AGENTS.md).

## 14. Acceptance criteria
- **AC-1** Each of the three GET pages returns 200 and contains: `lang="fa"`, `dir="rtl"`, the
  Vazirmatn Google Fonts link, the pinned Tailwind CDN script, `from-blue-700`/`to-purple-700`, and no
  `<script src>` other than the Tailwind CDN.
- **AC-2** Each page renders the glass card (`backdrop-blur-xl`, `bg-white/10`, `rounded-3xl`) inside
  a centered `max-w-md` container.
- **AC-3** Every input/select has a matching `<label for>` and a `focus:ring-2` utility.
- **AC-4** Submit buttons use the gradient + hover classes from §6.4; logout uses the destructive style.
- **AC-5** Wrong password → `401`, HTML response containing `role="alert"` and
  «شماره تلفن یا رمز عبور نادرست است.»; no `Set-Cookie`.
- **AC-6** Duplicate phone → `409`, HTML response containing `role="alert"` and
  «این شماره تلفن قبلاً ثبت شده است.»; only one user row exists.
- **AC-7** Form field names/values and all endpoints are byte-identical to §8; `tests/test_auth.py`
  passes unmodified.
- **AC-8** With JS disabled, login and registration still submit and redirect correctly.
- **AC-9** Focus outline is visible on all controls; tab order is logical; no keyboard traps.
- **AC-10** No horizontal scrolling at 320 px, 360 px and 768 px; card never overflows.
- **AC-11** Dashboard uses the same shell, gradient, typography and card styling, and its logout
  button matches the destructive style.
- **AC-12** No change to `app/models.py`, `alembic/`, or any migration; no new ADR.
- **AC-13** Failed submissions preserve `phone` (and `name`/`role`), and never echo the password.

## 15. Out of scope / follow-ups
- Tailwind build pipeline and CSP (`script-src`/`style-src`) hardening.
- Rendering `422` validation errors as HTML.
- CSRF tokens on the auth forms (pre-existing gap; requires a security decision, not this UI spec).
- Password reveal toggle, dark/light themes, toasts, loading spinners, password strength meter.
- Dashboard personalisation (name/role from the JWT).

## 16. Open questions (for approval)
1. **D1** — Error display: Option A (recommended), B (templates-only + JS), or C (accept JSON)?
2. Base layout: adopt new `templates/base.html` (recommended) or duplicate the shell in each page?
3. Keep the optional «باربری هوشمند» brand row with truck icon? (default: yes)
4. Pin Tailwind Play CDN at 3.4.17? (default: yes)
