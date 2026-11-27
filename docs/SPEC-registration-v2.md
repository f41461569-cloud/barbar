# SPEC: Registration v2 — Landing, Role-Specific Forms, and Admin Login

## Status
Approved — 2026-11-27. Decisions D1–D10 approved. Implementation follows
`docs/PLAN-registration-v2.md` under AGENTS.md (spec/plan gate + ADR for data-model/public-API changes).

## 1. Context

The current auth flow is a single registration form (`phone`, `name`, `password`, `role`) followed by a
shared phone/password login. The new design gives each role its own registration path and collects the
data the role actually needs:

- **Driver** — identity, license, truck and plate details.
- **Shipper / warehouse owner** — identity and cargo preference.
- **Admin** — a username and an admin code; admins log in on a separate page.

The redesign also replaces the light violet/pink auth styling with the product palette: dark navy
(`#0a192f`), bright yellow (`#fbbf24`), white cards, and Vazirmatn.

This SPEC supersedes the registration/login page requirements in `docs/SPEC-auth.md` and the auth-page
visual requirements in `docs/SPEC-ui.md`. ADR 003 (JWT in an HttpOnly cookie) and ADR 004 (303 after
login) remain in force. ADR 007 records the data-model, route, status-code, and admin-code decisions.

**Visual assumption:** no mockup image/PDF files were present in the repository when this SPEC was
written. The visual requirements below come from the written brief (navy `#0a192f`, yellow `#fbbf24`,
white cards, Vazirmatn, right-aligned icons, white truck, «باربر هوشمند»). If mockups exist, attach them
before approval; only visual details/spacing/assets should change, not the flow, fields, or routes.

## 2. Goals

| ID | Goal |
|---|---|
| G1 | A visitor can choose Driver, Shipper, or Admin from a landing page and reach the correct form. |
| G2 | Each form collects exactly the fields required for that role, with server-side validation. |
| G3 | Registration ends on a role-aware success page, then the user logs in. |
| G4 | Admin registration and admin login both require a deployment-level admin code. |
| G5 | The UI matches the navy/yellow/white design brief, is RTL, Persian, responsive, and accessible. |
| G6 | Existing users and existing pages keep working; the data-model change is additive and reversible on a scratch database. |
| G7 | The existing test suite is updated for the new required fields and the new page contracts, with no weakened assertions. |

## 3. Non-goals

- Carrier self-registration in the new landing page (the `carrier` role remains in the model and can log in).
- Company/legal-entity registration (`company_id`), KYC, document upload during registration, SMS/email
  verification, OTP, captcha, or password reset.
- Password confirmation, password-strength meter, or a password-reveal toggle.
- Per-admin codes, admin user management, admin invitation flow, or an admin audit log.
- CSRF tokens, login rate limiting, account lockout, or a WAF (existing gaps; see §18).
- Changes to driver-document review, cargo, booking, or dashboard behavior.
- A Tailwind build pipeline, npm, a component library, or a JS framework.
- Changing the JWT cookie flags, lifetime, or the post-login `/dashboard` redirect.
- Retroactively requiring the new profile fields from existing driver/shipper accounts.

## 4. Related documents

- `docs/adr/007-registration-v2-user-model.md` — **required**; proposed data-model and API decisions.
- `docs/PLAN-registration-v2.md` — TDD, test migration, migration verification, rollback.
- `docs/adr/003-auth-jwt-cookie.md` — cookie-based session; unchanged.
- `docs/adr/004-login-redirect-303.md` — login returns `303` to `/dashboard`; unchanged.
- `docs/SPEC-auth.md` — superseded for registration/login page behavior.
- `docs/SPEC-ui.md` — superseded for auth-page styling; its accessibility rules still apply where not
  contradicted here.
- `AGENTS.md` — spec/plan/TDD/ADR gate.

## 5. Roles and entry points

| Role | Registration entry | Login entry | Notes |
|---|---|---|---|
| Driver | `/auth/register/driver` | `/auth/login` | Phone + password after registration. |
| Shipper / Warehouse Owner | `/auth/register/shipper` | `/auth/login` | Phone + password after registration. |
| Admin | `/auth/register/admin` | `/auth/admin/login` | Username + password + admin code. |
| Carrier | — (not in the landing page) | `/auth/login` | Existing carrier accounts keep working; new ones are provisioned out of band. |

Role checks are server-side. Hiding a link is never sufficient.

## 6. Routes and flow

### 6.1 Flow

```
GET /auth/register                     landing (Driver | Shipper | Admin)
        │
        ├── /auth/register/driver ──POST──► 303 /auth/register/success?role=driver ──► /auth/login
        ├── /auth/register/shipper ─POST──► 303 /auth/register/success?role=shipper ─► /auth/login
        └── /auth/register/admin ──POST──► 303 /auth/register/success?role=admin ───► /auth/admin/login
```

