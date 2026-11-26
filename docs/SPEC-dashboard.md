# SPEC: Dashboard Redesign (Role-Aware Feature Cards)

## Status
Approved — 2026-11-24. **D1 = A** (optional cookie resolver), **D2 = A** (`main_class` block, `max-w-6xl`).
**Admin also sees the Fleet card**; only driver and shipper are excluded. No new ADR (no data-model or
API change).

## Context
`GET /dashboard` currently renders a single small glass card with a heading, one welcome line and a
logout button. It shows no identity, no role and no way to reach the product's features. The rest of
the UI already uses the shared shell in `templates/base.html` (Tailwind Play CDN 3.4.17, Vazirmatn,
RTL, blue→purple gradient, glassmorphism).

This spec turns the dashboard into a landing hub: a header with the logged-in user's name and role,
the existing logout button, and four feature cards matching the product (Available Cargos, Time
Slots, Digital Bill of Lading, Fleet Management). Buttons are placeholders until the feature routes
exist.

## Related documents
- `docs/SPEC-ui.md` (approved) — design system, base shell, accessibility baseline.
- `docs/SPEC-auth.md`, `docs/adr/003-auth-jwt-cookie.md` — the JWT cookie used to identify the user.
- `docs/SPEC.md`, `docs/adr/001-data-model.md` — cargo/slot/booking model referenced by the cards.
- `docs/SRS.md` — FR-3…FR-9 describe the features the cards lead to.
- `docs/PLAN-dashboard.md` — implementation plan.

## Goals
1. Greet the user by name and show the role (driver / shipper / carrier / admin).
2. Surface the four main features as tappable cards with icon, title, short description and button.
3. Show **Fleet Management only to carriers**.
4. Look like the rest of the app and stay responsive (1 / 2 / 4 columns).
5. Keep the logout button, and keep the page static HTML for now.

## Non-goals
- No new endpoints, no new API, no data-model change.
- No live counts, charts or statistics on the cards.
- No dashboard auth gate / RBAC enforcement (the page stays public for now, see D3).
- No JS framework; no client-side data fetching.
- No changes to login/registration pages.

## 1. Constraint conflict — read before approving

The brief says "files to update: `templates/dashboard.html` only", but two requirements are impossible
in that file alone:

| # | Requirement | Why dashboard.html alone cannot satisfy it |
|---|---|---|
| C1 | Show the logged-in user's **name and role** | `app/main.py` passes only `{"request": request}` to the template. The JWT is in an **HttpOnly** cookie, so the template/JS cannot read it. The name is not even in the token (claims: `sub`, `phone`, `role`). |
| C2 | Show **Fleet Management only to carrier** | The template has no role value to branch on (same root cause as C1). |
| C3 | **4 columns on desktop** | `base.html` hardcodes `<main class="relative w-full max-w-md">` (28 rem). Four cards inside 448 px would be ~100 px each. A wider container requires one additive block in `base.html`. |

### D1 — How the dashboard learns name and role
| Option | Change | Pros | Cons |
|---|---|---|---|
| **A (recommended)** | Add an **optional** current-user resolver that reads `request.cookies.get("access_token")`, decodes the JWT, loads the `User`, and pass it to the existing `GET /dashboard` as `current_user`. No new endpoint. | Server-rendered, works without JS, no secrets exposed, role gating is real. | Touches `app/main.py` (+ `app/auth/security.py`), not just the template. |
| B | Static placeholders («کاربر عزیز») and show all four cards to everyone. | Template-only. | Requirements "name", "role" and "carrier-only" are not met. |
| C | Put name/role in a second, **non-HttpOnly** cookie at login. | Template reads it via JS-free markup? No — template cannot read cookies either; needs JS. | Weakens the HttpOnly design and leaks identity to JS; also touches login. Rejected. |

**Recommendation: A.** It changes no endpoint, no response contract for other routes and no data
model; it only enriches the existing dashboard context. Anonymous visits still return 200 with a
generic greeting and the three public cards, so the existing dashboard tests keep passing.

### D2 — Wide layout for four columns
| Option | Change | Pros | Cons |
|---|---|---|---|
| **A (recommended)** | Add one block to `base.html`: `{% block main_class %}max-w-md{% endblock %}` and use it on `<main>`; dashboard overrides with `max-w-6xl`. | Additive, non-breaking; login/register keep `max-w-md`. | One line in a shared file. |
| B | Dashboard does not extend `base.html`; duplicate the head/gradient/orbs. | Template-only. | Duplicated design system; drift risk; violates "same design system as base.html". |
| C | Keep `max-w-md` and put 4 cards in a horizontal scroller. | No shell change. | Does not meet "4 columns on desktop"; poor UX. |

**Recommendation: A.**

### D3 — Anonymous `/dashboard`
Keep the page public: generic greeting, no role badge, three cards (no Fleet). This preserves the
current behaviour and the existing UI tests. Adding an auth gate is a separate change with its own
tests (redirect target, return-to URL) and is explicitly out of scope here.

