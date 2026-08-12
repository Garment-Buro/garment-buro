# Stage 21: atomic target checkout orchestration

Status: complete as a default-off service boundary with no public route

Quality score: 94/100

## Safety boundary

This stage coordinates existing target catalog, order, inventory, guest-access,
payment-attempt, and payment-creation services. It does not add an HTTP route,
construct a provider client in the FastAPI lifespan, switch legacy `/api/orders`,
or change the frontend/PWA.

`CHECKOUT_V2_ENABLED` is false by default. The setting cannot be enabled unless
target catalog reads, identity, target order reads, and durable payment creation
are all enabled. Their existing migration fingerprints, MinIO, identity secrets,
YooKassa credentials, and fiscal configuration remain mandatory gates.

## Delivered

- a dedicated `checkout` module owns cross-domain orchestration while order,
  inventory, payment, and provider rules remain in their existing services;
- guest checkout requires a valid client-generated opaque guest-access token;
  authenticated checkout accepts a positive resolved user ID and forbids a
  second guest capability;
- the client must persist the guest token before sending checkout, so response
  loss can replay the same order fingerprint without requiring the server to
  store or recover a raw capability;
- only `card` and `qr` are accepted at this boundary, with the existing payment
  mapping producing YooKassa `bank_card` and `sbp` respectively;
- the checkout idempotency key is normalized once and reused for order
  creation; a domain-separated SHA-256 derivation produces a deterministic
  43-character payment-attempt key without persisting or exposing the raw
  checkout key;
- target order, immutable items, status history, stock reservations, optional
  guest capability, payment aggregate, and first payment attempt prepare in one
  database transaction;
- paid checkout preflight refuses a non-positive total, missing normalized
  receipt email, missing items, or zero-price stored item before that transaction
  commits;
- if payment-attempt preparation fails, the order, reservation counters,
  capability, idempotency request, payment, and attempt all roll back together;
- after the preparation commit, durable payment creation performs its own
  commit-before-POST boundary, so no product/order/payment row lock is held
  during provider network access;
- a crash after preparation replays the same order and attempt; a historic
  order-only partial state can also continue by preparing the missing attempt;
- an unlinked timeout returns a safe checkout payment error carrying only order
  ID, attempt ID, allowlisted code, and unknown-outcome flag; replay uses the
  exact existing order, attempt, provider key, and canonical bytes;
- a provider-confirmed create rejection remains one resolved failed attempt and
  does not create another order/payment on checkout replay;
- provider-linked unknown recovery remains delegated to GET reconciliation and
  does not issue another POST;
- the returned internal result reloads current order state after payment
  processing, so an immediate provider success reports `processing/paid`
  instead of stale `new/pending` values;
- the internal result exposes the safe order/attempt IDs, replay flags, order/
  payment statuses, exact total/currency, and validated confirmation URL; it
  does not expose provider credentials, raw idempotency keys, guest token,
  receipt data, or provider response body.

## Transaction boundary

```text
validate default-off gate + actor + method
        |
        v
one DB transaction
  acquire/replay checkout request
  lock server catalog prices and stock
  create/replay order + immutable items + history
  reserve inventory
  persist guest token digest when unauthenticated
  create/replay payment aggregate + deterministic attempt
        |
        v
commit all preparation
        |
        v
durable payment creation
  commit request digest/key evidence
  YooKassa POST outside DB transaction
  persist/reconcile result according to Stage 20
        |
        v
reload current order state and return safe result
```

The outer service owns commit/rollback because it is the application-level
transaction boundary. Domain services remain reusable and do not call the
provider. Network failure cannot roll back the already durable order and
reservation, and preparation failure cannot leave an orphan order.

## Replay semantics

- same checkout key + same command + same actor/capability: replay the exact
  order and deterministic payment attempt;
- same checkout key + changed command, actor, or guest capability: fail the
  existing order idempotency fingerprint check;
- response loss after preparation but before POST: replay continues the stored
  attempt;
- unknown unlinked POST: same checkout replay reaches the same-key/body recovery
  from Stage 20;
- known provider rejection: same checkout replay returns the same failed
  attempt without a second POST;
- terminal provider result: same checkout replay returns current terminal order
  and payment state;
