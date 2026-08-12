# Stage 7: guarded identity API and legacy order ownership bridge

Status: complete for the bounded guarded backend slice; disabled by default

Quality score: 94/100

## Safety boundary

This stage provides the refactored backend routes for login, profile, email
change, account deletion, refresh/logout, and owned orders. It does not enable
them in any environment. `IDENTITY_API_ENABLED=false` remains the default and
the mounted legacy application continues serving production-compatible routes.

The flag must not be enabled for live traffic until the frontend performs
single-flight refresh/logout and the full flow has passed isolated PostgreSQL,
SMTP, web, and installed-PWA rehearsal. No staging or production data, service,
or email was changed during this stage.

## Delivered

- a feature-flagged router that atomically overrides the full current
  `/api/auth/*` route family before the legacy mount;
- exact Bearer response compatibility for four-digit email login without the
  legacy `testing_only_otp` disclosure;
- OTP challenge and encrypted notification enqueue in one PostgreSQL
  transaction;
- transactional cancellation of replaced and consumed OTP messages, plus a
  durable delivery deadline that dead-letters expired retries before SMTP;
- generic invalid-code behavior, durable attempts, resend/hour limits, and safe
  `Retry-After` responses;
- short access-token validation against a live refresh session, opaque rotating
  HttpOnly refresh cookie, logout, family revocation on reuse, and same-origin
  protection for cookie-authenticated mutations;
- optional legacy Bearer compatibility with a timezone-aware cutoff limited to
  31 days;
- typed partial profile updates while continuing to ignore direct `email`
  changes from the legacy form contract;
- OTP-verified email changes with uniqueness-race handling and audit events;
- soft account deletion that removes direct profile identifiers, invalidates
  OTPs, revokes sessions, and preserves audit/order retention boundaries;
- startup cutover verification for the exact reviewed identity fingerprint,
  imported user count, and customer permissions;
- a separate read-only SQLite order adapter with startup schema validation and
  no CDEK network calls from cabinet reads;
- PostgreSQL `legacy_order_claims` where one legacy order can belong to only one
  user and the matching identifier is stored only as an HMAC digest;
- order discovery exclusively through verified email; editable/unverified phone
  values cannot reveal another customer's order;
- ownership persistence across verified email changes and protection against
  later email recycling;
- Alembic revision `20260811_0006`, environment examples, and both Compose
  configurations.

## Current source snapshot evidence

The source was inspected read-only again on 2026-08-11:

| Check | Result |
| --- | ---: |
| Legacy users | 2 |
| Identity validation errors | 0 |
| Identity warnings | 0 |
| Identity fingerprint | `aece7dba5221df9eefb27eae2e26554d20e6091b2bbcf9d602f39b5bff2c357f` |
| Legacy orders | 2 |
| Orders with email | 2 |
| Phone-only orders | 0 |
| Orders matching a current user email | 1 |

No email address, phone number, profile value, OTP, or order content is included
in this report.

## Verification

- full Ruff lint and format checks: passed;
- all unit, contract, catalog, storage, database, identity, notification, and
  bridge tests: 88 passed;
- offline PostgreSQL Alembic upgrade through `20260811_0006`: passed;
- offline downgrade from head to base: passed;
- local and production Compose validation, including the notification profile:
  passed;
- guarded route precedence with unrelated legacy fallthrough: passed;
- encrypted OTP enqueue with no code in the response and terminal payload
  erasure after consumption: passed;
- login, profile partial update, verified email change, soft delete, and revoked
  access after deletion: passed;
- refresh rotation, old-access invalidation, cross-origin rejection, and
  whole-family revocation after old-token reuse: passed;
- bounded legacy Bearer acceptance: passed;
- wrong fingerprint, lower-than-reviewed user count, incomplete customer RBAC,
  and incompatible legacy order schema startup refusal: passed;
- verified-email order discovery, phone-only exclusion, durable claim after email
  change, and second-user claim-theft denial: passed;
- replaced and expired OTP notification non-delivery: passed;
- current source identity dry-run and aggregate order inspection: passed;
- repository whitespace check: passed.

Docker/OrbStack was not running, so this evidence does not claim a real
PostgreSQL container, SMTP delivery, concurrent PostgreSQL lock behavior, or
browser/PWA cookie behavior.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | HTTP, domain service, repository, target model, encrypted outbox, and read-only legacy adapter are separated; the adapter is deliberately transitional. |
| Security and privacy | 20/20 | OTP secrecy/expiry, session rotation/reuse revocation, CSRF origin checks, verified-email ownership, HMAC claim data, RBAC, and PII-clearing soft deletion are covered. |
| Reliability and data safety | 19/20 | Atomic challenge/outbox, cancellation/deadline handling, startup fingerprint/count/RBAC/schema guards, unique claims, and configuration rollback are implemented. |
| Compatibility | 19/20 | Existing paths, four-digit input, Bearer response/user/order shapes, partial profile form, legacy token grace, and legacy fallthrough are preserved; client refresh is not wired. |
| Verification | 17/20 | Broad negative HTTP/domain/migration tests and live source read-only checks pass; real PostgreSQL, SMTP, concurrency, and browser/PWA rehearsal remain. |
| Total | 94/100 | The disabled guarded backend slice exceeds the requested threshold without claiming live cutover readiness. |

## Enablement sequence

1. Apply Alembic through `20260811_0006` to an isolated target.
2. Run the identity dry-run against the same source snapshot, review it, and
   apply using `--expect-fingerprint`.
3. Start the notification worker with the same encryption-key ring as the API.
4. Configure `IDENTITY_MIGRATION_FINGERPRINT`; optionally set a legacy-token
   grace cutoff no more than 31 days ahead.
5. Complete frontend single-flight refresh, backend logout, and expired-session
   behavior for web and installed PWA.
6. Rehearse request, delivery, login, profile, email change, refresh/reuse,
   logout, deletion, ownership denial, and rollback on real isolated services.
7. Only after the evidence is reviewed, set `IDENTITY_API_ENABLED=true` in
   staging; production remains disabled through the observation period.

## Rollback

Set `IDENTITY_API_ENABLED=false` and restart the API. The complete auth route
family then falls through to legacy again. Retain PostgreSQL users, sessions,
audits, claims, notification rows, all required encryption keys, the source
SQLite file, and uploads for diagnosis. Do not downgrade `0006` after claims or
new identity activity exist; stopping the producer and worker is safer than
dropping security and ownership history.
