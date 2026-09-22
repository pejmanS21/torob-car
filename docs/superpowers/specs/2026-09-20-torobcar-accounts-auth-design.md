# Torobcar — Accounts and Authentication (Spec 4)

**Date:** 2026-09-20 · **Branch:** `feat/accounts-auth` (off `main`) · **Status:** awaiting review

## 1. Goal and scope

Give Torobcar real user accounts. Today the frontend fakes login: `AppState.tsx` keeps a
`loggedIn` boolean in `localStorage` and `toggleLogin()` flips it. The backend has no
users, no auth, and no `core/security.py`.

**In this spec**

- Backend: `users`, `saved_listings` and `price_alerts` tables; register, login, refresh,
  logout and change-password endpoints; `/me` endpoints for saved listings and price
  alerts; an admin account created at startup from environment variables.
- Frontend: a login/sign-up dialog replacing the fake toggle; saved listings and price
  alerts stored server-side for logged-in users, with a one-time upload of whatever was
  in `localStorage`.
- The two hooks the admin panel will need: a `require_admin` dependency and
  `users.token_version`.

**Out of scope (Spec 5 — admin panel):** the admin UI and its CRUD endpoints, a standalone
`/login` page with redirect, the «پنل مدیریت» menu link, and user management (disable,
promote, reset password).

**Out of scope (no provider yet):** email verification and password reset by email.

## 2. Decisions taken during brainstorming

| Question | Decision |
|---|---|
| Decomposition | Two specs: accounts/auth (this one), then the admin panel |
| Identity | Email + password |
| Account data | Saved listings and price alerts move server-side; compare stays in `localStorage` |
| Roles | `user` and `admin` — one enum column, no staff tier, no per-model permissions |
| Admin bootstrap | `ADMIN_EMAIL` + `ADMIN_PASSWORD`, created on boot if absent, never overwritten |
| Session mechanism | Stateless JWT in cookies (chosen over a Postgres session table and `fastapi-users`) |
| Password hashing | Stdlib `hashlib.scrypt` — no new dependency |
| Change-password UI | Not in v1; the endpoint ships, the form does not |

## 3. Data model

One Alembic migration. All three tables use `UUIDPrimaryKeyMixin`.

| Table | Columns |
|---|---|
| `users` | `email` (`String(320)`, unique, stored lowercased), `password_hash` (`Text`), `role` (`UserRole` enum: `user` / `admin`, default `user`), `is_active` (bool, default true), `token_version` (int, default 0), `created_at`, `last_login_at` (nullable) |
| `saved_listings` | `user_id` → `users.id` (on delete cascade), `listing_id` → `listings.id` (on delete cascade), `created_at`; unique on `(user_id, listing_id)` |
| `price_alerts` | `user_id` → `users.id` (on delete cascade, indexed), `title` (`Text`), `threshold` (`BigInteger`), `params` (`JSONB`), `created_at` |

`UserRole` lives in `enums.py` and is mapped with the existing `enum_type` helper.

Listing ids are stable across re-ingests — `ListingRepository.upsert_many` keys on `token`
and `id` is in `_IMMUTABLE_COLUMNS` — so `saved_listings.listing_id` is a plain foreign key.

`price_alerts` mirrors the frontend's existing `PriceAlert {title, params, threshold}`.
`params` is stored as the opaque search-parameter object the frontend sent; the backend
validates that it is a JSON object and does not interpret it.

Email normalisation is `email.strip().lower()`, applied in the `UserCreate` and
`LoginRequest` schemas so every layer below sees one form.

## 4. Tokens and passwords (`core/security.py`)

Pure functions, no I/O: `hash_password`, `verify_password`, `encode_token`, `decode_token`.

### 4.1 Tokens

HS256 via **PyJWT** (the one new dependency — a hand-rolled JWT is a security bug waiting
to happen). The key is `Settings.jwt_secret` (`SecretStr`). `decode_token` pins
`algorithms=["HS256"]`.