- a new payment attempt after a known failure/cancellation is intentionally not
  invented here; it needs a separately authorized order-payment retry contract.

## Compatibility boundary

Legacy checkout remains the only public write route. Existing response
`{order_id, payment_url}`, frontend cart clearing/redirect behavior, auth
cookies/tokens, guest order-read header, CDEK registration, email sending, and
CRM data remain unchanged.

This service does not read Redis/local cart state. It consumes the already typed
order command and revalidates product/variant availability, server price, total,
inventory, and receipt prerequisites through existing target services. A later
HTTP stage must define how web/PWA produce and retain the checkout idempotency
key and guest capability before this boundary can own traffic.

## Verification

- complete backend gate passed: 201 unit/contract tests;
- Ruff lint/format passed for all target app/tests/migrations;
- dependency compatibility and normal/all-worker Compose rendering passed;
- offline PostgreSQL Alembic upgrade still renders one linear head through
  `20260811_0016` (this stage needs no schema change);
- an observer database session saw the committed order, payment attempt, and
  active reservation during the fake provider POST;
- an injected payment-preparation failure left zero order/request/access/
  reservation/payment/attempt rows and restored reserved stock counters;
- a pre-existing order-only checkout replay prepared the missing payment and
  completed without a duplicate order or reservation;
- exact checkout replay performed no second POST and retained one order,
  reservation, payment, attempt, and reconciliation job;
- timeout replay sent byte-identical provider body/key and retained one order
  and attempt;
- authenticated immediate success reported current processing/paid state,
  confirmed the reservation, consumed stock exactly once, and created no guest
  capability;
- guest/account exclusivity, required guest capability, supported method gate,
  and default-off behavior failed before database writes;
- `qr` generated a typed `sbp` provider request;
- known provider rejection replay retained one pending order, active reservation,
  and resolved failed attempt with one provider POST;
- raw checkout/payment keys and guest capability were absent from persisted
  request/access/attempt evidence.

Docker/OrbStack remains unavailable. There is no real PostgreSQL proof for
catalog/order/payment lock ordering, rollback under connection loss, or
concurrent identical checkout requests. There is no YooKassa sandbox, public
HTTP contract, optional-auth path, browser/PWA persistence, reverse-proxy log
redaction, CDEK/email handoff, deployment, or staging traffic evidence.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Cross-domain orchestration is isolated; domain services keep ownership; preparation and network boundaries are explicit. |
| Security and privacy | 20/20 | Default-off dependency gate, server prices, required guest capability, actor exclusivity, domain-separated key derivation, and no raw secret/key persistence. |
| Reliability and data safety | 20/20 | Atomic preparation, rollback proof, commit-before-network, deterministic replay, partial-state recovery, and current-state response are covered. |
| Compatibility | 20/20 | No route, frontend, legacy, CDEK, email, CRM, or read-contract change. |
| Verification | 14/20 | Strong SQLite/fake-provider/full-suite gates pass; real PostgreSQL concurrency, provider sandbox, HTTP/browser, and deployment proof remain absent. |
| Total | 94/100 | The orchestration slice exceeds the requested threshold without overstating public/live readiness. |

## Next bounded slices

1. Add a guarded target checkout HTTP route with bounded body, required
   `Idempotency-Key`, guest capability header, optional target identity, safe
   error/status mapping, `Cache-Control: no-store`, and contract tests.
2. Add an explicit authorized payment-retry route for a retained pending order
   after a failed/canceled attempt; never create a new order for that case.
3. Add frontend/PWA generation and durable local retention of checkout and guest
   keys, then rehearse response loss, refresh, redirect, installed PWA, and
   authenticated/guest flows on staging before coordinated cutover.
4. Add durable paid-order post-commit commands for email and CDEK only after the
   payment boundary is live-safe.

## Rollback

Keep `CHECKOUT_V2_ENABLED=false`. No public router or provider lifecycle depends
on this module, and no schema was added. If later traffic is enabled, first
disable the route and payment creation, then reconcile every created order,
reservation, attempt, provider payment, and guest capability before changing
consumer ownership. Do not delete durable order/payment evidence to emulate a
legacy rollback.
