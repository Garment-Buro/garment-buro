# Stage 20: durable YooKassa payment creation

Status: complete as a default-off service boundary with no production traffic

Quality score: 93/100

## Safety boundary

This stage adds no public checkout route and does not switch the legacy order
endpoint or frontend/PWA. `PAYMENT_CREATION_ENABLED` is false by default in
settings and both Compose environments. Enabling the service requires the
target database, YooKassa credentials, and an explicit fiscal contract for
product and delivery receipt lines.

The code does not infer VAT, payment mode, or payment subject from a product
name. Marked-goods subjects are intentionally rejected because the target
catalog/order schema does not yet preserve marking codes. Accounting and the
YooKassa test shop must confirm the configured 54-FZ values before any HTTP
cutover.

## Delivered

- revision `20260811_0016` adds the exact provider-request digest, first/last
  create timestamps, bounded replay evidence, and a terminal `failed` attempt
  state for a provider-confirmed request rejection;
- database constraints keep creation evidence all-null/count-zero or complete,
  require terminal resolution timestamps, and allow a failed create without a
  fabricated provider ID or cancellation reason;
- the request builder uses immutable target `order_items`, exact Decimal
  amounts, and the order currency rather than reparsing a cart or accepting a
  client total;
- each order item becomes its own receipt line and delivery is a separate
  `service` line, so their calculated total must equal the stored order total;
- normalized receipt descriptions are capped at 128 characters, the stored
  normalized order email is used, and no address, phone, customization, raw
  cart, or internal CRM value enters provider metadata;
- product/delivery VAT codes, payment modes, subjects, and optional tax system
  are explicit environment settings with allowlists/ranges;
- product subject accepts only `commodity` or `non_marked`; delivery accepts
  only `service`; marked goods require a later schema and provider-contract
  stage rather than a guessed value;
- the instance-scoped aiohttp transport sends the exact canonical JSON bytes
  with the persisted UUIDv4 `Idempotence-Key`, uses Basic authentication,
  refuses redirects, and caps the response at 256 KiB;
- provider response bodies, receipt/customer data, and credentials are not
  included in provider exceptions or persisted attempt rows; only the request
  SHA-256 and safe error code are stored;
- creation intent and the digest are committed before the external POST, so a
  crash/network timeout cannot erase evidence that the operation may have
  reached YooKassa;
- a fresh concurrent duplicate is refused while the first request may still be
  in flight; after the processing timeout, an unlinked unknown outcome may
  replay only the same canonical bytes with the same persisted key;
- the replay window defaults to 23 hours, inside YooKassa's documented 24-hour
  idempotence guarantee; an unlinked attempt fails closed after that window
  instead of creating with a new key;
- an accepted response is checked against provider ID, metadata order ID,
  exact amount/currency, payment method, and staging/production test mode;
- pending/waiting responses atomically persist the provider snapshot and
  schedule the existing reconciliation job;
- an immediate succeeded response atomically persists payment evidence,
  confirms inventory, moves the order to processing, and writes order history;
- if that local transaction fails after a valid provider response, it stores
  only the verified provider identity as `unknown` and schedules reconciliation;
  later calls do not POST again once a provider ID is known;
- a provider-confirmed 4xx create rejection closes the attempt as `failed`, so
  a new client attempt can receive a new numbered attempt and UUIDv4 key;
- network/timeout/429/5xx/redirect/malformed-success outcomes remain `unknown`
  and never permit a new parallel payment attempt.

## Transaction and recovery boundary

```text
lock payment attempt -> lock order + load immutable items
        |
        +-- build canonical request and verify stored digest/replay window
        +-- persist digest + timestamp + count
        |
        v
commit before network
        |
        v
YooKassa POST /payments with persisted key and exact bytes
        |
        +-- known rejection -> failed + resolved timestamp
        +-- unknown response -> unknown; exact POST replay remains possible
        +-- valid response -> lock attempt, validate evidence
                              +-- active: persist + schedule reconciliation
                              +-- succeeded: payment + inventory + order atomically
                              +-- local apply failure: remember provider ID as unknown
                                                     + schedule GET reconciliation
```

All provider-linked recovery moves to the existing GET reconciler. This avoids
blind POST retries once the provider payment identity is known. The create and
reconciliation paths use the same attempt-first lock order.

