# SPEC: Light Theme Redesign (White Cards, Pastel Canvas, Violet→Pink Accent)

## Status
Draft — awaiting approval. Visual/CSS change only: no API, model, route, form-field or cookie change, so
**no new ADR is required** (see §19).

## Context
The current UI (`templates/base.html` + auth pages + dashboard) uses a dark glassmorphism system:
deep blue→indigo→purple gradient, `bg-white/10` translucent panels with `backdrop-blur-xl`, white text,
and blue→purple buttons. `docs/SPEC-ui.md` describes that system; `docs/SPEC-dashboard.md` adds the
role-aware dashboard.

This spec replaces the *visual layer* with a light, airy theme while keeping the existing shell
structure, RTL layout, Vazirmatn font, classes/blocks (`main_class`), accessibility contracts, form
field names, and all behavior. Only presentation classes and the FOUC guard change.

The suite must remain at **45 collected tests, all passing**. Tests that assert the old dark tokens are
rewritten to assert the new theme; behavioral tests (auth, fields, RTL, role identity, Fleet visibility)
remain semantically unchanged.

## Related documents
- `docs/SPEC-ui.md` — shell, form contracts, accessibility baseline (visual tokens superseded here).
- `docs/SPEC-dashboard.md` — dashboard structure and role/Fleet rules (visual tokens superseded here).
- `docs/adr/003-auth-jwt-cookie.md` — session cookie; untouched.
- `docs/PLAN-theme.md` — implementation plan.

## Goals
1. Light, airy canvas: white base with soft pink / mint / lavender pastel gradients.
2. Pure-white cards with a subtle border and soft shadow; **no glassmorphism**; `rounded-2xl`.
3. One consistent accent palette for primary actions, links, focus rings and non-role badges.
4. Readable text tokens: headings `#1f2937`, body `#6b7280`.
5. Soft red error alerts and role-colored status pills.
6. Preserve RTL, Vazirmatn, responsive 1/2/4-column behavior, keyboard focus and no-JS operation.
7. Keep the suite at 45 tests, all green.

## Non-goals
- No changes to `app/`, DB models, Alembic, endpoints, routes, cookies, or form field names.
- No new fonts, JS framework, component library, or custom build step (Tailwind Play CDN 3.4.17 stays).
- No layout restructuring: same shell, same blocks, same card order, same `data-*` hooks.
- No copy changes except where a visual label is unavoidable (none planned).
- No `docs/SPEC-ui.md` / `docs/SPEC-dashboard.md` edits in this change (see §20).

## 1. Decision — accent palette
Two suggested directions were considered:

| Option | Gradient | Links | Verdict |
|---|---|---|---|
| Teal → coral | `from-teal-600 to-rose-500` | teal | Warm, but white text on the coral end drops below 4.5:1; a teal action button with coral links breaks the "one accent" rule. |
| **Violet → pink (chosen)** | `from-violet-600 to-pink-600` | violet | Both gradient ends keep white text ≥ 4.5:1 (violet-600 ≈ 5.9:1, pink-600 ≈ 4.9:1), one coherent family, distinct from role pills. |

**Decision: violet→pink primary.** Violet is the action/focus/link color; pink is the warm end of the
primary gradient and the soft background wash. Role pills keep their own semantic colors (blue, green,
purple, orange), so they are not confused with primary actions.

## 2. Design tokens
Tailwind default scale only — no arbitrary hex classes, except the FOUC guard.

