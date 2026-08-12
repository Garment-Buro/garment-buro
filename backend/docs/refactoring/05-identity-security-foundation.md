# Stage 5: identity persistence and security foundation

Status: complete for the bounded foundation slice

Quality score: 93/100

## Safety boundary

This stage adds the PostgreSQL identity/security domain and its tested services,
but does not route production authentication traffic to them. All current
`/api/auth/*` routes still fall through to legacy. That is deliberate:
`/api/auth/orders` still reads legacy SQLite orders, so switching user creation
before the order ownership bridge exists would break the cabinet for newly
created target-only users.

No staging or production database was changed.

## Delivered

- Alembic revision `20260811_0004` with normalized `users`, `roles`,
  `permissions`, assignments, OTP challenges, refresh sessions, security audit,
  and identity migration runs;
- typed SQLAlchemy 2.0 models and deterministic constraints/indexes;
- system `customer`, `manager`, and `admin` roles with explicit permissions;
- legacy-compatible four-digit OTP generation, with only a salted and
  separately peppered HMAC-SHA256 digest stored;
- OTP expiry, 60-second resend interval, per-email/per-IP hourly limits, five
  durable verification attempts, and challenge invalidation;
- IP/client values stored only as keyed digests in the security domain;
- 15-minute signed access tokens with explicit access type, session ID, issue
  time, expiry, and JWT algorithm allowlist;
- opaque high-entropy refresh tokens stored only as SHA-256 digests;
- refresh rotation, family/generation tracking, logout revocation, active
  session cap, and whole-family revocation on old-token reuse;
- active-user and permission checks for future HTTP dependencies;
- audit events for OTP request/failure/expiry, login, refresh rotation/reuse,
  and logout;
- settings-backed service construction using a separate
  `IDENTITY_OTP_PEPPER`, short access lifetime, and configurable policy limits;
- a deterministic read-only legacy-user planner and guarded importer split into
  typed plan, planner, and apply-service modules;
- importer preservation of legacy IDs and profile values, normalized email
  uniqueness, customer-role assignment, PostgreSQL sequence synchronization,
  and an empty-target guard;
- legacy OTP code/expiry values are explicitly discarded rather than copied;
- migration reports contain no email addresses or profile values.

## Current source snapshot evidence

A read-only dry-run against the current developer SQLite database completed on
2026-08-11:

| Check | Result |
| --- | ---: |
| Users | 2 |
| Normalized email duplicate groups | 0 |
| Telegram ID duplicate groups | 0 |
| Legacy OTP states to discard | 0 |
| Validation errors | 0 |
| Plan fingerprint | `aece7dba5221df9eefb27eae2e26554d20e6091b2bbcf9d602f39b5bff2c357f` |

The fingerprint covers every migrated user/profile value and every warning or
error, while the rendered report exposes only counts and the fingerprint.

## Verification

- full Ruff lint and format checks: passed;
- all unit/contract/catalog/storage/database/identity tests: 71 passed;
- offline PostgreSQL Alembic upgrade through `20260811_0004`: passed;
- offline downgrade from head to base: passed;
- isolated identity migration with exact IDs/profile/customer role: passed;
- source SQLite unchanged after planning: passed;
- plaintext OTP exclusion and PII-minimized report: passed;
- case-insensitive duplicate-email rejection: passed;
- OTP HMAC context binding and constant-time digest comparison: passed;
- resend rate limit and five-attempt durability: passed;
- access/refresh separation, rotation, logout, and old-token reuse response:
  passed;
- customer permission allow/deny behavior: passed;
- local and production Compose configuration validation: passed.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Models, repository, security, service, settings factory, and migration responsibilities are separated; the HTTP boundary is intentionally deferred. |
| Security | 20/20 | No plaintext OTP/refresh token persistence, independent pepper, durable limits, short access token, rotation/reuse revocation, RBAC, and audit are covered. |
| Data safety | 19/20 | Read-only source, PII-minimized report, full fingerprint approval, empty target, preserved IDs, OTP discard, and sequence handling are implemented. |
| Compatibility | 18/20 | Four-digit UI contract and legacy IDs/profile fields are preserved, and legacy routes remain untouched; target HTTP/profile/order ownership is not switched yet. |
| Verification | 17/20 | Negative service and migration tests plus offline Alembic/Compose pass; a real PostgreSQL apply, email delivery, HTTP cookies, and browser/PWA sessions remain for the next slice. |
| Total | 93/100 | The bounded foundation exceeds the required threshold without claiming auth cutover. |

## Rollback

There is no runtime switch to roll back in this slice. Revision `0004` can be
downgraded to `0003` only while no target identity data is needed. After an
identity import, retain the target for diagnosis and keep the source SQLite
unchanged; do not downgrade or delete either side during rehearsal.

## Required before auth cutover

1. Add feature-flagged auth/profile routes with the exact current response
   fields and generic error behavior, and enqueue OTP through the completed
   encrypted outbox in the same transaction as the challenge.
2. Put refresh tokens in a Secure, HttpOnly, SameSite cookie compatible with
   both the web app and installed PWA; add CSRF protection where required.
3. Implement the order ownership bridge before routing `/api/auth/orders`.
4. Add profile update/email-change/delete flows and ownership-negative tests.
5. Add access-session lookup and permission dependencies, then protect catalog
   writes and admin routes.
6. Rehearse Alembic/import/login/refresh/logout on real isolated PostgreSQL and
   verify email plus browser/PWA behavior before production.