| Cookie | JWT `exp` | Cookie `Max-Age` | `Path` | Claims |
|---|---|---|---|---|
| `access_token` | `ACCESS_TOKEN_MINUTES` (15) | `REFRESH_TOKEN_DAYS` (30) | `/` | `sub`, `role`, `ver`, `exp`, `typ=access` |
| `refresh_token` | `REFRESH_TOKEN_DAYS` (30) | `REFRESH_TOKEN_DAYS` (30) | `/api/v1/auth` | `sub`, `ver`, `exp`, `typ=refresh` |

Both cookies are `HttpOnly; SameSite=Lax`, and `Secure` when `ENV != development`.

The access **cookie** deliberately outlives the access **token**. If the browser dropped
the cookie after 15 minutes, the backend would see no cookie and answer
`not_authenticated`, and the frontend would never know to refresh. Keeping the cookie
means an expired token is still sent, the backend answers `token_expired`, and the client
refreshes. Anonymous visitors have no cookie, get `not_authenticated`, and never call
`/auth/refresh`. Only the JWT `exp` claim decides validity.
`decode_token` takes the expected `typ` and rejects the other kind.

### 4.2 Revocation without a blocklist

`ver` is a copy of `users.token_version`. `POST /auth/refresh` loads the user and rejects
the request when `is_active` is false or `ver` does not match. Disable-user,
change-password and logout-everywhere each bump `token_version`, which locks the user out
within one access-token lifetime at most. No table is consulted on ordinary requests.

`require_admin` always loads the user from the database, so disabling or demoting an admin
takes effect immediately.

### 4.3 Passwords

`hashlib.scrypt` with `n=2**17, r=8, p=1`, a 16-byte salt per user, run inside
`asyncio.to_thread` so it never blocks the event loop. Stored as
`scrypt$n$r$p$salt_b64$hash_b64` so the cost can be raised later without invalidating old
hashes. `n` comes from `Settings.scrypt_n`; test settings use `2**4`.

Password length: minimum 8, maximum 128. The maximum stops an attacker from sending huge
passwords to tie up the hasher. Password fields are `SecretStr` in every schema.

### 4.4 Settings

New keys in `core/config.py` and `example.env`:

| Key | Default | Notes |
|---|---|---|
| `JWT_SECRET` | empty | `Settings` validation raises when empty and `ENV != development`. In development an empty value becomes a random per-process secret (`secrets.token_urlsafe`) with one warning logged — logins then reset on every restart, so `.scripts/setup.sh` writes a generated value into `.env`. No secret is ever hardcoded. |
| `ACCESS_TOKEN_MINUTES` | 15 | |
| `REFRESH_TOKEN_DAYS` | 30 | |
| `SCRYPT_N` | 131072 | |
| `ADMIN_EMAIL` | empty | |
| `ADMIN_PASSWORD` | empty | `SecretStr` |

## 5. Backend API

Two new modules under `api/v1/endpoints/`, registered in `api/v1/router.py`.

### 5.1 `auth.py` — prefix `/auth`

| Route | Body → Response | Notes |
|---|---|---|
| `POST /register` | `UserCreate {email, password}` → `201 UserRead` | Sets both cookies; sign-up also logs in |
| `POST /login` | `LoginRequest {email, password}` → `UserRead` | Sets both cookies, stamps `last_login_at` |
| `POST /refresh` | none → `UserRead` | Reads `refresh_token`, checks `is_active` and `ver`, issues a fresh pair |
| `POST /logout` | none → `204` | Clears both cookies |
| `POST /logout-all` | none → `204` | Bumps `token_version`, clears cookies. Requires a valid access token. |
| `POST /password` | `PasswordChange {current, new}` → `204` | Verifies `current`, bumps `token_version`, re-issues cookies so this device stays logged in. Requires a valid access token. |

### 5.2 `me.py` — prefix `/me`

Every route requires a valid access token.