| Token | Tailwind | Hex | Use |
|---|---|---|---|
| Heading | `gray-800` | `#1f2937` | `h1`, `h2`, brand text, input text |
| Body | `gray-500` | `#6b7280` | subtitles, descriptions, labels' helper text |
| Border | `gray-200` | `#e5e7eb` | card and panel borders |
| Field border | `gray-300` | `#d1d5db` | inputs/selects |
| Canvas base | `white` | `#ffffff` | body base, cards, inputs |
| Pastel pink | `pink-50` / `pink-200/40` | `#fdf2f8` / `#fbcfe8` @40% | background gradient start / orb |
| Pastel mint | `emerald-200/40` | `#a7f3d0` @40% | background orb |
| Pastel lavender | `violet-100` / `violet-200/40` | `#ede9fe` / `#ddd6fe` @40% | background gradient end / orb |
| Primary start | `violet-600` | `#7c3aed` | CTA gradient start, focus ring |
| Primary end | `pink-600` | `#db2777` | CTA gradient end |
| Link | `violet-700` | `#6d28d9` | links |
| Error bg | `red-50` | `#fef2f2` | alert background |
| Error text | `red-700` | `#b91c1c` | alert text/icon container |
| Error border | `red-200` | `#fecaca` | alert border |

No `text-white/xx`, no `bg-white/10`, no `backdrop-blur-*`, no dark gradient tokens
(`from-blue-700`, `via-indigo-700`, `to-purple-700`), no `#4338ca`.

## 3. Background and shell (`templates/base.html`)
- `meta name="color-scheme"` → `content="light"`.
- FOUC guard: `html{background:#ffffff}` and `body{font-family:'Vazirmatn',…;color:#1f2937}`.
  Still the only inline `<style>`.
- Body:
  `flex min-h-screen items-center justify-center bg-gradient-to-br from-pink-50 via-white to-violet-100 p-4 font-vazir text-gray-800 antialiased`
- Decorative orbs (unchanged structure, pastel colors):
  - `bg-pink-200/40`, top-right;
  - `bg-emerald-200/40`, bottom-left;
  - `bg-violet-200/40`, upper-middle.
  All `rounded-full blur-3xl`, inside the existing `aria-hidden` fixed container.
- Shell panel: `rounded-2xl border border-gray-200 bg-white p-6 shadow-xl shadow-gray-200/50 sm:p-8`.
  **No** `backdrop-blur-*`, **no** `bg-white/10`.
- `main` keeps `relative w-full {% block main_class %}max-w-md{% endblock %}`; dashboard still overrides
  with `max-w-6xl`.
- Brand row: keep `data-brand="smart-freight"`, truck SVG, «باربری هوشمند»; text `text-gray-800`,
  icon `text-violet-600`.
- Submit-guard script unchanged.

## 4. Cards
Every white surface is `rounded-2xl`:
- Auth/shell panel: see §3.
- Dashboard feature card:
  `flex h-full flex-col rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow duration-200 hover:shadow-md motion-reduce:transition-none`
- No translucency, no gradient on card backgrounds. Cards are pure `bg-white`.
- Card icons sit in a `rounded-xl bg-violet-50 text-violet-600` tile (`h-11 w-11`), stroke SVG 1.8,
  `aria-hidden="true"`.
- No `rounded-3xl` remains on any surface.

## 5. Typography
- Font: Vazirmatn unchanged (Google Fonts link + `font-vazir`).
- Page `h1`: `text-2xl font-bold text-gray-800`.
- Section subtitle: `text-sm text-gray-500`.
- Card `h2`: `text-base font-bold text-gray-800`.
- Card body: `text-sm leading-6 text-gray-500`.
- Labels: `text-sm font-medium text-gray-700`.
- No white/translucent text anywhere except on gradient CTAs.

## 6. Buttons and links
Primary CTA (auth submit and card CTAs):

```
rounded-xl bg-gradient-to-r from-violet-600 to-pink-600
text-base font-bold text-white shadow-lg shadow-pink-500/20
transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-pink-500/30
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600
focus-visible:ring-offset-2 focus-visible:ring-offset-white
active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60
motion-reduce:transform-none motion-reduce:transition-none
```

- Compact card CTA: same colors/ring/lift with `px-4 py-2.5 text-sm` and `mt-auto w-full inline-flex
  items-center justify-center gap-2`.
