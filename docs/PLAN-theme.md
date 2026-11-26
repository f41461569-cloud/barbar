# PLAN: Light Theme Redesign

## Status
Implemented — 2026-11-24. Visual/CSS-only change; suite remains **45 collected tests, all passing**
(38 UI + 5 auth + 2 concurrency). RED observed at 12 failed / 26 passed before the templates changed.

## Dependencies
- `docs/SPEC-theme.md` — approved spec and class recipes (required).
- `docs/SPEC-ui.md` — shell/form contracts and accessibility baseline (visual tokens superseded).
- `docs/SPEC-dashboard.md` — dashboard structure, role and Fleet rules (unchanged).
- `AGENTS.md` — spec/plan gate and TDD rule.
- Dev server: `venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000`.
- PostgreSQL for the 5 auth-failure/role assertions:
  `$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"`.

## Change-control position — no ADR required
CSS/design only:

- No model, column, index, migration or seed change.
- No endpoint, route, HTTP method, status code, redirect, cookie or form-field change.
- No new API surface, dependency or build step.
- Only Tailwind classes, the FOUC guard, and the `color-scheme` meta change.

**No new ADR** (ADR 001/003 remain in force). If any change reaches `app/**`, stop and re-scope.

## Files
| File | Action |
|---|---|
| `tests/test_ui_templates.py` | **first:** rewrite dark-theme assertions into light-theme assertions; same test count |
| `templates/base.html` | pastel canvas, white `rounded-2xl` shell, light FOUC guard, `color-scheme: light` |
| `templates/auth/login.html` | white inputs, violet→pink CTA, violet links/focus, soft-red alert, gray text |
| `templates/auth/register.html` | same, plus white select/options and gray chevron |
| `templates/dashboard.html` | white cards, violet icon tiles, role pills, soft-red logout, CTA recipe |

Not changed: `app/**`, `alembic/**`, `requirements.txt`, `templates/*` structure, `tests/test_auth.py`,
`tests/test_booking_concurrency.py`, `docs/SPEC-ui.md`, `docs/SPEC-dashboard.md`.

## Design decisions (from SPEC-theme)
- **Palette:** violet→pink (`from-violet-600 to-pink-600`); links/focus violet-700/600. No teal/coral
  (white-on-coral fails AA; two action colors would be inconsistent).
- **Cards:** pure `bg-white`, `rounded-2xl`, `border-gray-200`, soft shadow, no `backdrop-blur`.
- **Text:** headings `text-gray-800` (`#1f2937`), body `text-gray-500` (`#6b7280`).
- **Alerts:** `bg-red-50` / `text-red-700` / `border-red-200`.
- **Role pills:** driver blue, shipper emerald, carrier purple, admin orange.
- **Focus:** violet/red ring + white offset (never white-on-white).

## Steps (TDD; check off as completed)

### Phase 1 — RED (tests first)
1. [x] Record approval of `docs/SPEC-theme.md`; confirm no `app/**` change is needed.
2. [x] In `tests/test_ui_templates.py`, rewrite only the visual assertions:
   - `test_glass_card_and_gradient` → `test_light_theme_shell` (params unchanged: 3):
     `bg-white`, `border-gray-200`, `rounded-2xl`, `shadow-`, `from-pink-50`, `via-white`,
     `to-violet-100`, `text-gray-800`, `color-scheme" content="light"`; assert absence of
     `backdrop-blur`, `bg-white/10`, `text-white/`, `from-blue-700`, `via-indigo-700`,
     `to-purple-700`, `#4338ca`.
   - `test_primary_buttons_are_gradient`: `from-violet-600`, `to-pink-600`,
     `hover:-translate-y-0.5`, `focus-visible:ring-violet-600`; absence of `from-blue-500` /
     `to-purple-500`.
   - `test_dashboard_uses_same_shell_and_destructive_logout`: light shell tokens; first button
     `bg-red-50`, `text-red-700`, `border-red-200`; keep `action="/auth/logout"` and «داشبورد».
   - `test_dashboard_shows_three_cards_anonymously`: each `<article>` has `bg-white`, `rounded-2xl`,
     `border-gray-200`, `shadow-`, no `backdrop-blur`.
   - `test_dashboard_header_single_h1_generic_greeting_and_logout`: logout `bg-red-50`.
   - `test_dashboard_role_identity[...]`: add role-pill tokens (§9 SPEC) while keeping name, Persian
     label, badge presence, no-phone-leak, Fleet visibility.
   - `test_wrong_password_renders_styled_alert` and `test_duplicate_phone_renders_styled_alert`:
     add `bg-red-50`, `text-red-700`, `border-red-200`.