- Registration is open to anonymous visitors.
- A successful registration creates the account and redirects with **303** (POST → Redirect → GET).
- The success page is a GET; refreshing it does not re-submit the form.
- Login success is unchanged: **303** → `/dashboard` with the `access_token` HttpOnly cookie.
- Logout is unchanged: **302** → `/auth/login` and the cookie is deleted.

### 6.2 Endpoint contract

| Method | Path | Request | Success | Failure |
|---|---|---|---|---|
| GET | `/auth/register` | — | `200` landing | — |
| GET | `/auth/register/driver` | — | `200` form | — |
| POST | `/auth/register/driver` | form fields §7.2 | `303` success | `422` / `409` |
| GET | `/auth/register/shipper` | — | `200` form | — |
| POST | `/auth/register/shipper` | form fields §7.3 | `303` success | `422` / `409` |
| GET | `/auth/register/admin` | — | `200` form | — |
| POST | `/auth/register/admin` | form fields §7.4 | `303` success | `401` / `409` / `503` |
| GET | `/auth/register/success?role=...` | `role` ∈ driver/shipper/admin | `200` success | `404` for unknown role |
| GET | `/auth/login` | — | `200` form | — |
| POST | `/auth/login` | `phone`, `password` | `303` `/dashboard` + cookie | `401` |
| GET | `/auth/admin/login` | — | `200` form | — |
| POST | `/auth/admin/login` | `username`, `password`, `admin_code` | `303` `/dashboard` + cookie | `401` / `503` |
| POST | `/auth/logout` | — | `302` `/auth/login`, cookie cleared | — |

- The legacy `POST /auth/register` is removed. `GET /auth/register` now serves the landing page, so a
  POST to that path returns `405`.
- Missing/blank fields are validated in the route/service and re-rendered as HTML `422`, not FastAPI's
  JSON validation response. Form parameters therefore use empty-string defaults.
- `role` on the success page is validated against the allowlist; anything else is `404`.
- All form endpoints accept `application/x-www-form-urlencoded` (standard HTML form POST).

## 7. Fields and validation

### 7.1 Common rules

| Field | Rule |
|---|---|
| `full_name` | Trim; 3–100 characters; at least one non-space character. Stored in `users.name`. |
| `phone` | Normalize Persian/Arabic digits and `+98`/`0098`/`98`/`0` prefixes; require an Iranian mobile (`9xxxxxxxxx` after normalization); store `+989xxxxxxxxx`. |
| `national_id` | Normalize digits; exactly 10 digits; reject all-identical digits; verify the standard Iranian national-ID checksum; store 10 digits. |
| `license_number` | Trim; normalize digits/letters to uppercase; 5–30 characters from `[0-9A-Za-z-]`; unique. |
| `plate_number` | Trim; normalize Persian/Arabic digits/letters; 5–20 characters; indexed but not unique. |
| `truck_type` | One of the allowlist in §7.2. |
| `cargo_type_preference` | One of the allowlist in §7.3. |
| `password` | 8–72 characters, not all whitespace, at most 72 UTF-8 bytes (bcrypt limit); bcrypt hash only. |
| `username` | Trim; lowercase; 3–50 characters matching `^[a-z0-9][a-z0-9._-]{2,49}$`; unique. |
| `admin_code` | Non-empty; compared to `settings.ADMIN_CODE` with `secrets.compare_digest`; never stored or echoed. |

Browser hints (`required`, `inputmode`, `autocomplete`, `maxlength`) are supplementary. The server is
authoritative. Do not add a client-side `pattern` that would reject Persian digits before the server can
normalize them.

### 7.2 Driver form

| Order | Field name | Persian label | Input | Required | Notes |
|---|---|---|---|---|---|
| 1 | `full_name` | نام و نام خانوادگی | text, RTL | yes | `autocomplete="name"` |
| 2 | `phone` | شماره تلفن | tel, LTR | yes | `inputmode="tel"`, `autocomplete="tel"` |
| 3 | `national_id` | کد ملی | text, LTR | yes | `inputmode="numeric"`, `maxlength="10"` |
| 4 | `license_number` | شماره گواهینامه | text, LTR | yes | `autocomplete="off"` |
| 5 | `truck_type` | نوع خودرو | select | yes | options below |
| 6 | `plate_number` | شماره پلاک | text, RTL/LTR mix | yes | `autocomplete="off"` |
| 7 | `password` | رمز عبور | password, LTR | yes | `autocomplete="new-password"` |

`truck_type` options (value → label): `pickup` → «وانت», `khavar` → «خاور», `truck` → «کامیون»,
`trailer` → «تریلی», `refrigerated` → «یخچال‌دار», `tanker` → «تانکر». Include an empty
«انتخاب کنید» option; it is not a valid submission.