- Hover keeps the same gradient (only lift + shadow) to preserve white-text contrast.
- Links: `font-medium text-violet-700 underline decoration-violet-300 underline-offset-4
  hover:text-violet-800 hover:decoration-violet-500 focus-visible:outline-none focus-visible:ring-2
  focus-visible:ring-violet-600 focus-visible:ring-offset-2 focus-visible:ring-offset-white`.
- Logout (secondary destructive):
  `rounded-xl border border-red-200 bg-red-50 text-red-700 shadow-sm hover:-translate-y-0.5
  hover:bg-red-100 hover:shadow-md focus-visible:ring-2 focus-visible:ring-red-600
  focus-visible:ring-offset-2 focus-visible:ring-offset-white` plus the existing motion-reduce and
  disabled rules where relevant. It remains the **first** `<button>` in the dashboard.
- Focus rings are never white-on-white: ring color violet-600 (primary), red-600 (destructive).

## 7. Inputs and selects (`login.html`, `register.html`)
- Shared field recipe:
  `w-full rounded-xl border bg-white px-4 py-3 text-base text-gray-800 shadow-sm
  placeholder:text-gray-400 focus:outline-none focus:border-violet-500 focus:ring-2
  focus:ring-violet-500/30`
- Border: `border-gray-300`; when `error`: `border-red-300` (keep `aria-invalid` and
  `aria-describedby="form-error"`).
- `focus:ring-2` must remain in the class string (existing field-contract test relies on it).
- Select adds `appearance-none pe-10 [&>option]:bg-white [&>option]:text-gray-800`; chevron
  `text-gray-400`.
- `dir="ltr"` on phone/password stays. No `value` on password fields.

## 8. Error alerts (`login.html`, `register.html`)
Replace the translucent red panel with:

```
mb-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700
```

Icon: `text-red-500`. Keep `id="form-error"`, `role="alert"`, `aria-live="assertive"` and the message
texts (`شماره تلفن یا رمز عبور نادرست است.`, `این شماره تلفن قبلاً ثبت شده است.`). No dark
`text-red-50`, `bg-red-500/20`, or `border-red-300/40` remains.

## 9. Role badges (dashboard)
Base: `mt-2 inline-flex rounded-full border px-3 py-1 text-xs font-medium` + per-role colors:

| Role | Pill classes | Meaning |
|---|---|---|
| `driver` | `border-blue-200 bg-blue-50 text-blue-700` | blue |
| `shipper` | `border-emerald-200 bg-emerald-50 text-emerald-700` | green |
| `carrier` | `border-purple-200 bg-purple-50 text-purple-700` | purple |
| `admin` | `border-orange-200 bg-orange-50 text-orange-700` | orange |

Keep `data-role-badge` on the element so tests and future tooling can locate it. The badge exists only
when authenticated; anonymous pages must not contain `data-role-badge`.

## 10. Auth pages
- `h1`: «ورود» / «ثبت نام» centered, `text-gray-800`.
- Subtitle: `text-gray-500`.
- Footer prompt: `text-sm text-gray-500`; links use the §6 link recipe.
- Submit buttons: §6 primary CTA, `data-busy-text` and `data-guard` behavior unchanged.
- Login and register keep `max-w-md` (default `main_class`).

## 11. Dashboard
Structure and behavior are unchanged from `docs/SPEC-dashboard.md`:
- Header: «خوش آمدید» (`text-gray-500`), `h1` name or generic line (`text-gray-800`), role pill per §9,
  logout form `method="post" action="/auth/logout"` per §6.
- Grid: `mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4`.
- Cards 1–3 always; Fleet card only when
  `current_user and current_user.role.value in ("carrier", "admin")` (server-side, not CSS-hidden).
- Card titles, descriptions, CTA labels, `data-future-route` values and order: unchanged
  (`/cargos`, `/time-slots`, `/bol`, `/fleet`).
- Every card uses the white recipe in §4; no glass tokens.