## 2. Files (contingent on D1/D2)
| File | Action | Needed for |
|---|---|---|
| `templates/dashboard.html` | rewrite | always |
| `templates/base.html` | +1 block (`main_class`), default `max-w-md` | D2 = A |
| `app/auth/security.py` | add `get_optional_current_user(request, db)` | D1 = A |
| `app/main.py` | `GET /dashboard` depends on the resolver, passes `current_user` | D1 = A |
| `tests/test_ui_templates.py` | add dashboard tests | always (TDD, per PLAN) |

No other file changes. The dashboard template continues to extend `base.html`.

## 3. Page structure

```
GET /dashboard
└── base.html shell (gradient, orbs, Vazirmatn, brand row, glass panel, main_class = max-w-6xl)
    └── block card
        ├── header  (welcome + role badge   |   logout form)
        └── grid    (1 / 2 / 4 columns)
            ├── card  Available Cargos
            ├── card  Time Slots
            ├── card  Digital Bill of Lading
            └── card  Fleet Management   (carrier + admin)
```

The brand row stays as provided by `base.html`. The page keeps exactly one `h1` (the greeting: the
user's name, or the generic line); «داشبورد» lives in the document `<title>` and card titles are
`h2`.

## 4. Header

- Container: `flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between`.
- Greeting block:
  - `p` small label `text-sm text-white/70` — «خوش آمدید»
  - `h1` `text-2xl font-bold` — `{{ current_user.name }}` (authenticated) or «به باربری هوشمند خوش آمدید.»
  - Role badge, authenticated only: `rounded-full border border-white/25 bg-white/15 px-3 py-1 text-xs font-medium text-white/90`.
- Logout form: unchanged contract — `method="post" action="/auth/logout"`, button styled exactly as
  today (`bg-red-500/20`, hover `bg-red-500/30`, white focus ring) so the existing dashboard test and
  muscle memory survive. Placed at the inline-end of the header (`sm:ms-auto`), full-width under the
  greeting on mobile.
- Role labels (single source of truth in the template):

| Role value | Persian label |
|---|---|
| `driver` | راننده |
| `shipper` | صاحب کالا / انبار |
| `carrier` | شرکت حمل و نقل |
| `admin` | مدیر سیستم |

## 5. Feature cards

### 5.1 Grid
`mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4` — 1 column < 640 px, 2 columns 640–1023 px,
4 columns ≥ 1024 px. Cards stretch to equal height (`h-full`).

### 5.2 Card anatomy
```
<article class="flex h-full flex-col rounded-2xl border border-white/15 bg-white/5 p-5
                transition-colors duration-200 hover:bg-white/10
                motion-reduce:transition-none">
  icon   → inline SVG in a 44×44 rounded-xl tile (aria-hidden="true")
  h2     → text-base font-bold
  p      → text-sm text-white/75 leading-6
  <a>    → compact gradient button, mt-auto (pinned to the card bottom)
</article>
```
- Icons: 24 px stroke SVG (box, calendar-clock, document, users/vehicles), `stroke-width="1.8"`,
  decorative only. No icon font, no external assets.
- Titles must match the brief exactly: «لیست بارهای موجود», «نوبت‌دهی بارگیری», «بارنامه دیجیتال»,
  «مدیریت ناوگان».

### 5.3 Card content

| # | Title | Description (short) | Button label | Future route | Visible to |
|---|---|---|---|---|---|
| 1 | لیست بارهای موجود | بارهای ثبت‌شده برای حمل را ببینید و انتخاب کنید. | مشاهده بارها | `/cargos` | all roles + anonymous |
| 2 | نوبت‌دهی بارگیری | نوبت خالی انبارها را رزرو کنید. | رزرو نوبت | `/time-slots` | all roles + anonymous |
| 3 | بارنامه دیجیتال | بارنامه سفر را مشاهده و وضعیت آن را پیگیری کنید. | مشاهده بارنامه | `/bol` | all roles + anonymous |
| 4 | مدیریت ناوگان | رانندگان و ظرفیت ناوگان را مدیریت کنید. | مدیریت ناوگان | `/fleet` | **carrier and admin** |

- Button is an `<a>` because it navigates: `href="#"` for now, with `data-future-route="/cargos"` (etc.)
  so the intended destination is recorded and searchable. No JS, no disabled control: the link is
  keyboard reachable and announced with its visible text.
- Buttons use the compact gradient recipe: `mt-auto inline-flex w-full items-center justify-center gap-2
  rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 px-4 py-2.5 text-sm font-bold text-white
  transition-all duration-200 hover:from-blue-400 hover:to-purple-400 hover:shadow-lg
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white
  focus-visible:ring-offset-2 focus-visible:ring-offset-indigo-700 motion-reduce:transition-none`.
- Button text is not the only affordance: the whole card is *not* a link (avoids nested interactive
  elements); only the button navigates.
- Fleet card is rendered only when `current_user and current_user.role.value == "carrier"`. Anonymous
  and other roles never see it (no CSS hiding — it must not be in the DOM).

## 6. Reuse of the design system
- No new colours, fonts, shadows or gradients: everything comes from the existing tokens
  (`from-blue-700 via-indigo-700 to-purple-700`, `bg-white/10`, `backdrop-blur-xl`, `rounded-3xl`,
  `shadow-2xl`, Vazirmatn, `focus-visible` white rings).
- Inner cards are one step lighter than the outer glass panel (`bg-white/5` → `bg-white/10` on hover)
  so nesting still reads as glass.
- No extra `<style>` and no extra JS; the only scripts remain base.html's Tailwind config and the
  submit guard.

## 7. Accessibility
- One `h1`; card titles are `h2`, in DOM order 1→4.
- Icons `aria-hidden="true"`; every link/button has a visible text label.
- Keyboard: Tab order = logout → card buttons (1→4); visible 2 px white focus ring on every control.
- Greeting is plain text, not an image; role is text, not colour-coded only.
- Contrast: body `text-white` on the gradient, secondary text at least `text-white/75` (≥ 4.5:1 against
  the lightest stop; verify with a contrast check).
- Reduced motion respected on card/button transitions.
- Page remains usable with JavaScript disabled (it is plain HTML + POST form).

## 8. Responsive acceptance
| Width | Expected |
|---|---|
| 320 / 360 / 390 px | 1 column; header stacked; logout full-width; no horizontal scroll |
| 768 px | 2 columns; header row (greeting inline-start, logout inline-end) |
| 1024 / 1440 px | 4 columns; content capped by `max-w-6xl` and centered |
| 200 % zoom | no overlap; text reflows |

## 9. Change control / ADR position
- No data-model change: models, migrations and seed data untouched.
- No new API and no change to existing endpoints, status codes, form fields, redirects or cookies.
  `GET /dashboard` keeps its path and its 200 response; it merely receives a richer template context
  (D1 = A).
- Therefore **no new ADR is required**. ADR 001/003 remain in force. Reading the existing HttpOnly
  cookie server-side is exactly how ADR 003 intends the session to be used. If implementation later
  changes an endpoint, status code, cookie flag or adds auth gating, stop and write an ADR first.

## 10. Acceptance criteria
- **AC-1** Authenticated request to `/dashboard` renders the user's `name` and the correct Persian role
  label for `driver`, `shipper`, `carrier` and `admin`.
- **AC-2** Anonymous `/dashboard` returns 200 with a generic greeting, no role badge, and cards 1–3.
- **AC-3** Cards 1–3 are present for every role; card 4 (مدیریت ناوگان) appears **only** for `carrier`
  and `admin` and is absent from the DOM for driver, shipper and anonymous.
- **AC-4** Each card contains an icon (`aria-hidden`), an `h2` title from §5.3, a description and a
  link button; links carry the `data-future-route` values from §5.3.
- **AC-5** Grid classes are exactly `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`; at 320/390 px there is
  one column and no horizontal scroll (`scrollWidth == clientWidth`).
- **AC-6** The logout form still posts to `/auth/logout` and its button keeps `bg-red-500/20`.
- **AC-7** Existing dashboard assertions still pass unmodified: `test_dashboard_uses_same_shell_and_destructive_logout`,
  `test_glass_card_and_gradient[/dashboard]`, `test_brand_row_with_truck_icon[/dashboard]`,
  `test_page_is_rtl_persian[/dashboard]`, `test_tailwind_is_pinned_cdn[/dashboard]`.
- **AC-8** Only `templates/dashboard.html` (plus `templates/base.html` for D2 and `app/main.py` +
  `app/auth/security.py` for D1, if approved) and `tests/test_ui_templates.py` change; no model,
  migration or `requirements.txt` change.
- **AC-9** No new endpoint and no new/renamed form field; `/docs` and `/api/bookings` are untouched.
- **AC-10** Keyboard-only run reaches logout and all visible card buttons with a visible focus ring;
  the page works with JS disabled.

## 11. Out of scope / follow-ups
- Real feature routes (`/cargos`, `/time-slots`, `/bol`, `/fleet`) — cards only carry the intended path.
- Dashboard auth gate and RBAC enforcement (D3).
- Live metrics (counts of open cargos/slots), notifications, charts.
- Admin-specific cards or fleet visibility for admins (decided: admins *do* see the Fleet card).

## 12. Resolved decisions (2026-11-24)
1. **D1 = A** — identity comes from an optional server-side resolver that reads the HttpOnly
   `access_token` cookie (Bearer header as fallback). No new endpoint.
2. **D2 = A** — `base.html` gains a `main_class` block defaulting to `max-w-md`; the dashboard
   overrides it with `max-w-6xl`. Login/register stay `max-w-md`.
3. **Admin sees the Fleet card** alongside carrier; it is hidden from driver, shipper and anonymous.