3. [x] Run the UI suite against the current dark templates → RED with the expected failures; confirm
   **38 UI tests collected** (no additions/removals). Behavior tests may stay green.
   Observed: 12 failed / 26 passed (3 shell + 1 CTA + 1 dashboard shell + 2 alerts + 1 card markup +
   4 role pills). Logout assertions were tightened with `class.split()` so `bg-red-50` could not
   match the old `bg-red-500/20` substring.

### Phase 2 — Shell
4. [x] `templates/base.html`:
   - `content="light"` for `color-scheme`;
   - FOUC guard `html{background:#ffffff}` + `color:#1f2937`;
   - body recipe from SPEC §3 (`from-pink-50 via-white to-violet-100`, `text-gray-800`);
   - orbs → `bg-pink-200/40`, `bg-emerald-200/40`, `bg-violet-200/40`;
   - shell → `rounded-2xl border border-gray-200 bg-white p-6 shadow-xl shadow-gray-200/50 sm:p-8`;
   - brand text `text-gray-800`, icon `text-violet-600`;
   - leave `main_class` block, blocks, and submit guard unchanged.

### Phase 3 — Auth pages
5. [x] `login.html`: headings/labels/footer to gray + violet tokens; inputs to white field recipe
   (`border-gray-300`, `focus:ring-2`, `focus:ring-violet-500/30`); error alert to
   `border-red-200 bg-red-50 text-red-700` (icon `text-red-500`); submit button to primary CTA.
6. [x] `register.html`: same as login, plus select `bg-white` / `[&>option]:bg-white` and chevron
   `text-gray-400`; preserve `current_role` selection logic.

### Phase 4 — Dashboard
7. [x] `dashboard.html`:
   - greeting label `text-gray-500`, `h1` `text-gray-800`;
   - role-pill class map (driver/shipper/carrier/admin) on the existing `data-role-badge` element;
   - card class → white `rounded-2xl` + `border-gray-200` + `shadow-sm` + `hover:shadow-md`;
   - icon tile → `bg-violet-50 text-violet-600`;
   - card `h2`/`p` → gray-800/gray-500;
   - CTA → violet→pink compact recipe with hover lift and violet ring;
   - logout → soft-red secondary recipe (still the first `<button>`);
   - keep grid classes, card order, routes, Fleet condition and all icons.

### Phase 5 — GREEN
8. [x] `pytest tests/test_ui_templates.py -v` → **38 passed**.
9. [x] `pytest tests/ -v` with PostgreSQL → **45 passed**.
10. [x] Grep for dark-theme remnants in `templates/` (see Commands) → no matches.
11. [x] Browser QA per §Manual QA and record results in this plan.
12. [x] `git diff --stat` shows only the five files above.

## Test strategy (test-by-test)
Counts are frozen: 30 original UI + 8 dashboard UI = 38; + 5 auth + 2 concurrency = **45**.

| Test | Change | Count |
|---|---|---|
| `test_light_theme_shell` (was `test_glass_card_and_gradient`) | new tokens, dark tokens forbidden, `color-scheme: light` | 3 |
| `test_primary_buttons_are_gradient` | violet→pink + lift + violet ring | 1 |
| `test_dashboard_uses_same_shell_and_destructive_logout` | light shell, logout `bg-red-50`/`text-red-700` | 1 |
| `test_dashboard_shows_three_cards_anonymously` | add white-card/radius/border/shadow assertions | 1 |
| `test_dashboard_header_single_h1_generic_greeting_and_logout` | logout token update | 1 |
| `test_dashboard_role_identity[driver/shipper/carrier/admin]` | add per-role pill tokens | 4 |
| `test_wrong_password_renders_styled_alert` | add soft-red alert tokens | 1 |
| `test_duplicate_phone_renders_styled_alert` | add soft-red alert tokens | 1 |
| All other UI tests | untouched | 25 |

