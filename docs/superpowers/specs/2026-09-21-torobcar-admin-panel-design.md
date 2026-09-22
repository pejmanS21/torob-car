# Torobcar — Admin Panel (Spec 5)

**Date:** 2026-09-21 · **Branch:** `feat/admin-panel` (off `feat/accounts-auth`) · **Status:** awaiting review

**Depends on Spec 4** (`2026-09-20-torobcar-accounts-auth-design.md`), which is open as PR #2 and
supplies `require_admin`, `users.token_version`, the `UserRole` enum and the cookie/JWT machinery
this spec extends. Nothing here can land before that merges.

## 1. Goal and scope

Give the operator full control of the platform from a web UI: manage accounts, moderate crawled
listings, correct the vehicle catalog, run ingests, and see who changed what.

**In this spec**

- A guarded `/api/v1/admin` API and an `/admin` section of the Next.js app.
- A real `/login` page with `?next=` redirect, and the «پنل مدیریت» header link — both deferred by Spec 4.
- User administration: search, disable/enable, promote/demote, reset password, delete.
- Listing moderation that survives re-ingest.
- Vehicle-catalog editing with forced cache invalidation.
- CSV ingest triggered from the UI, backed by a durable job queue.
- An append-only audit trail of every admin mutation.
- Admin-session hardening: a freshness claim plus re-authentication for destructive actions.

**Out of scope:** generic metadata-driven CRUD over every table; editing individual listing fields
(moderation is a decision about an ad, not a correction to it); email delivery of any kind; staff
roles or per-model permissions — `UserRole` stays `user` / `admin`.

## 2. Decisions taken during brainstorming

| Question | Decision |
|---|---|
| Scope | Everything: foundation, users, content, operations |
| Ingest jobs | A job table in Postgres with an in-process worker (no second Redis, no new dependency) |
| Listing moderation | A separate table keyed by the crawl `token`, so it survives re-ingest and delete-and-recreate |
| Audit | Every admin mutation, written in the same transaction as the change |
| Hardening | Short admin window + re-auth on destructive actions |
| Catalog | Editable, and every write bumps the cache `data_version` |
| API shape | A dedicated `/api/v1/admin` router, not role-gated fields on existing endpoints |

## 3. Privilege boundary and the admin session

### 3.1 The `auth_at` claim

Tokens gain one claim: `auth_at`, the unix second at which the user last entered their password.

- `authenticate` sets it to now.
- **`refresh` copies it through unchanged** — a silently refreshing session never renews admin
  freshness. This is the whole point of the claim; without it a 30-day refresh cookie would keep
  admin access alive indefinitely.
- `POST /api/v1/auth/reauth` verifies the current password and re-mints the pair with a fresh
  `auth_at`. It does **not** bump `token_version`, so other devices stay signed in.

`core/security.py` gains the field on `TokenClaims` and threads it through `encode_token` /
`decode_token` / `issue_token_pair`. A token minted before this change has no `auth_at`; `decode_token`
treats a missing claim as `0`, which fails both windows and forces one re-authentication. That is the
correct migration behaviour and needs no token invalidation.

### 3.2 Two dependencies, two windows

| Dependency | Requires | Applied to |
|---|---|---|
| `require_admin` | role `admin`, `is_active`, and `auth_at` within `ADMIN_SESSION_MINUTES` (60) | the whole admin router |
| `require_fresh_admin` | the same, but `auth_at` within `ADMIN_REAUTH_MINUTES` (5) | delete, disable, promote/demote, reset password |

`require_admin` is mounted as a **router-level** dependency on `/api/v1/admin`, so a newly added
endpoint is guarded by default rather than by the author remembering. It continues to read the
database on every call (Spec 4 behaviour), so demotion and disabling take effect immediately.

When the window has lapsed the API returns **403 `admin_reauth_required`** — a distinct code, so the
frontend can show a password prompt instead of the generic error banner.

### 3.3 New settings