## 12. Responsive
No layout change intended; verify the theme does not introduce overflow:
- 320–639 px: 1 column; stacked header; full-width logout; CTAs full width.
- 640–1023 px: 2 columns; header becomes a row at `sm`.
- ≥1024 px: 4 columns; content capped at `max-w-6xl` (1152 px) and centered.
- `scrollWidth == clientWidth` at 320/390/768/1024/1440; text reflows at 200% zoom.

## 13. Accessibility and contrast
- Contrast targets (WCAG AA): headings 14.6:1, body 4.8:1, violet-700 links 7.0:1, white on
  violet-600 ≈5.9:1, white on pink-600 ≈4.9:1, red-700 on red-50 ≈6.5:1, pill text on its 50-tint ≥4.5:1.
- One `h1` per page; card titles `h2`; DOM order preserved.
- All icons stay `aria-hidden="true"`; every control keeps a visible text label.
- Focus is always visible on white: violet-600 / red-600 2 px ring with white offset.
- `motion-reduce:transform-none` + `motion-reduce:transition-none` on lifts/transitions.
- `role="alert"` + `aria-live="assertive"` on errors; fields keep `aria-invalid`/`aria-describedby`.
- Page still works with JavaScript disabled (plain HTML + POST form).

## 14. Files
| File | Action |
|---|---|
| `templates/base.html` | light canvas, pastel orbs, white shell, light FOUC guard, `color-scheme: light` |
| `templates/auth/login.html` | white inputs, new CTA/link/focus tokens, soft-red alert, gray text |
| `templates/auth/register.html` | same as login, plus select/chevron colors |
| `templates/dashboard.html` | white cards, violet icon tiles, role pills, soft-red logout, CTA recipe |
| `tests/test_ui_templates.py` | replace dark-theme assertions with light-theme assertions (same test count) |

Not changed: `app/**`, `alembic/**`, `requirements.txt`, `templates/auth/*` structure, `docs/*`.
No new files, no new dependencies.

## 15. Test contract — 45 tests stay 45
The suite is **rewritten, not expanded**. Collected counts unchanged: 38 UI + 5 auth + 2 concurrency =
**45**.

Rewritten assertions in `tests/test_ui_templates.py`:
1. `test_glass_card_and_gradient` → **`test_light_theme_shell`** (3 params, same count): asserts
   `bg-white`, `border-gray-200`, `rounded-2xl`, `shadow-`, `from-pink-50`, `via-white`, `to-violet-100`,
   `text-gray-800`, `color-scheme" content="light"`; asserts **absence** of `backdrop-blur`,
   `bg-white/10`, `text-white/`, `from-blue-700`, `via-indigo-700`, `to-purple-700`, `#4338ca`.
2. `test_primary_buttons_are_gradient` (1): `from-violet-600`, `to-pink-600`,
   `hover:-translate-y-0.5`, `focus-visible:ring-2`, `focus-visible:ring-violet-600`; absence of
   `from-blue-500`/`to-purple-500`.
3. `test_dashboard_uses_same_shell_and_destructive_logout` (1): light shell tokens instead of
   `backdrop-blur-xl`; first button has `bg-red-50`, `text-red-700`, `border-red-200` (instead of
   `bg-red-500/20`); `action="/auth/logout"` and «داشبورد» unchanged.
4. `test_dashboard_shows_three_cards_anonymously` (1): each `<article>` additionally has `bg-white`,
   `rounded-2xl`, `border-gray-200`, `shadow-`, and no `backdrop-blur`.
5. `test_dashboard_header_single_h1_generic_greeting_and_logout` (1): logout assertion moves to
   `bg-red-50`; generic greeting, single `h1`, no badge unchanged.
6. `test_dashboard_role_identity[driver|shipper|carrier|admin]` (4): add the role-pill class
   assertions from §9 (`bg-blue-50`/`text-blue-700`, `bg-emerald-50`/`text-emerald-700`,
   `bg-purple-50`/`text-purple-700`, `bg-orange-50`/`text-orange-700`); keep name, Persian label,
   badge presence, no-phone-leak and Fleet visibility checks.