### 7.3 Shipper form

| Order | Field name | Persian label | Input | Required | Notes |
|---|---|---|---|---|---|
| 1 | `full_name` | نام و نام خانوادگی | text, RTL | yes | `autocomplete="name"` |
| 2 | `phone` | شماره تلفن | tel, LTR | yes | `inputmode="tel"`, `autocomplete="tel"` |
| 3 | `cargo_type_preference` | نوع بار | select | yes | options below |
| 4 | `national_id` | کد ملی | text, LTR | yes | `inputmode="numeric"`, `maxlength="10"` |
| 5 | `password` | رمز عبور | password, LTR | yes | `autocomplete="new-password"` |

`cargo_type_preference` options (value → label): `general` → «عمومی», `perishable` → «فاسدشدنی»,
`fragile` → «شکستنی», `bulk` → «فله», `hazardous` → «خطرناک», `heavy` → «ماشین‌آلات / سنگین».
Include an empty «انتخاب کنید» option.

### 7.4 Admin form

| Order | Field name | Persian label | Input | Required | Notes |
|---|---|---|---|---|---|
| 1 | `username` | نام کاربری | text, LTR | yes | `autocomplete="username"` |
| 2 | `password` | رمز عبور | password, LTR | yes | `autocomplete="new-password"` |
| 3 | `admin_code` | کد مدیریت | password, LTR | yes | `autocomplete="off"` |

There is no phone field on the admin form. On success, `users.name` is set to the username and
`users.phone` stays `NULL`.

### 7.5 Login forms

User login (`/auth/login`):

| Order | Field name | Persian label | Input | Required |
|---|---|---|---|---|
| 1 | `phone` | شماره تلفن | tel, LTR, `autocomplete="username"` | yes |
| 2 | `password` | رمز عبور | password, LTR, `autocomplete="current-password"` | yes |

Admin login (`/auth/admin/login`):

| Order | Field name | Persian label | Input | Required |
|---|---|---|---|---|
| 1 | `username` | نام کاربری | text, LTR, `autocomplete="username"` | yes |
| 2 | `password` | رمز عبور | password, LTR, `autocomplete="current-password"` | yes |
| 3 | `admin_code` | کد مدیریت | password, LTR, `autocomplete="off"` | yes |

Admin login resolves the identifier as `users.username` first. If no username matches and the value
looks like a phone, it may resolve a legacy admin by normalized phone (ADR 007 §5). The form still
labels the field «نام کاربری»; a small help line may mention that legacy admins can enter their phone.

## 8. Admin code

- Source: `settings.ADMIN_CODE` (environment variable `ADMIN_CODE`), empty by default.
- Required for both `POST /auth/register/admin` and `POST /auth/admin/login`.
- Compared in constant time with `secrets.compare_digest`.
- Never stored in `users`, never rendered back into the form, never logged, and never included in a
  JWT.
- If `ADMIN_CODE` is empty, both admin endpoints return `503` and render a generic page:
  «ورود مدیران در حال حاضر فعال نیست.» Do not fall back to a default code.
- A wrong code returns `401` with a generic message. Do not reveal whether the username exists.
- The configured code should be at least 16 random characters in deployed environments. This is a
  deployment requirement, not an input-validation rule.
- Rotating the code affects future admin logins only; existing JWTs live until their normal expiry.

## 9. Authentication and session

- Password hashing stays bcrypt via the existing `passlib` context.
- User login authenticates `driver`, `shipper`, and `carrier` by phone. An admin account on this route
  gets the same generic `401` as a wrong password.
- Admin login authenticates only `admin`. A non-admin account gets the same generic admin `401`.
- Login failure never sets a cookie.
- Login success sets the existing `access_token` cookie: `HttpOnly`, `SameSite=Lax`, `max_age=3600`,
  path `/` (ADR 003/004). `Secure` remains a production deployment concern.
- JWT payload keeps `sub` and `role`; include `phone` only when non-null and `username` only when
  non-null. Do not include national ID, license, plate, or admin code.
- `get_optional_current_user` is unchanged: cookie first, Bearer fallback, invalid/expired tokens return
  `None`.
- Logout is unchanged and clears the cookie. It redirects to `/auth/login` even for admins; the admin can
  use the «ورود مدیران» link.

## 10. Visual system

### 10.1 Tokens