YooKassa requires an idempotence key on create, returns the original result for
the same key/data, and documents a 24-hour guarantee. Its response guidance
requires retrying an unknown 5xx outcome with the same key and request or
checking the current object. See the official
[API interaction format](https://yookassa.ru/developers/api),
[response recommendations](https://yookassa.ru/developers/using-api/response-handling/recommendations),
and [payment process](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process).

Receipt fields and values must follow the merchant's real tax contract. The
current allowed configuration is based on YooKassa's official
[receipt basics](https://yookassa.ru/developers/payment-acceptance/receipts/basics)
and [54-FZ parameter values](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values),
but the repository deliberately ships no guessed values.

## Configuration gate

```dotenv
PAYMENT_CREATION_ENABLED=false
PAYMENT_CREATION_RETRY_WINDOW_SECONDS=82800
PAYMENT_CREATION_PROCESSING_TIMEOUT_SECONDS=60

YOOKASSA_RECEIPT_TAX_SYSTEM_CODE=
YOOKASSA_RECEIPT_PRODUCT_VAT_CODE=
YOOKASSA_RECEIPT_DELIVERY_VAT_CODE=
YOOKASSA_RECEIPT_PRODUCT_PAYMENT_MODE=
YOOKASSA_RECEIPT_DELIVERY_PAYMENT_MODE=
YOOKASSA_RECEIPT_PRODUCT_SUBJECT=
YOOKASSA_RECEIPT_DELIVERY_SUBJECT=
```

Do not copy values from an example. Obtain the product/delivery VAT, payment
mode, subject, tax system, marked-goods requirements, and any closing-receipt
obligation from accounting and the YooKassa contract. The settings validator
will refuse an enabled service when a required value is blank or unsupported.

## Compatibility boundary

Legacy `backend/payments.py`, legacy `/api/orders`, and their frontend response
remain traffic owners. No public router constructs this service yet. Existing
payment event/webhook/reconciliation behavior changes only in one compatible
way: a verified provider identity recovered after local create processing can
now seed the same durable GET job.

No catalog, cart, order-read, auth, CDEK, email, CRM, PWA, MinIO, or public API
contract changed.

## Verification

- complete backend suite passed: 192 unit/contract tests;
- Ruff lint and format passed for all target app/tests/migrations;
- offline PostgreSQL Alembic upgrade through `20260811_0016` and one-revision
  downgrade SQL rendered successfully with deterministic constraint names;
- request construction verified exact Decimal item/delivery totals, normalized
  descriptions, receipt email, metadata order ID, return URL, and no raw
  receipt data in attempt persistence;
- a separate database session observed committed request evidence before the
  fake provider POST;
- a timeout persisted `unknown`, then replayed the byte-identical body and key;
- fresh parallel replay and changed request/config replay were refused before
  network access;
- expired unlinked idempotence evidence failed closed without a provider call;
- a known request rejection produced a resolved `failed` attempt and permitted
  a second numbered attempt with a new key;
- immediate success applied payment/order/inventory atomically;
- a synthetic local apply failure rolled back success, retained verified
  provider identity, scheduled reconciliation, performed no second POST, and
  recovered through one provider GET;
- provider HTTP status classification, malformed response handling, exact
  headers/body, no-redirect behavior, invalid-key rejection, and body-size
  checks passed;
- default-off and fiscal configuration failures passed;
- dependency compatibility and normal/all-worker Compose rendering passed.

Docker/OrbStack remains unavailable. There is no live PostgreSQL proof for row
locks, concurrent POST/reconciliation races, constraints, or applied revision
`0016`. There is no YooKassa sandbox POST, fiscal receipt, real confirmation
redirect, webhook round-trip, deployed logging evidence, or accounting-approved
tax contract. Therefore the service is not production-enabled and no public
checkout route was added.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Typed request/provider/service boundaries, explicit persisted evidence, existing reconciliation reuse, and no router/provider SDK coupling; operator metrics remain ahead. |
| Security and privacy | 20/20 | Default-off, explicit fiscal contract, no guessed marking, exact server totals, no redirects, bounded bodies, safe errors, and digest-only request persistence. |
| Reliability and data safety | 20/20 | Commit-before-POST, same-key/body recovery, in-flight guard, bounded window, linked-ID GET recovery, and atomic immediate success are covered. |
| Compatibility | 20/20 | Legacy/frontend traffic and all unrelated domains remain unchanged; migration and service are inert by default. |
| Verification | 14/20 | Strong fake-provider/SQLite/offline-PostgreSQL gates pass; real PostgreSQL, YooKassa sandbox, receipt, deployment, and concurrency evidence are unavailable. |
| Total | 93/100 | The bounded creation slice exceeds the requested threshold without claiming live readiness. |

## Next bounded slices

1. Add a default-off target checkout orchestration service that creates the
   target order, guest capability, reservation, payment attempt, and payment
   request through existing domain services without putting network calls in a
   database transaction.
2. Expose the orchestration only through a guarded target route after its auth/
   guest idempotency and response contracts are captured; legacy remains the
   fallback until coordinated frontend/PWA staging.
3. Add operator counters/alerts for `failed`/unlinked `unknown`, dead events,
   and dead reconciliation jobs.
4. Rehearse real PostgreSQL concurrency and YooKassa sandbox create/success/
   cancel/timeout/duplicate/missed-webhook flows with accounting-approved
   receipt values.

## Rollback

Keep `PAYMENT_CREATION_ENABLED=false`; no traffic reaches this service today.
Revision `0016` may remain inert. Before an online downgrade, resolve every
provider-linked or unknown attempt and every reconciliation job. The downgrade
refuses to proceed while terminal `failed` attempt rows exist because silently
mapping them to provider cancellation would falsify evidence. Never delete or
rewrite payment attempts merely to satisfy downgrade constraints.