| Route | Notes |
|---|---|
| `GET /me` | → `UserRead {id, email, role, created_at}` |
| `GET /me/saved` | → `list[UUID]` of listing ids, newest first |
| `PUT /me/saved/{listing_id}` → `204` | Idempotent (`ON CONFLICT DO NOTHING`). Unknown listing → the existing `ListingNotFoundError`. |
| `DELETE /me/saved/{listing_id}` → `204` | Idempotent; deleting an unsaved listing is not an error |
| `GET /me/alerts` | → `list[PriceAlertRead {id, title, threshold, params, created_at}]` |
| `POST /me/alerts` | `PriceAlertCreate {title, threshold, params}` → `201 PriceAlertRead` |
| `DELETE /me/alerts/{alert_id}` → `204` | Scoped by `user_id`. Another user's alert → `404 alert_not_found`, never 403, so the response does not reveal that the alert exists. |
| `POST /me/import` | `ImportRequest {saved: [UUID], alerts: [PriceAlertCreate]}` → `AccountState {saved, alerts}` | The one-shot `localStorage` upload. Saved ids that no longer exist are skipped silently. Alerts are de-duplicated on `(title, threshold, params)`. Idempotent. Limits: 500 saved ids, 50 alerts. |

### 5.3 Layering

- `core/security.py` — section 4.
- `repositories/user_repository.py`, `saved_listing_repository.py`,
  `price_alert_repository.py`.
- `services/auth_service.py` — register, authenticate, refresh, change-password,
  logout-all, `ensure_admin`. Returns `(UserRead, TokenPair)`; never touches `Response`.
  The endpoint writes cookies through one `_set_auth_cookies` helper and clears them
  through one `_clear_auth_cookies` helper.
- `services/account_service.py` — saved listings, alerts, import.
- `dependencies/providers.py` — `get_current_user` decodes the `access_token` cookie into a
  lightweight `CurrentUser(id, role)` with no database hit; `require_admin` loads the user
  from the database and checks `role` and `is_active`. `get_optional_user` is not built;
  no route needs it yet.

### 5.4 Errors

New `AppError` subclasses in `errors.py`; the existing envelope handler picks them up.

| Class | Status · code | When |
|---|---|---|
| `InvalidCredentialsError` | 401 · `invalid_credentials` | Wrong email **or** wrong password — identical message. A missing user still runs a dummy scrypt hash so timing does not reveal which accounts exist. Also raised when `current` is wrong in `POST /auth/password`. |
| `NotAuthenticatedError` | 401 · `not_authenticated` | No cookie, a malformed or tampered token, or the wrong `typ` |
| `TokenExpiredError` | 401 · `token_expired` | Distinct code so the frontend refreshes instead of prompting for login |
| `AccountDisabledError` | 403 · `account_disabled` | `is_active` is false at login or refresh |
| `PermissionDeniedError` | 403 · `permission_denied` | `require_admin` and the user is not an admin |
| `EmailAlreadyRegisteredError` | 409 · `email_taken` | Registration hits the unique constraint |
| `AlertNotFoundError` | 404 · `alert_not_found` | Alert id unknown or owned by someone else |

A stale `ver` at refresh raises `NotAuthenticatedError`.

`email_taken` reveals that an address is registered. Accepted for now: the alternative is a
"check your inbox" flow and there is no SMTP provider.

### 5.5 Admin bootstrap

`AuthService.ensure_admin(email, password)` runs in `lifespan` before `yield`, on its own
session from the existing factory, and commits.

- `ADMIN_EMAIL` or `ADMIN_PASSWORD` empty → log one line and skip.
- The email already exists → do nothing. Never rewrite the password; never promote an
  existing account.
- The insert uses `ON CONFLICT (email) DO NOTHING`, so extra workers cannot race.
- If the `users` table is missing (migrations not applied), startup fails loudly.

### 5.6 Traefik

The `api-assistant` router rule gains `|| PathPrefix(`/api/v1/auth`)`, putting auth under
the 5/s, burst-10 limit. One label edit in `.docker/compose.yml`, mirrored in CLAUDE.md
§11.3 and §11.4. `/me` stays on the default `api` router.

## 6. Frontend

### 6.1 API client (`lib/api/client.ts`)