`ADMIN_SESSION_MINUTES=60`, `ADMIN_REAUTH_MINUTES=5`, `INGEST_UPLOAD_DIR=/data/ingest`,
`INGEST_MAX_UPLOAD_MB=50`. All added to `example.env` and `core/config.py`.

## 4. Data model

**One migration per phase**, not one for the spec — the phases in §12 are independently
shippable, so their schema must be too: `0004` creates `admin_audit` (phase 1), `0005`
`listing_moderation` (phase 2), `0006` `ingest_jobs` (phase 3). All tables use the existing
`UUIDPrimaryKeyMixin` (UUIDv8, app-side).

| Table | Columns |
|---|---|
| `admin_audit` | `actor_id` → `users.id` **ON DELETE SET NULL**, nullable; `action` (`AdminAction` enum); `target_type` (str); `target_id` (str, nullable); `summary` (JSONB); `created_at` |
| `listing_moderation` | `token` (`String(64)`, **unique**); `is_hidden` (bool); `reason` (Text, nullable); `moderated_by` → `users.id` ON DELETE SET NULL, nullable; `created_at`; `updated_at` |
| `ingest_jobs` | `status` (`IngestJobStatus` enum: `pending`/`running`/`succeeded`/`failed`, indexed); `csv_path` (Text); `original_filename` (Text); `requested_by` → `users.id` ON DELETE SET NULL, nullable; `report` (JSONB, nullable); `error` (Text, nullable); `created_at`; `started_at`; `finished_at` (both nullable) |

New enums in `enums.py`: `AdminAction` (`user_disabled`, `user_enabled`, `user_promoted`,
`user_demoted`, `user_password_reset`, `user_deleted`, `listing_hidden`, `listing_unhidden`,
`catalog_updated`, `ingest_requested`) and `IngestJobStatus`.

**Two deliberate choices:**

- `admin_audit.actor_id` is `ON DELETE SET NULL`, never `CASCADE`. Deleting an admin must not erase
  the record of what they did. `summary` retains the actor's email so the row stays readable.
- `listing_moderation` keys on `token`, not `listing_id`. `Listing.token` is the crawl identity and is
  already unique and indexed; `ListingRepository.upsert_many` keys on it and holds `id` immutable. A
  moderation row therefore survives a re-ingest **and** a delete-and-recreate, which a column on
  `listings` would not.

## 5. Backend API

A new `api/v1/admin/` package: `router.py` plus one thin module per resource. Every module follows the
existing layering — endpoints → services → repositories, no SQLAlchemy outside `repositories/`.

| Route | Guard | Notes |
|---|---|---|
| `GET /admin/stats` | admin | counts, data freshness, recent audit. The last-ingest tile is added in phase 3, when `ingest_jobs` exists — phase 1 must not ship a tile with no table behind it |
| `GET /admin/users` | admin | search by email, filter by role/active, paginated |
| `GET /admin/users/{id}` | admin | includes saved/alert counts |
| `PATCH /admin/users/{id}` | **fresh** | `is_active` and/or `role` |
| `POST /admin/users/{id}/password` | **fresh** | sets a new password, bumps that user's `token_version` |
| `DELETE /admin/users/{id}` | **fresh** | cascades saved listings and alerts |
| `GET /admin/listings` | admin | search, with moderation state joined |
| `PUT /admin/listings/{token}/moderation` | admin | hide with a reason (idempotent) |
| `DELETE /admin/listings/{token}/moderation` | admin | unhide (idempotent) |
| `GET /admin/catalog` | admin | rows with listing counts |
| `PATCH /admin/catalog/{id}` | admin | edit brand/model/trim; bumps cache `data_version` |
| `POST /admin/ingest/uploads` | admin | multipart CSV → stored file |
| `POST /admin/ingest/jobs` | admin | enqueue a job for an uploaded file |
| `GET /admin/ingest/jobs` · `GET /admin/ingest/jobs/{id}` | admin | history and per-run report |
| `GET /admin/audit` | admin | append-only, filter by actor/action/target |
| `POST /api/v1/auth/reauth` | authenticated | **not** under `/admin`: re-mints with a fresh `auth_at` |

