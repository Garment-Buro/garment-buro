# Stage 6: encrypted notification outbox foundation

Status: complete for the bounded foundation slice

Quality score: 94/100

## Safety boundary

This stage adds the persistent encrypted email queue and worker, but deliberately
does not switch `/api/auth/*` traffic. The next auth/profile slice must create an
OTP challenge and enqueue its email in one PostgreSQL transaction; until then,
legacy authentication and its current frontend contract remain unchanged.

No staging or production database was changed, and no real email was sent.

## Delivered

- Alembic revision `20260811_0005` with `notification_outbox` and immutable
  delivery-attempt numbering;
- AES-256-GCM authenticated encryption for recipient, OTP, and template context;
- strict URL-safe Base64 validation, exact 32-byte keys, positive key versions,
  and previous-key support for controlled rotation;
- a caller-owned enqueue transaction so the future OTP/profile/order mutation
  and notification row can commit or roll back together;
- unique deduplication keys with concurrent insert conflict recovery;
- PostgreSQL-oriented `FOR UPDATE SKIP LOCKED` claims for multiple workers;
- claim commit before network I/O, capped exponential retry, terminal
  dead-lettering, and configurable attempt/time limits;
- stale-worker recovery that marks the prior processing attempt abandoned before
  opening the next numbered attempt;
- encrypted payload erasure after both successful delivery and dead-lettering;
- safe persisted error codes without raw SMTP errors, email addresses, or OTPs in
  the outbox lifecycle fields;
- an autoescaped, strict OTP email renderer separated from the SMTP transport;
- a bounded `--once` mode and a continuous polling worker with non-sensitive
  operational logs;
- opt-in local and production Compose profiles with no default encryption key;
- settings validation and documented key generation/rotation procedure.

## Verification

- full Ruff lint and format checks: passed;
- all unit, contract, catalog, storage, database, identity, and notification
  tests: 78 passed;
- offline PostgreSQL Alembic upgrade through `20260811_0005`: passed;
- offline downgrade from head to base: passed;
- local and production Compose validation with the `notifications` profile:
  passed;
- AES-GCM round trip, ciphertext tampering rejection, invalid-key rejection, and
  previous-key decryption after rotation: passed;
- database-value inspection proving that recipient and OTP are not stored in
  plaintext: passed;
- same-key enqueue deduplication and SMTP failure-to-retry-to-sent flow: passed;
- no claim before `available_at`, stale claim abandonment/recovery, and ordered
  attempt history: passed;
- payload erasure after sent and dead states: passed;
- tampered queued payload moves directly to dead-letter without SMTP or retry:
  passed;
- repository diff whitespace check: passed.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Model, crypto, renderer, transport, repository, orchestration service, settings factory, worker, and migration have separate responsibilities. |
| Security and data minimization | 20/20 | Authenticated encryption, strict key validation/rotation, no plaintext payload persistence, terminal erasure, and safe error codes are tested. |
| Reliability | 19/20 | Transactional enqueue boundary, deduplication, skip-locked claims, durable attempt history, retry/backoff, stale recovery, and restart policy are present; SMTP cannot provide exactly-once delivery. |
| Compatibility | 18/20 | The renderer accepts the current four-digit OTP while supporting the target configured range, and legacy routes remain unchanged; auth is not wired yet. |
| Verification | 17/20 | Negative and lifecycle tests plus offline migration and Compose checks pass; real PostgreSQL concurrency, SMTP, and deployed worker observation remain for staging. |
| Total | 94/100 | The bounded queue foundation exceeds the required threshold without claiming email or auth cutover. |

## Operational semantics and rollback

The queue is at-least-once. A worker crash after SMTP accepts a message but
before `mark_sent` commits can lead to a duplicate after stale-claim recovery.
Templates must remain idempotent from the recipient's perspective, and provider
message identifiers can be added when the chosen SMTP provider exposes them.

Before integration, rollback is limited to stopping the opt-in worker and
downgrading revision `0005` to `0004`. After auth or order flows begin enqueueing,
do not drop the tables: stop producers and workers, inspect pending/retry rows,
retain all required old encryption keys, drain or explicitly dead-letter rows,
and only then plan a schema rollback.

## Required before auth cutover

1. Add feature-flagged auth/profile routers preserving the current public
   responses and generic anti-enumeration errors.
2. Create OTP challenges and enqueue `auth_otp` using the same session and one
   commit; use the durable challenge ID in the deduplication key.
3. Add refresh/logout HTTP contracts and Secure, HttpOnly, SameSite cookie
   behavior compatible with same-origin web and installed PWA sessions.
4. Move profile update, email change, delete, and `/api/auth/orders` behind the
   target identity and ownership services.
5. Verify migration, OTP delivery, login, refresh rotation/reuse, logout,
   ownership denial, and browser/PWA persistence on isolated real PostgreSQL and
   SMTP before enabling production traffic.