7. `test_wrong_password_renders_styled_alert` + `test_duplicate_phone_renders_styled_alert` (2, PG):
   add `bg-red-50`, `text-red-700`, `border-red-200` assertions; keep alert/status/text checks.

Unchanged (must remain green):
`test_page_is_rtl_persian`, `test_tailwind_is_pinned_cdn`, `test_no_legacy_style_or_js_framework`,
`test_brand_row_with_truck_icon`, `test_login_field_contract`, `test_register_field_contract`,
`test_labels_are_linked`, `test_password_is_never_prefilled`, `test_no_alert_on_clean_get`,
`test_dashboard_grid_and_container`, `test_dashboard_ignores_invalid_cookie`, the remaining failure
paths, `tests/test_auth.py`, `tests/test_booking_concurrency.py`.

Note: `test_light_theme_shell` replaces the old name; `docs/SPEC-dashboard.md` AC-7 still mentions the
old name and is intentionally not edited here (§20).

## 16. No dark-theme remnants
After implementation, this must return no matches in `templates/`:

```
backdrop-blur | bg-white/10 | text-white/ | from-blue-700 | via-indigo-700 | to-purple-700 | #4338ca | bg-red-500/20
```

(`text-white` inside gradient buttons is allowed and expected.)

## 17. Acceptance criteria
- **AC-1** Every page (login, register, dashboard) renders a white shell/card with `rounded-2xl`,
  `border-gray-200`, and a soft shadow; no `backdrop-blur` or translucent white surfaces.
- **AC-2** Canvas is white with pastel pink/mint/lavender gradients; `color-scheme` is `light`; the FOUC
  guard is white.
- **AC-3** Headings use `text-gray-800` (#1f2937) and body/secondary text uses `text-gray-500` (#6b7280).
- **AC-4** Primary CTAs use `from-violet-600 to-pink-600`, white text, hover lift
  (`hover:-translate-y-0.5`), and a violet focus ring with white offset.
- **AC-5** Links use violet-700 with the same focus treatment; no white-on-white focus ring.
- **AC-6** Error alerts are `bg-red-50` + `text-red-700` + `border-red-200`, keeping
  `role="alert"`/`aria-live` and existing messages.
- **AC-7** Role pills are blue/green/purple/orange per §9, `rounded-full`, and only present when
  authenticated.
- **AC-8** Dashboard keeps one `h1`, header greeting, logout posting to `/auth/logout` as the first
  button, three base cards, Fleet only for carrier/admin, and all `data-future-route` values.
- **AC-9** Layout is 1/2/4 columns at mobile/tablet/desktop; no horizontal scroll at 320, 390, 768,
  1024 or 1440 px.
- **AC-10** RTL, `lang="fa"`, Vazirmatn, pinned Tailwind 3.4.17 CDN, and single-script-src contract are
  preserved.
- **AC-11** Tests: 38 UI + 5 auth + 2 concurrency = **45 passed**; no behavioral assertions weakened;
  `tests/test_auth.py` and `tests/test_booking_concurrency.py` untouched.
- **AC-12** `app/**`, models, migrations, routes and `requirements.txt` are untouched.

## 18. Manual QA
320 / 390 / 768 / 1024 / 1440 px; carrier, driver, anonymous; keyboard-only; JS disabled; a forced
login error and a duplicate-registration error. Details and expected values are in
`docs/PLAN-theme.md` §Manual QA.

## 19. Change control / ADR position
- No data-model, migration, endpoint, route, status code, cookie, or form-field change.
- No new public API or behavior.
- Therefore **no new ADR**. ADR 001/003 remain in force. If implementation starts touching `app/**`,
  stop and re-scope.

## 20. Out of scope / follow-ups
- Refreshing the visual-token sections of `docs/SPEC-ui.md` and AC-7's test name in
  `docs/SPEC-dashboard.md` (docs-only touch-up; not part of this change).
- Dark-mode toggle (explicitly not requested; `color-scheme` becomes light).
- New illustrations, logos, or icon set changes.
- Component extraction/macros; the templates stay explicit.