### 5.1 Lockout guards

Both return **409** and are enforced in the service, not the endpoint:

- `cannot_modify_self` — an admin may not disable, demote or delete their own account.
- `last_admin` — the last remaining **active** admin may not be disabled, demoted or deleted. The check
  and the write occur in one transaction (`SELECT … FOR UPDATE` over active admins) so two concurrent
  demotions cannot both pass.

Without these, one click locks every human out of the panel permanently: Spec 4's bootstrap only
creates the admin when the email is **absent**, so it cannot rescue a disabled or demoted row.

### 5.2 Audit writes

Every mutating admin service method appends an `admin_audit` row **inside the same transaction** as the
change, via a small `AuditRecorder` collaborator injected into each admin service. If the change rolls
back, so does its audit row; there is no path that writes one without the other, and no update or
delete path for the table at all.

### 5.3 New errors

`AdminReauthRequiredError` (403 `admin_reauth_required`), `CannotModifySelfError` (409
`cannot_modify_self`), `LastAdminError` (409 `last_admin`), `IngestUploadRejectedError` (422
`ingest_upload_rejected`), `IngestJobNotFoundError` (404 `ingest_job_not_found`).

## 6. Hiding listings from the public API

`listing_moderation` joins to `listings` on `token`. Every public read path must exclude hidden rows:
**`/search`, `/facets`, `/estimates`, `/listings`, `/listings/{id}`, `/listings/{id}/similar`, the model
stats, and the assistant's tool queries.** A hidden ad that still surfaces in results — or still counts
toward a facet — is the failure this table exists to prevent.

The exclusion lives in `ListingRepository` as one private condition applied by the shared candidate
query builder, so a future query inherits it rather than re-implementing it. `ranking/` is pure and
unaffected.

This is the **highest-risk edit in the spec**: it touches the hot search path. The golden-query suite in
`tests/api/test_search_api.py` is the guard and must stay green, and the verdict thresholds remain the
`CHEAP_DIFF_PCT` / `EXPENSIVE_DIFF_PCT` constants in `ranking/weights.py`.

## 7. The ingest worker

A single asyncio task started from `lifespan`, alongside the existing admin bootstrap.

- **Claiming:** `SELECT … WHERE status='pending' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1`.
  One job at a time — the pipeline does bulk upserts and a cache invalidation, and interleaving two
  would corrupt both. `SKIP LOCKED` means a second container can be added later without double-running.
- **Crash recovery:** on boot, every job still marked `running` is reset to `pending`; the process that
  owned it is gone. This is why the queue is in Postgres and not in memory.
- **Execution:** runs the existing `IngestPipeline` unchanged. On success it stores the existing
  `IngestReport` in `report` and bumps the cache `data_version`; on failure it stores the exception text
  in `error` and the pipeline's own transaction leaves the data untouched.
- **Uploads:** multipart to `INGEST_UPLOAD_DIR` on a named Docker volume. The stored name is
  server-generated (`uuid4().hex + ".csv"`); the client filename is kept only as a display label and
  **never** used to build a path. Rejected over `INGEST_MAX_UPLOAD_MB` or without a CSV content type.

## 8. Frontend

`/login` is public; everything under `/admin` is guarded. All are Client Components calling
`/api/v1/admin` — Server Components stay anonymous, so no admin data is fetched during prerender.

| Route | Contents |
|---|---|
| `/login` | email + password, honours `?next=`, redirects back on success |
| `/admin` | counts, data freshness, recent audit; last ingest from phase 3 |
| `/admin/users`, `/admin/users/[id]` | search; disable/enable, promote/demote, reset password, delete |
| `/admin/listings` | search; hide/unhide with a reason |
| `/admin/catalog` | brand/model/trim with listing counts; edit |
| `/admin/ingest` | upload, job list, job detail + report |
| `/admin/audit` | append-only, filterable |