`test_login_field_contract`, `test_register_field_contract` and `test_labels_are_linked` stay as-is:
the light inputs keep `name` attributes, `required`, ids and `focus:ring-2`.

`tests/test_auth.py` (5) and `tests/test_booking_concurrency.py` (2) must not change.

## Class recipes (copy-paste reference)
```text
Shell:   rounded-2xl border border-gray-200 bg-white p-6 shadow-xl shadow-gray-200/50 sm:p-8
Card:    flex h-full flex-col rounded-2xl border border-gray-200 bg-white p-5 shadow-sm
         transition-shadow duration-200 hover:shadow-md motion-reduce:transition-none
Icon:    mb-3 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-violet-50 text-violet-600
CTA:     rounded-xl bg-gradient-to-r from-violet-600 to-pink-600 text-base font-bold text-white
         shadow-lg shadow-pink-500/20 transition-all duration-200 hover:-translate-y-0.5
         hover:shadow-xl hover:shadow-pink-500/30 focus-visible:outline-none
         focus-visible:ring-2 focus-visible:ring-violet-600 focus-visible:ring-offset-2
         focus-visible:ring-offset-white active:translate-y-0 motion-reduce:transform-none
         motion-reduce:transition-none
Compact: px-4 py-2.5 text-sm mt-auto inline-flex w-full items-center justify-center gap-2
Input:   w-full rounded-xl border bg-white px-4 py-3 text-base text-gray-800 shadow-sm
         placeholder:text-gray-400 focus:outline-none focus:border-violet-500 focus:ring-2
         focus:ring-violet-500/30   (+ border-gray-300 | border-red-300 on error)
Alert:   mb-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700
Logout:  rounded-xl border border-red-200 bg-red-50 text-red-700 shadow-sm hover:bg-red-100
         focus-visible:ring-2 focus-visible:ring-red-600 focus-visible:ring-offset-2
         focus-visible:ring-offset-white
Link:    font-medium text-violet-700 underline decoration-violet-300 underline-offset-4
         hover:text-violet-800 hover:decoration-violet-500
```

## Commands
```powershell
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/smart_freight_test"
venv\Scripts\python.exe -m pytest tests/test_ui_templates.py -v
venv\Scripts\python.exe -m pytest tests/ -v

# no dark-theme remnants
Select-String -Path templates\*.html,templates\auth\*.html -Pattern 'backdrop-blur|bg-white/10|text-white/|from-blue-700|via-indigo-700|to-purple-700|#4338ca|bg-red-500/20'

venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

## Manual QA
Run in Chrome against the dev server; hard-refresh (Ctrl+F5) because Tailwind Play CDN compiles on load.

| Check | Expected |
|---|---|
| 320 / 390 px | 1 column; stacked header; full-width logout; no horizontal scroll; pastel canvas visible |
| 768 px | 2 columns; header in one row; white cards |
| 1024 / 1440 px | 4 columns; content capped at `max-w-6xl` (1152 px), centered |
| White cards | computed `background-color: rgb(255, 255, 255)`; `backdrop-filter: none` |
| Canvas | body has pink→white→lavender gradient; no dark blue/purple fill |
| Carrier | 4 cards; purple «شرکت حمل و نقل» pill; violet→pink CTAs |
| Driver | 3 cards (no Fleet in DOM); blue «راننده» pill |
| Shipper / admin | green / orange pills; admin sees Fleet |
| Anonymous | 3 cards, generic greeting, no pill, no Fleet |
| Login error | soft red panel `#fef2f2`, red text `#b91c1c`, visible red border |
| Duplicate register | same alert styling, preserved name/role, no password echo |
| Keyboard | Tab: logout → card CTAs; visible violet/red focus ring on white |
| JS disabled | page renders; logout submits; no layout dependence on JS |
| Console | no errors; Tailwind compiled |
| Contrast | headings `#1f2937`, body `#6b7280`, white on gradient ≥4.5:1, error text ≥4.5:1 |