| Token | Value | Tailwind / usage |
|---|---|---|
| Navy | `#0a192f` | `bg-[#0a192f]` — header, page background |
| Navy elevated | `#112240` | `bg-[#112240]` — subtle gradient/panel |
| Yellow | `#fbbf24` | `bg-[#fbbf24]`, `text-[#fbbf24]`, `border-[#fbbf24]` — primary buttons, accents, links on navy |
| Button text | gray-900 / black | `text-gray-900` — text on yellow primary buttons |
| Yellow hover | `#fcd34d` | `hover:bg-[#fcd34d]` |
| White card | `#ffffff` | `bg-white` |
| Card border | slate-200 | `border-slate-200` |
| Body text | slate-900 | `text-slate-900` |
| Muted text | slate-500 | `text-slate-500` |
| Error | red-50 / red-200 / red-700 | alert inside white cards |
| Success | emerald-50 / emerald-200 / emerald-700 | success notice |
| Radius | card 16 px, controls 12 px | `rounded-2xl`, `rounded-xl` |
| Shadow | soft, deep | `shadow-2xl shadow-black/20` |
| Focus ring | yellow, 2 px | `focus:ring-2 focus:ring-[#fbbf24]/40` |

Do not introduce violet/pink gradients, glassmorphism, or dark text on dark navy. Yellow buttons always
use dark navy/black text.

### 10.2 Typography and platform

- `<html lang="fa" dir="rtl">`.
- Vazirmatn from Google Fonts: weights `400;500;700;800`, with `preconnect` to `fonts.googleapis.com`
  and `fonts.gstatic.com` (crossorigin). Fallback `Tahoma, Arial, sans-serif`.
- Tailwind Play CDN pinned at `https://cdn.tailwindcss.com/3.4.17`, with an inline
  `tailwind.config` that registers the `vazir` font family.
- Exactly one external `<script src>` (Tailwind). The only inline JS is the existing double-submit
  guard in `base.html`; every page must work with JavaScript disabled.
- `color-scheme` is `light` because the cards are white, even though the page background is navy.

### 10.3 Shared shell (`templates/base.html`)

- Full-width header on navy, bottom border `border-white/10`.
- Header inner container: `mx-auto flex max-w-6xl items-center justify-between px-4 py-4`.
- Right side (RTL start): inline white truck SVG (32×32, `aria-hidden="true"`) + «باربر هوشمند» in
  `text-lg font-bold text-white`. The brand may link to `/dashboard` or be a non-link; do **not** link
  it to `/` (the app has no root route).
- Optional header action block for a link (e.g. «ورود» on the landing page, «ثبت‌نام» on login pages).
  The dashboard may leave it empty.
- Page background: navy with a subtle `from-[#0a192f] to-[#112240]` vertical gradient. No animated
  background, no heavy blur.
- Main container: `mx-auto w-full px-4 py-8 sm:py-12` plus the page's `main_class`:
  - login, role forms, success, admin login: `max-w-md`.
  - landing role grid: `max-w-5xl`.
  - dashboard and existing wide pages: `max-w-6xl` (preserve current behavior).
- Content card: `rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl shadow-black/20 sm:p-8`.
  Existing pages that already render their own white card keep their internal layout; the shell card is
  the outer white surface.
- Add a `card_class` block so the landing page can opt out of the outer white surface and place the
  heading directly on navy, with three white role cards (default: the white card classes above;
  landing: `bg-transparent p-0 shadow-none border-0`).
- Footer block: centered text on navy, `text-sm text-slate-300`; links use yellow with a visible focus
  ring.
- The brand text in page `<title>` blocks is «باربر هوشمند». Replace the old «باربری هوشمند» string in
  templates touched by the shell.

### 10.4 Forms and controls

- White card, `space-y-4` (or `space-y-5`) form stack.
- Label above each control: `mb-2 block text-sm font-medium text-slate-700`.
- Input base:
  `w-full rounded-xl border border-slate-200 bg-white py-3 pr-11 pl-4 text-base text-slate-900 placeholder:text-slate-400 shadow-sm focus:outline-none focus:border-[#fbbf24] focus:ring-2 focus:ring-[#fbbf24]/40`.
- Icon wrapper: `pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400`, with an
  inline SVG (user, phone, id-card, license/card, truck, plate, lock, shield/key). Icons are decorative
  (`aria-hidden="true"`); labels carry the meaning.
- Right-aligned icons are physical-right (`right-3`), matching the brief, even when the input text is
  LTR. Numeric/secret fields use `dir="ltr" class="text-left"`.
- Select: native `<select>` with `appearance-none`, right icon/chevron at the inline end, and readable
  options (`[&>option]:bg-white [&>option]:text-slate-900`).
- Primary button:
  `w-full rounded-xl bg-[#fbbf24] px-4 py-3 text-base font-bold text-gray-900 shadow-lg shadow-amber-500/20 transition-all duration-200 hover:bg-[#fcd34d] hover:-translate-y-0.5 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#fbbf24] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a192f] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transform-none motion-reduce:transition-none`.
  Minimum hit area 44×44 px (`py-3`).
- Secondary/destructive buttons keep semantic colors (logout stays red-toned) but use the same geometry
  and rounded-xl shape.