`/admin` redirects to `/login?next=…` when `GET /me` says anonymous, and renders «دسترسی ندارید» when
the user is real but not an admin. The header menu shows «پنل مدیریت» only when `user.role === "admin"`.

A shared `ReauthPrompt` component catches `admin_reauth_required`, collects the password, calls
`/auth/reauth` and retries the original action once. Error copy is keyed by `ApiError.code` in
`lib/admin.ts`, never by message text, matching `AUTH_ERROR_TEXT`. The admin UI is Persian and RTL like
the rest of the app.

## 9. Testing

| Area | Proves |
|---|---|
| `tests/core/test_security.py` (extend) | `auth_at` round-trips; a missing claim decodes as `0`; `refresh` preserves it while `authenticate` and `reauth` reset it |
| `tests/repositories/test_admin_*.py` | audit is append-only; moderation upsert is idempotent per token; job claiming under `SKIP LOCKED` hands one job to one caller |
| `tests/services/test_admin_*.py` | both lockout guards, including the concurrent-demotion case; audit written on success and absent on failure; catalog edit bumps `data_version` |
| `tests/api/test_admin_api.py` | a non-admin gets 403 on **every** admin route, parametrised over `admin.router.routes` so a new route cannot skip the guard; a stale `auth_at` yields `admin_reauth_required`; `/auth/reauth` restores access |
| `tests/api/test_search_api.py` (extend) | a hidden listing disappears from `/search`, `/facets` and `/estimates` — and **the golden queries stay green** |
| `tests/services/test_ingest_worker.py` | a job stuck in `running` is requeued on boot; a failed job records the error and leaves data untouched |
| frontend `bun test` | reauth-retry logic and admin error-code copy, as pure helpers in `lib/admin.ts` |

## 10. Security checklist

- [ ] `require_admin` is a router-level dependency; the parametrised test proves no route escapes it.
- [ ] Destructive routes additionally require `require_fresh_admin`.
- [ ] `refresh` does not renew `auth_at`; only a real password entry does.
- [ ] Both lockout guards enforced transactionally.
- [ ] Every admin mutation writes an audit row in the same transaction; the table has no update or delete path.
- [ ] Uploads: size cap, content-type check, server-generated filename, no client string in any path.
- [ ] Hidden listings are absent from every public read path, verified per endpoint.
- [ ] Admin responses never include `password_hash`; `UserRead` remains the only user schema leaving the API.
- [ ] No secret, password or token is logged; reset passwords are `SecretStr`.
- [ ] No CORS middleware is added; `SameSite=Lax` plus JSON-only mutations remains the CSRF defence. The
      one multipart endpoint is `POST`-only and admin-guarded.

## 11. Known ceilings

Each gets a `ponytail:` comment naming the upgrade path.

| Ceiling | Upgrade path |
|---|---|
| Ingest progress is coarse: `pending` → `running` → terminal plus the final report | Thread a progress callback through `IngestPipeline` |
| One in-process worker; a job only starts when the API container is up | The `SKIP LOCKED` claim already allows a separate worker container |
| Uploaded CSVs are never garbage-collected | A retention sweep once disk actually matters |
| Audit has no retention policy or export | Partition or archive when the table grows |
| `AdminAction` is a closed enum; a new action needs a code change | Intentional — it keeps the vocabulary reviewable |

## 12. Phasing

Three independently shippable phases; the implementation plan sequences them.

1. **Foundation + users** — `auth_at`, both dependencies, `/auth/reauth`, the admin router, audit table, user administration, `/login`, the `/admin` shell.
2. **Content** — `listing_moderation`, exclusion across every public read path, catalog editing with cache invalidation.
3. **Operations** — `ingest_jobs`, the worker, upload endpoint, the ingest screens, the
   dashboard's last-ingest tile, and the dedicated `/admin/audit` screen. Note the audit
   *table* and its `GET /admin/audit` endpoint land in phase 1, because user administration
   writes audit rows from its first commit; phase 3 only adds the browsing UI.

Definition of done is CLAUDE.md §14 in full, for each phase.