- Add `apiPut` and `apiDelete` beside `apiPost`. `request` returns `undefined` on 204.
- **Silent refresh** inside `request`: on 401 with `code === "token_expired"`, call
  `POST /auth/refresh` once and replay the original request. A module-level in-flight
  promise is shared, so parallel 401s trigger one refresh. If the refresh fails, the
  original `ApiError` propagates. `not_authenticated` never triggers a refresh. The
  refresh call itself is never replayed.
- Cookies are same-origin, so `fetch` sends them by default. No token ever reaches
  JavaScript.

### 6.2 Server Components stay anonymous

They cannot write cookies during render, so they cannot refresh. Everything they fetch —
search, listing, model, facets — is public. All `/me` data loads client-side; SSR paths
and `base.ts` are untouched.

### 6.3 Types (`lib/api/types.ts`)

`UserRead`, `AuthRequest`, `PriceAlertRead`, `ImportRequest` and `AccountState`, mirrored by
hand from `schemas/`. `PriceAlert` in `lib/types.ts` gains `id?: string`, present once the
server has stored it.

### 6.4 State (`state/AppState.tsx`)

- `Persisted` drops `loggedIn`. `STORAGE_KEY` stays `torobcar:v2`; `readPersisted` already
  ignores unknown keys.
- New non-persisted state: `user: UserRead | null`, `authReady: boolean`, `authOpen: boolean`.
  `loggedIn` becomes the derived `user !== null`, so existing consumers keep working.
- On mount: `GET /me`. Success → set `user`, then load `GET /me/saved` and `GET /me/alerts`
  and replace local `saved` and `alerts`. `not_authenticated` → anonymous; local `saved`
  is used as today.
- `toggleLogin` is removed. In its place:
  - `login(email, password)` / `register(email, password)` — call the endpoint, then
    `POST /me/import` with the current local `saved` and `alerts`, adopt the merged
    response, toast «خوش اومدی!».
  - `logout()` — `POST /auth/logout`, set `user` to `null`, clear `saved` and `alerts` in
    memory and in storage so the next person on a shared device does not inherit them.
    `compare` is kept.
  - `openAuth()` / `closeAuth()`.
- Anonymous behaviour is unchanged: `toggleSaved` works locally; `addAlert` is blocked and
  now opens the auth dialog.
- Logged in, `toggleSaved`, `addAlert` and `removeAlert` are **optimistic**: apply through
  the existing `commitPersisted` path, fire the request, and on failure revert and toast
  «ذخیره نشد؛ دوباره امتحان کن». `addAlert` patches the server-assigned `id` onto the
  local alert when the response arrives.
- `removeAlert(index)` becomes `removeAlert(id)`; `AlertsDropdown` is the only caller.
- The pure decisions — optimistic apply/revert and "logout clears saved and alerts, keeps
  compare" — live in a new `lib/account.ts`, matching `lib/compare.ts` and its siblings.

### 6.5 UI

One new component, `AuthDialog.tsx` + CSS module, rendered once in the app shell.

- Native `<dialog>`: focus trap, Escape and backdrop with no library.
- Two tabs, «ورود» and «ثبت‌نام».
- Inputs are `type="email"` and `type="password"` with `autocomplete="email"`,
  `"current-password"` or `"new-password"`, and `minLength={8}` `maxLength={128}`.
- Inline errors chosen by `ApiError.code`:
  - `invalid_credentials` → «ایمیل یا رمز اشتباه است»
  - `email_taken` → «این ایمیل قبلاً ثبت شده؛ وارد شو», and switch to the login tab
  - `account_disabled` → «حساب غیرفعال شده»
  - status 422 → the backend's own message
  - anything else → the existing «سرویس … در دسترس نیست»
- Every «ورود» button (`Header`, `AlertsDropdown`) calls `openAuth()`.

**Header, logged in:** the badge shows the first character of the email, with the full
email in `title`. Clicking it opens a small menu with «خروج». The hardcoded «علی» goes.

**Not built:** a `/login` page, a profile or change-password page, a strength meter.

## 7. Testing

### 7.1 Backend (pytest, existing `session`, `client`, `api` fixtures)