- Links on white cards: `font-medium text-[#0a192f] underline decoration-[#fbbf24] underline-offset-4`
  with a yellow focus ring. Links on navy: yellow text.

### 10.5 Error and status messages

- Error alert inside the white card, above the form:
  `role="alert" aria-live="assertive" class="mb-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"`,
  with a red warning icon (`aria-hidden`) and `break-words` text.
- Success/status messages use emerald tones and `role="status" aria-live="polite"`.
- Invalid controls get `aria-invalid="true"` and `aria-describedby` pointing at the alert/field error.
- Failed submissions preserve every non-secret field. Password and admin code are **never** re-filled.
- Jinja autoescaping stays on. `|safe` is forbidden for user-provided values.

## 11. Page specifications

### 11.1 Landing — `GET /auth/register`

- One `h1`: «ثبت‌نام در باربر هوشمند».
- Subtitle: «نقش خود را انتخاب کنید و حساب کاربری بسازید.»
- Three white role cards in a responsive grid (`grid-cols-1 sm:grid-cols-3`):
  - Driver: truck icon, «راننده», short line «مدیریت بار، نوبت و بارنامه», link
    `/auth/register/driver`.
  - Shipper: box/warehouse icon, «صاحب کالا / انبار», short line «ثبت بار و مدیریت محموله‌ها», link
    `/auth/register/shipper`.
  - Admin: shield/key icon, «مدیر سیستم», short line «بررسی مدارک و مدیریت سامانه», link
    `/auth/register/admin`.
- Cards use a yellow icon tile, navy heading, muted description, and a yellow «شروع» / arrow action.
  Hover raises the card slightly; focus-visible shows a yellow ring.
- Footer: «حساب دارید؟» + link «وارد شوید» → `/auth/login`.
- No carrier card, no role `<select>`, no form on this page.

### 11.2 Driver registration — `/auth/register/driver`

- `h1`: «ثبت‌نام راننده».
- Subtitle: «اطلاعات هویتی و خودروی خود را وارد کنید.»
- Fields in the order and with the labels from §7.2.
- Submit button: «ثبت‌نام راننده».
- Footer: «حساب دارید؟ وارد شوید» → `/auth/login`; a back link «بازگشت به انتخاب نقش» →
  `/auth/register`.
- On `422`/`409`, re-render this page with the alert, field-level messages, and preserved values.

### 11.3 Shipper registration — `/auth/register/shipper`

- `h1`: «ثبت‌نام صاحب کالا / انبار».
- Subtitle: «برای ثبت و مدیریت بار، اطلاعات خود را وارد کنید.»
- Fields in the order and with the labels from §7.3.
- Submit button: «ثبت‌نام صاحب کالا».
- Same footer/back-link behavior as the driver page.

### 11.4 Admin registration — `/auth/register/admin`

- `h1`: «ثبت‌نام مدیر سیستم».
- Subtitle: «این بخش فقط با کد مدیریت قابل استفاده است.»
- Fields in the order and with the labels from §7.4.
- Submit button: «ساخت حساب مدیر».
- Footer: link «ورود مدیران» → `/auth/admin/login`; «بازگشت به انتخاب نقش» → `/auth/register`.
- A wrong code returns `401` with «کد مدیریت نادرست است.» and preserves `username` only.
- If `ADMIN_CODE` is unset, return `503` with the generic disabled message.

### 11.5 Success — `GET /auth/register/success?role=...`

- White card, yellow/emerald success icon, one `h1`: «ثبت‌نام با موفقیت انجام شد.»
- Role-specific body:
  - Driver: «حساب راننده ساخته شد. برای مشاهده بارها وارد شوید.»
  - Shipper: «حساب صاحب کالا ساخته شد. برای ثبت بار وارد شوید.»
  - Admin: «حساب مدیر ساخته شد. از صفحه ورود مدیران وارد شوید.»
- Primary button:
  - Driver/shipper: «ورود به حساب» → `/auth/login`.
  - Admin: «ورود مدیران» → `/auth/admin/login`.
- Secondary link: «بازگشت به انتخاب نقش» → `/auth/register`. Do not link to `/`; the app currently has
  no root route.
- No phone, national ID, username, or other account data is displayed.
- Unknown/missing `role` → `404`.

### 11.6 User login — `/auth/login`

- `h1`: «ورود».
- Subtitle: «برای مدیریت بار و نوبت‌ها وارد شوید.»
- Fields from §7.5 (phone, password).
- Submit button: «ورود».
- Footer links:
  - «حساب ندارید؟ ثبت‌نام کنید» → `/auth/register`.
  - «ورود مدیران» → `/auth/admin/login` (visually secondary).
- Wrong credentials → `401`, styled alert, phone preserved, password not echoed, no `Set-Cookie`.
- Admin credentials on this page → the same `401`; do not reveal the role.