### Recorded results
2026-11-24, Chrome (dev server, `--reload`):

| Check | Result |
|---|---|
| Automated | UI **38 passed**; full suite **45 passed**; `--collect-only` = 45 |
| Dark-token grep | no matches for any forbidden token in `templates/` |
| 320 px | 4 cards (carrier), 1 column, no horizontal scroll; header stacked; logout full-width |
| 390 px | same; pastel canvas, white cards; carrier pill purple `rgb(126, 34, 206)` on `#faf5ff` |
| 768 px | 4 cards, 2 columns, no overflow |
| 1366 / 1440 px | 4 cards, 4 columns; `main` capped at 1152 px, centered; no overflow |
| White cards | computed `background-color: rgb(255, 255, 255)`; `border-radius: 16px`; `backdrop-filter: none` |
| Canvas | `linear-gradient(to right bottom, #fdf2f8, #ffffff, #ede9fe)` |
| Text | body/headings computed `rgb(31, 41, 55)`; secondary `text-gray-500` |
| Logout | computed `bg #fef2f2`, text `#b91c1c` |
| Driver | 3 cards, no Fleet; blue pill `#eff6ff` / `#1d4ed8` |
| Login error | alert `bg #fef2f2`, border `#fecaca`, text `#b91c1c`; inputs white |
| Register | white inputs/select, violet→pink CTA, violet footer link |
| Keyboard | Tab: logout (red ring) → card CTA (violet ring); ring = white 2 px offset + 4 px color |
| Console | only the intentional 401 network entry from the failed-login check; no JS errors |

## Risks and mitigations
| Risk | Mitigation |
|---|---|
| Test-count drift | Only rewrite assertions; do not add/remove test functions or params. Verify `--collect-only` = 45. |
| White-on-white focus ring | Use violet-600/red-600 rings with `ring-offset-white`; explicitly asserted. |
| Gradient end too light for white text | Use violet-600→pink-600 (both ≥4.5:1); hover changes lift/shadow, not colors. |
| Dark tokens left in one template | Run the grep command in §Commands; SPEC §16 lists every forbidden token. |
| Glass fallback hidden in base shell | Remove `backdrop-blur-*` and all `bg-white/10`; test asserts their absence on all 3 pages. |
| Role pills confused with primary actions | Semantic 50/700 pills; primary actions are the only gradient surfaces. |
| Old tests encode `bg-red-500/20` | Update the two logout assertions; keep `action`, first-button order and text. |
| Auth/error states lose accessibility | Keep `role="alert"`, `aria-live`, `aria-invalid`, `aria-describedby`; only colors change. |
| Tailwind CDN cache during QA | Hard refresh; verify computed styles, not just class strings. |

## Rollback
`git checkout -- templates/base.html templates/auth/login.html templates/auth/register.html
templates/dashboard.html tests/test_ui_templates.py`. No migration or data change to undo.

## Definition of done
- [x] SPEC approved; palette and class recipes fixed; no open questions.
- [x] UI suite 38 passed; full suite 45 passed; no test added or removed.
- [x] `tests/test_auth.py` and `tests/test_booking_concurrency.py` untouched.
- [x] Grep for forbidden dark tokens returns no matches.
- [x] Manual QA passed at 320/390/768/1024/1440, carrier + driver + anonymous, keyboard, both error
      states (shipper/admin covered by the parametrized role test and identical markup).
- [x] Diff limited to the five files in §Files; `app/**` untouched.
- [x] No ADR required (CSS/design only) — stated in the commit message.

## Follow-ups (not in this plan)
- Refresh visual-token sections of `docs/SPEC-ui.md` and AC-7's test name in
  `docs/SPEC-dashboard.md`.
- Optional dark-mode toggle (separate spec; this change locks `color-scheme: light`).
- Design-token extraction if the class recipes start repeating across more templates.