| File | Proves |
|---|---|
| `tests/core/test_security.py` | Hash verifies; wrong password does not; two hashes of one password differ; stored parameters parse back so old hashes survive a cost bump; token round-trips; expired → `TokenExpiredError`; tampered → `NotAuthenticatedError`; refresh token rejected as access and the reverse |
| `tests/repositories/test_user_repository.py`, `test_saved_listing_repository.py`, `test_price_alert_repository.py` | Real test DB. Email uniqueness holds across case; second save is a no-op; deleting a user cascades; an alert delete scoped to another user deletes nothing |
| `tests/services/test_auth_service.py` | Repositories mocked. Unknown email and wrong password raise the same error, and the unknown-email path still calls the hasher; disabled user → `AccountDisabledError`; stale `ver` fails refresh; change-password bumps `token_version`; `ensure_admin` creates when absent, leaves an existing row alone, skips on empty vars |
| `tests/services/test_account_service.py` | Import skips vanished listing ids, de-duplicates alerts, is idempotent |
| `tests/api/test_auth_api.py`, `test_me_api.py` | Register → cookies carry `HttpOnly`, `SameSite=lax` and the right `Path` → `GET /me` → logout → 401. Duplicate email → 409 `email_taken`. Short password → 422. `/me/*` without a cookie → 401 `not_authenticated`. User B deleting user A's alert → 404. Disabled user refresh → 403. |
| `tests/core/test_config.py` (extend) | Empty `JWT_SECRET` raises under `ENV=production`; under `development` it yields a non-empty random secret |
| `tests/test_errors.py` (extend) | Each new error maps to its status and code |

### 7.2 Frontend (`bun test`)

- `lib/api/client.test.ts`: `token_expired` → exactly one refresh and one replay; parallel
  401s share one refresh; failed refresh surfaces the original error; `not_authenticated`
  does not refresh; 204 resolves to `undefined`.
- `lib/account.test.ts`: optimistic apply and revert; logout clears saved and alerts and
  keeps compare.

### 7.3 Smoke (`.scripts/smoke.sh`)

A new "account" step: register `smoke+<timestamp>@example.com`, save a listing, reload and
check it is still saved, log out and check it is gone.

## 8. Security checklist

- [ ] Passwords never logged; `SecretStr` in every schema.
- [ ] Cookies `HttpOnly`, `SameSite=Lax`, `Secure` outside development; refresh cookie
      path-scoped to `/api/v1/auth`. An expired access token with a live cookie yields
      `token_expired`, never a successful request.
- [ ] State-changing routes accept JSON only; no CORS middleware is added. With
      `SameSite=Lax` that is the whole CSRF defence.
- [ ] Credential failures are identical in body and timing.
- [ ] `/auth/*` sits behind the 5/s Traefik limit.
- [ ] `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` empty in `example.env`; Gitleaks and
      Semgrep stay clean.
- [ ] `decode_token` pins `algorithms=["HS256"]`.

## 9. Known ceilings

Each is marked in code with a `ponytail:` comment naming the upgrade path.

| Ceiling | Upgrade path |
|---|---|
| Rate limiting is per IP only; slow distributed guessing is not stopped | Per-email failure counter in Redis via the existing `Cache.incr` |
| Up to 15 minutes of revocation lag on non-admin routes | Lower `ACCESS_TOKEN_MINUTES`, or check `token_version` in Redis |
| No email verification or reset | First SMTP provider; until then admins reset passwords (Spec 5) |

## 10. Rollout order

Each step leaves the suite green.

1. `core/security.py`, settings, `PyJWT` via `uv add`; `setup.sh` generates `JWT_SECRET`.
2. `UserRole`, models, migration.
3. Repositories.
4. Services and `ensure_admin` in `lifespan`.
5. Errors, providers, endpoints, router registration.
6. Traefik label, `example.env`, CLAUDE.md §2, §4, §11.
7. Frontend client: `apiPut`, `apiDelete`, 204, silent refresh.
8. `lib/account.ts`, `AppState`, `AuthDialog`, `Header`, `AlertsDropdown`.
9. Smoke step; `graphify update .`.

Definition of done is CLAUDE.md §14 in full.