### 11.7 Admin login — `/auth/admin/login`

- `h1`: «ورود مدیران».
- Subtitle: «این صفحه مخصوص مدیران سیستم است.»
- Fields from §7.5 (username, password, admin_code).
- Submit button: «ورود به پنل مدیریت».
- Footer: «بازگشت به ورود کاربران» → `/auth/login`.
- Wrong username/password/code or a non-admin account → `401`, generic alert, username preserved,
  password/admin code not echoed, no cookie.
- `ADMIN_CODE` unset → `503`, generic disabled page.
- Successful login → `303` `/dashboard` + cookie.

## 12. Error messages

| Condition | Status | Persian message |
|---|---|---|
| Missing/invalid `full_name` | 422 | «نام و نام خانوادگی را وارد کنید.» |
| Invalid `phone` | 422 | «شماره تلفن معتبر نیست.» |
| Invalid `national_id` | 422 | «کد ملی معتبر نیست.» |
| Invalid `license_number` | 422 | «شماره گواهینامه معتبر نیست.» |
| Missing/invalid `truck_type` | 422 | «نوع خودرو را انتخاب کنید.» |
| Invalid `plate_number` | 422 | «شماره پلاک معتبر نیست.» |
| Missing/invalid `cargo_type_preference` | 422 | «نوع بار را انتخاب کنید.» |
| Password too short / too long | 422 | «رمز عبور باید بین ۸ تا ۷۲ کاراکتر باشد.» |
| Invalid `username` | 422 | «نام کاربری معتبر نیست (۳ تا ۵۰ کاراکتر، حروف کوچک انگلیسی، عدد، نقطه، خط تیره).» |
| Duplicate phone | 409 | «این شماره تلفن قبلاً ثبت شده است.» |
| Duplicate national ID | 409 | «این کد ملی قبلاً ثبت شده است.» |
| Duplicate license number | 409 | «این شماره گواهینامه قبلاً ثبت شده است.» |
| Duplicate username | 409 | «این نام کاربری قبلاً ثبت شده است.» |
| Wrong user credentials | 401 | «شماره تلفن یا رمز عبور نادرست است.» |
| Wrong admin credentials/code | 401 | «نام کاربری، رمز عبور یا کد مدیریت نادرست است.» |
| Admin code not configured | 503 | «ورود مدیران در حال حاضر فعال نیست.» |
| Unexpected server error | 500 | «خطایی رخ داد. لطفاً دوباره تلاش کنید.» (if a handler is added; not required by this spec) |

- Login messages are deliberately generic; do not enumerate accounts or roles.
- Registration duplicate messages may name the conflicting field because the user just supplied it.
- Field-level messages may be shown next to the control in addition to the top alert.

## 13. Accessibility

- One `h1` per page; `<main>` landmark; logical heading order.
- Every control has a programmatic `<label for>`; no placeholder-only labels.
- `aria-invalid="true"` on failed controls and `aria-describedby` linking to the error text.
- Error alert: `role="alert"` + `aria-live="assertive"`; success/status: `role="status"` +
  `aria-live="polite"`.
- Visible focus for every interactive element; yellow ring on white cards, yellow/white ring on navy.
- Keyboard order follows the visual field order; Enter submits; no traps.
- Contrast: navy/white and navy/yellow meet WCAG AA for the used sizes. Muted text is not the only
  carrier of meaning.
- `prefers-reduced-motion`: transitions and hover transforms disabled.
- Pages remain usable at 200% zoom and with JavaScript disabled.
- Icons are decorative (`aria-hidden="true"`); the truck logo has an accessible brand name via text.

## 14. Responsive behavior

- Mobile-first; minimum supported width 320 px.
- Form cards `w-full max-w-md`; landing `w-full max-w-5xl`; dashboard/existing wide pages `max-w-6xl`.
- Page padding `px-4 py-8` → `sm:py-12`; card padding `p-6` → `sm:p-8`.
- Landing grid stacks on mobile and becomes three columns at `sm`.
- No horizontal scroll at 320, 360, 390, 768, 1024, 1440 px. Long Persian strings wrap
  (`break-words`), and LTR numeric fields do not overflow.
- Inputs are at least 16 px (`text-base`) to prevent iOS zoom-on-focus.
- Header brand and action remain on one line at 320 px; if needed, hide the action text and keep the
  brand.

## 15. Security and privacy

- Passwords are bcrypt-hashed; plaintext is never stored, logged, or rendered. Password/admin-code
  fields are never re-populated on error.
- Admin code is an environment secret; constant-time comparison; never stored in the DB, JWT, HTML, or
  logs.
