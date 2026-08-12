# Stage 15: hashed guest order access capability

Status: complete behind the existing default-off order-read boundary

Quality score: 93/100

## Safety boundary

This stage does not route `POST /api/orders` to the target service and does not
change the frontend. The current checkout and order-result page therefore keep
their legacy behavior. The capability is usable only for a target-created guest
order that explicitly registered a token in the same database transaction.

The client owns the only raw copy of a 256-bit Base64URL token. PostgreSQL stores
only its SHA-256 digest. The token is sent in `X-Order-Access-Token`, never in a
numeric path, query string, provider reference, or response body. Missing,
malformed, unknown, expired, and revoked tokens share one `404` response.

## Delivered

- revision `20260811_0012` adds one capability per order, a globally unique
  64-character digest, bounded expiry, revocation timestamp, and cascade delete;
- the default TTL is 30 days and configuration refuses values outside 1-365;
- token generation uses 32 cryptographically random bytes and unpadded
  Base64URL, producing the strict 43-character transport shape;
- target guest order creation records the digest and expiry in the same
  transaction as the order, initial history, reservation, and idempotency row;
- the token digest participates in the request fingerprint: an exact retry
  replays the order, while a changed token under the same idempotency key fails
  as a conflict;
- raw guest and idempotency tokens are absent from persisted model state;
- `GET /api/order-access` resolves only an active, unexpired digest and returns
  the existing order response contract;
- success and failure responses set `Cache-Control: no-store`;
- revocation locks the capability row and is idempotent;
- authenticated orders cannot receive guest capability access;
- imported historical orders cannot receive capabilities retrospectively, and
  startup refuses any imported-order capability before enabling target reads;
- migration reporting counts the new table so an old import replay cannot
  silently accept unexpected target data;
- environment examples and both Compose definitions expose the TTL setting.

## Compatibility boundary

The existing authenticated account and staff order paths are unchanged. The
guest endpoint returns the same `LegacyOrderResponse` mapping used by those
paths, including exact imported/raw compatibility behavior, although imported
orders are intentionally ineligible for guest tokens.

`OrderCreationService` keeps its token argument optional because no public
target checkout owns the route yet and older service contracts remain valid. A
future public checkout must require a token whenever `user_id` is absent. The
frontend must create and retain that token before the first request, resend the
exact value for an idempotent retry, and attach it when opening the result from
web or installed PWA state.

Because the raw token cannot be recovered, a lost browser/PWA token cannot be
reissued automatically. Account ownership or a separately verified support
flow is required; numeric IDs, email/phone query parameters, and provider IDs
must never be used as recovery credentials.

## Operational requirements

- redact `X-Order-Access-Token` from reverse-proxy access logs, application
  request/error logs, tracing spans, analytics, and support diagnostics;
- never put the token in a URL, email, provider metadata, or client telemetry;
- use HTTPS only and keep response caching disabled;
- perform expiry cleanup only as an operational optimization—every read still
  checks expiry and revocation;
- rehearse first checkout, exact retry, refresh, installed-PWA reopen, expiry,
  revocation, and lost-token behavior in isolated staging;
- activate target guest checkout only after real PostgreSQL migration/startup
  evidence and frontend feature flags are coordinated.

## Verification

- complete backend gate passed: Ruff lint/format, 129 unit/contract tests, and
  offline PostgreSQL Alembic upgrade/downgrade through `20260811_0012`;
- generated token shape, digest-only persistence, expiry boundary, revocation,
  repeat revocation, invalid input, authenticated-order rejection, and imported
  order rejection passed at the service/repository boundary;
- exact token retry and changed-token idempotency conflict passed through the
  transactional target creation service;
- real FastAPI dependency tests covered absent, malformed, and valid guest
  headers, indistinguishable `404`, `no-store`, and compatible response mapping;
- startup coverage rejects guest capabilities attached to imported rows;
- local and production Compose rendering and repository whitespace passed;
- no frontend file changed, so this stage makes no browser/PWA success claim.

Docker/OrbStack remains unavailable. This stage therefore does not prove the
runtime migration, locking/index behavior, or query plan on PostgreSQL; it also
does not prove proxy redaction, deployment startup, browser state persistence,
or installed-PWA recovery. SQLite validates transaction and HTTP semantics,
while offline DDL validates the intended PostgreSQL schema only.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Router, capability service, repositories, mapper, ORM model, and cutover verification remain separated. |
| Security and privacy | 20/20 | High-entropy opaque token, digest-only storage, strict transport shape, equal 404, no-store, expiry, revocation, and import exclusion are covered. |
| Reliability and data safety | 19/20 | Capability creation is transactional, token identity is fingerprinted for replay, row-lock revocation is idempotent, and schema constraints fail closed. |
| Compatibility | 18/20 | Existing owner/staff/legacy paths and response models remain unchanged; coordinated frontend checkout/result work is intentionally outstanding. |
| Verification | 17/20 | Full automated, migration, configuration, and HTTP gates pass; real PostgreSQL, proxy, browser/PWA, and staging evidence remain unavailable. |
| Total | 93/100 | The backend capability exceeds the requested threshold without pretending the still-legacy public checkout is ready. |

## Next bounded slices

1. Add a guarded target checkout HTTP contract that requires either authenticated
   ownership or this guest token, with server-owned delivery/promotion totals.
2. Update the frontend to generate/persist/resend the token and use the header
   result endpoint in web and installed PWA modes.
3. Rehearse identity/catalog/cart/order access against real PostgreSQL and MinIO
   with staging-only flags, proxy redaction, and browser/PWA sessions.
4. Add YooKassa attempt/event persistence, durable webhook intake, provider
   verification, and reconciliation before payment changes order state.
5. Model CDEK shipments/events separately from quarantined legacy references.

## Rollback

Before target checkout activation, rollback is code/configuration only: set
`ORDER_READS_ENABLED=false` and restart. Revision `0012` can remain as an empty,
inert table. Do not downgrade it after any target guest order has been created;
preserve capability evidence and reconcile every target write before changing
source ownership.