- National ID, license number, and plate number are sensitive PII. They are rendered only in the user's
  own registration form (and preserved on that form's error). They must not appear on the dashboard,
  public pages, admin document list, or logs.
- Jinja autoescaping stays on; `|safe` is forbidden for user input.
- Cookie remains `HttpOnly`, `SameSite=Lax`; `Secure` belongs to the production deployment config.
- Login and admin-login failures do not reveal whether an account exists or what role it has.
- Duplicate registration is protected by database unique indexes and `IntegrityError` handling, not only
  by a pre-check query.
- CSRF tokens and rate limiting are existing gaps; this spec does not add them. Admin code adds
  sensitivity, so they remain high-priority follow-ups.

## 16. Compatibility and data migration

- New `users` columns are nullable, so existing rows and existing tests that insert users directly keep
  working.
- `users.phone` becomes nullable. Existing drivers/shippers keep their phone and can log in as before.
- New required registration fields apply only to new registrations; existing accounts are not forced to
  complete them.
- Existing admin rows with a phone and no username can use the admin login phone fallback (ADR 007 §5).
- The legacy `POST /auth/register` is removed; `GET /auth/register` becomes the landing page. Update all
  tests, docs, and links that assume the old single form.
- Carrier self-registration is removed from the UI; carrier accounts keep working on `/auth/login`.
- The migration is additive and deploys before the app. Downgrade sets `phone NOT NULL` and therefore
  fails if v2 admins with `NULL` phone exist; document and test on a scratch database.
- The shared `base.html` change affects every page that extends it. Regression must cover dashboard,
  cargo list/create, driver documents, admin documents, and the 403 page.

## 17. Test-suite impact (summary; details in the PLAN)

The new required fields and routes break the current auth tests. The plan must update:

- `tests/test_auth.py` — the `_register` helper, registration endpoints/fields, admin login, and all
  success/failure cases.
- `tests/test_ui_templates.py` — remove the old single-form markup tests; keep/update the shared-shell
  and dashboard tests for the new brand and palette.
- New `tests/test_registration_ui.py` — landing, role forms, login, admin login, success, error states.
- New `tests/test_registration_concurrency.py` — PostgreSQL-gated duplicate-registration race.
- `tests/support.py` — valid numeric phones, national-ID/license generators, registration/login helpers.
- Any test that logs in as an admin must switch from `/auth/login` to `/auth/admin/login` with the admin
  code (notably `test_dashboard_role_identity[admin]`).
- Tests that insert `User` directly remain valid because the new columns are nullable, but helpers used
  for login must generate valid phones/usernames.
- No existing assertion may be silently weakened; changes must be documented in the PLAN.

## 18. Out of scope / follow-ups

- CSRF tokens for auth forms, especially the admin code form.
- Login/admin-login rate limiting, account lockout, and audit logging of admin sign-ins.
- Password reset, OTP/SMS verification, email verification, captcha.
- Per-admin codes, admin invitations, admin user management, and an admin audit trail.
- Company/legal-entity registration (`company_id`, 11-digit legal ID).
- Profile-completion flow for existing drivers/shippers with missing new fields.
- Tailwind build pipeline and CSP hardening (Play CDN remains).
- A real raster/vector brand asset if the inline truck SVG is replaced by a designed logo.
- RTL-specific visual QA with real Persian content and long names.

## 19. Acceptance criteria

- **AC-1** `GET /auth/register` returns `200` with the navy header, white truck SVG, «باربر هوشمند», and
  exactly three role links to `/auth/register/driver`, `/auth/register/shipper`,
  `/auth/register/admin`; no carrier link and no role `<select>`.
- **AC-2** The driver form contains exactly `full_name`, `phone`, `national_id`, `license_number`,
  `truck_type`, `plate_number`, `password` in that order, with matching `<label for>`, `required`, and
  right-aligned icons; the password has no `value`.
- **AC-3** The shipper form contains exactly `full_name`, `phone`, `cargo_type_preference`,
  `national_id`, `password` in that order, with matching labels and required attributes.
- **AC-4** The admin form contains exactly `username`, `password`, `admin_code`, with
  `admin_code` as `type="password"`, and no phone field.
- **AC-5** The user login form contains only `phone` and `password`, plus a link to
  `/auth/admin/login`; it has no admin-code field.
- **AC-6** The admin login form contains `username`, `password`, `admin_code`, plus a link back to
  `/auth/login`; it has no phone field.
- **AC-7** A successful driver/shipper/admin registration returns `303` to
  `/auth/register/success?role=<role>`; the success page renders the role-specific message and the
  correct login link. An unknown `role` returns `404`.
- **AC-8** Driver registration persists the normalized phone, national ID, license number, truck type,
  plate number, role `driver`, `name` from `full_name`, and a bcrypt hash; the plaintext password is
  never stored.
- **AC-9** Shipper registration persists the normalized phone, national ID, cargo preference, role
  `shipper`, `name` from `full_name`, and a bcrypt hash.
- **AC-10** Admin registration with the correct `ADMIN_CODE` creates an admin with a lowercase
  username, `name = username`, `phone = NULL`, and a bcrypt hash. A wrong code returns `401` and creates
  no row. An unset code returns `503`.
- **AC-11** Duplicate phone, national ID, license number, or username returns `409` with a styled alert
  and exactly one row remains; concurrent duplicate requests on PostgreSQL produce one success and one
  `409`, never a `500`.
- **AC-12** Missing or invalid fields return `422` with an HTML form (not JSON), field/alert messages,
  `aria-invalid`, preserved non-secret values, and no password/admin-code echo.
- **AC-13** Driver/shipper/carrier login with correct credentials returns `303` to `/dashboard` and sets
  an HttpOnly `access_token` cookie; wrong password or unknown phone returns `401` with no cookie.
- **AC-14** Admin login with correct username/password/code returns `303` to `/dashboard` and sets the
  cookie; wrong password, wrong code, unknown username, or a non-admin account returns `401` with no
  cookie. An admin on `/auth/login` also gets `401` and no cookie.
- **AC-15** Auth pages and the shared shell use `#0a192f` navy, `#fbbf24` yellow, white cards,
  Vazirmatn, and the pinned Tailwind CDN `3.4.17`; no violet/pink auth gradients remain; there is
  exactly one external `<script src>`.
- **AC-16** The header is navy, contains a white truck logo and «باربر هوشمند», and appears on auth,
  success, dashboard, and existing pages that extend `base.html`.
- **AC-17** Forms are white rounded cards with right-aligned input icons and yellow primary buttons with
  black/near-black text; focus rings are visible and controls meet the 44 px target.
- **AC-18** Pages are `lang="fa" dir="rtl"`, use Persian labels, and have no horizontal scroll at 320,
  360, 390, 768, 1024, and 1440 px.
- **AC-19** Accessibility checks pass: one `h1`, labels for every control, visible focus, `role="alert"`
  for errors, logical tab order, AA contrast, reduced-motion support, and JS-disabled usability.
- **AC-20** Security/privacy checks pass: no password/admin-code echo, no admin code in DB/JWT/logs, no
  national ID/license/plate on non-form pages or logs, Jinja autoescaping, and no `|safe` on user input.
- **AC-21** Dashboard, `/cargos`, `/shipper/cargos`, `/shipper/cargos/new`, `/driver/documents`,
  `/admin/documents`, and the 403 page rendered by the domain error handler still render under the new
  shell; dashboard brand/greeting and role badges are correct.
- **AC-22** The new Alembic revision adds the columns/indexes from ADR 007, makes `phone` nullable, and
  passes `upgrade head` → `alembic check` → `downgrade -1` → `upgrade head` on a scratch PostgreSQL
  database; the dev SQLite database is migrated.
- **AC-23** The full PostgreSQL suite is green, the SQLite run has no failures (PostgreSQL-only modules
  skip), and the new tests cover every route, field, error path, and the duplicate-registration race.
- **AC-24** `docs/SPEC-registration-v2.md`, `docs/PLAN-registration-v2.md`, and ADR 007 are approved;
  `docs/SPEC-auth.md` and `docs/SPEC-ui.md` carry a one-line supersession note for the auth pages.

## 20. Decisions requiring approval

| ID | Decision | Proposed default |
|---|---|---|
| D1 | Landing route and role set | `GET /auth/register` is the landing page; Driver, Shipper, Admin only; carrier registration retired. |
| D2 | Full-name storage | Form field `full_name` maps to existing `users.name`; no redundant column. |
| D3 | Shipper legal ID | Use `national_id` for shippers; no `company_id` in v2. |
| D4 | Admin code | `ADMIN_CODE` env secret, required on admin registration **and** admin login; `503` when unset. |
| D5 | Admin login compatibility | Username first; legacy admins may fall back to phone; non-admins/admins on the wrong login get generic `401`. |
| D6 | Registration success | `303` → `/auth/register/success?role=...`; success page is a GET. |
| D7 | Status codes | `422` validation, `409` duplicates, `401` credentials/code, `503` admin disabled. |
| D8 | Normalization/uniqueness | Canonical `+989...` phone, 10-digit checksum national ID, lowercase username, DB unique indexes. |
| D9 | Shared shell/brand | New navy/yellow/white `base.html`; brand «باربر هوشمند»; inline truck SVG; existing pages inherit the shell. |
| D10 | Carrier login | Carrier role remains and may use `/auth/login`; only registration is retired. |

Approval of this SPEC means approval of D1–D10. Any change to a route, field name, status code, admin
code rule, or the role set requires updating this SPEC and ADR 007 before implementation.
