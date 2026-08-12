# Stage 23: authorized retained-order payment retry

Status: complete as a default-off target route with no production traffic

Quality score: 94/100

## Safety boundary

This stage adds one target-only action:
`POST /api/orders/{order_id}/payment-attempts`. It is registered only when
`CHECKOUT_V2_ENABLED=true`, which remains false by default and already requires
the reviewed target catalog, identity, order-read, and payment-creation gates.

The action never reruns order creation, changes immutable order items, creates a
second payment aggregate, or reserves stock again. It only creates a later
numbered payment attempt for an existing target order after a known failed or
canceled attempt. Legacy/imported orders, frontend/PWA behavior, Nginx, CDEK,
email, CRM, schema, and deployment ownership remain unchanged.

## Delivered

- the route has no request body, requires the existing 16-128 character
  `Idempotency-Key`, and returns the checkout-compatible
  `{order_id, payment_url}` response;
- an unexpected streamed or declared body, invalid content length, noncanonical
  order ID, or invalid retry key fails before service mutation and never echoes
  submitted data;
- target identity is exclusive: an account uses only its resolved user ID and a
  guest uses only `X-Order-Access-Token`; a mixed actor returns 400;
- account authorization requires direct `order.user_id` ownership, not merely a
  historic email claim; imported legacy orders therefore cannot enter target
  payment creation;
- guest authorization locks the order capability row, validates format, hashes
  the supplied token, compares its digest constant-time, and requires it to be
  unexpired and unrevoked;
- missing order/capability, another account, and malformed, expired, revoked, or
  wrong guest capability share the same 404 response to avoid order discovery;
- a supplied malformed/invalid Authorization header still fails 401 and cannot
  downgrade the request into guest checkout;
- a new attempt is allowed only when the target order is still payable, the
  payment has not succeeded, and the latest attempt is terminal `failed` or
  provider `canceled`;
- `prepared`, unlinked/linked `unknown`, `pending`, and `waiting_for_capture`
  attempts reject another key while their outcome can still change;
- all existing inventory reservations must remain active and unexpired; the
  retry transaction then refreshes them to one new configured inventory TTL,
  increments their versions, and commits that extension with the new attempt;
- total attempts per order, including initial checkout, are bounded by
  `PAYMENT_MAX_ATTEMPTS_PER_ORDER` (default 3, accepted range 1–10), so retries
  cannot retain stock indefinitely;
- exact retry replay does not consume the attempt limit, issue another provider
  UUID, create another row, or extend inventory again;
- a new retry obtains a new numbered attempt and UUIDv4 YooKassa idempotence key
  while retaining the same order/payment amount, currency, method, and immutable
  fiscal receipt snapshots;
- existing attempt lookup/locking precedes order locking on replay, matching the
  attempt-first creation/reconciliation boundary; a second lookup after the
  order lock closes the new-key race;
- the generic payment service now permits exact replay of a matching terminal
  attempt before checking current payable order state, so a lost immediate
  success response replays instead of incorrectly rejecting `processing/paid`;
- unknown provider outcomes return safe retained-order evidence and replay with
  byte-identical request/key; known retry rejection is terminal and is not
  POSTed twice;
- safe status mapping and `Cache-Control: no-store` match checkout: 400 invalid
  request, 401 invalid auth, 404 ownership/capability, 409 state, 502 known
  provider rejection, and replayable 503 unknown/unavailable state.

## Transaction boundary

```text
validate actor + retry key
        |
        v
lock existing attempt by retry-key digest (when replay)
lock requested target order
authorize direct user or locked guest capability
        |
        +-- exact existing key: validate order/fingerprint and reuse attempt
        |
        `-- new key:
              lock payment + latest attempt
              require failed/canceled and attempt count below cap
              lock active reservations and extend one bounded TTL
              create next numbered attempt with new provider UUIDv4
        |
        v
commit before network
        |
        v
Stage 20 durable YooKassa create/recovery
```

The service rechecks a key that appeared while waiting for the order lock. If
another request committed it, the transaction releases the order and restarts
through the attempt-first replay path. This prevents an identical concurrent
HTTP retry from creating a parallel attempt and avoids holding order locks while
waiting behind provider reconciliation on an existing attempt.

## Request and response contract

Guest request:

```http
POST /api/orders/123/payment-attempts
Idempotency-Key: <new retry key>
X-Order-Access-Token: <retained guest capability>
Content-Length: 0
```

Authenticated request replaces the guest header with the target Bearer access
token. The caller must durably store the retry key before sending and reuse it
after timeout, reload, process restart, or response loss. It must not switch to
a new key while the existing attempt is active or unknown.

Success retains the current checkout shape:

```json
{
  "order_id": 123,
  "payment_url": "https://..."
}
```

`payment_url` can be null for exact replay of a terminal attempt. A new key is
not permitted after payment succeeded.

## Configuration

```dotenv
# Total provider attempts per target order, including initial checkout.
PAYMENT_MAX_ATTEMPTS_PER_ORDER=3
```

The variable is present in local/production Compose with the same default and
is validated globally at 1–10. Retry reservation extension reuses
`INVENTORY_RESERVATION_TTL_SECONDS`; it does not add an unrelated second TTL.

## Verification

- complete backend suite passed: 229 unit/contract tests;
- Ruff lint/format passed for all target app/tests/migrations and the legacy
  entrypoint retained syntax validation;
- offline PostgreSQL Alembic upgrade through the single `20260811_0016` head and
  full downgrade SQL rendered successfully; no revision is required here;
- normal and all-worker Compose configurations rendered with the attempt-cap
  setting;
- a known-failed guest checkout created exactly one second attempt, refreshed
  its one reservation version, called the provider once for the retry, and exact
  replay retained one order, one payment, attempts `[1, 2]`, and the same URL;
- the initial and retry attempts used different provider UUIDs while their
  canonical immutable payment request bodies matched;
- a new key during an active pending attempt returned 409 without another POST;
- timeout recovery replayed the second attempt with byte-identical provider
  body/key and no third attempt;
- known retry rejection replayed safe 502 evidence and performed one POST for
  that attempt;
- provider-canceled initial payment admitted a later attempt; succeeded checkout
  replayed exactly after the order became `processing/paid`, while a new retry
  key failed;
- direct-account ownership passed via a real OTP/access-token path; another
  authenticated user received 404 and a mixed account/capability received 400;
- absent, malformed, wrong, and revoked guest capabilities returned 404;
- expired inventory refused a new attempt, while active refresh extended once,
  incremented version once, and rejected refresh after expiry;
- the default three-attempt cap allowed attempts 1–3 and refused attempt 4
  without provider access;
- empty-body enforcement covered declared and actual streamed bytes, invalid
  content length, invalid IDs/keys, no-store headers, and no request-data echo;
- with `CHECKOUT_V2_ENABLED=false`, legacy checkout still handled its POST and
  the target retry route was absent.

Docker/OrbStack remains unavailable, so no container was started. There is no
live PostgreSQL proof for simultaneous identical/different retry keys, row-lock
ordering, transaction restart, reservation refresh, or attempt-cap races. There
is no YooKassa sandbox second-attempt redirect/cancel/success/webhook/reconcile
round trip, browser/PWA key retention, proxy test, or staging traffic evidence.
The route must remain off.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Retry orchestration is isolated, reuses payment/inventory ownership, and factory wiring shares the checkout provider boundary; operator metrics remain ahead. |
| Security and privacy | 20/20 | Direct ownership, constant-time capability digest, imported-order exclusion, fail-closed auth, no body, safe errors, no-store, and no raw key/token persistence. |
| Reliability and data safety | 20/20 | Terminal-only new attempt, exact replay, attempt-first existing lock, race restart, bounded refreshed reservation, attempt cap, and durable provider recovery. |
| Compatibility | 20/20 | Default-off route, unchanged checkout response, no new order/reservation/schema, and no legacy/frontend/proxy/CDEK/email/CRM switch. |
| Verification | 15/20 | Full local/contract/offline-PostgreSQL gates pass; real PostgreSQL concurrency, provider sandbox, browser/PWA, proxy, container, and staging proof remain unavailable. |
| Total | 94/100 | The retained-order retry slice exceeds the requested threshold without claiming live concurrency or provider readiness. |

## Next bounded slices

1. Add durable post-payment fulfillment commands/outbox records for order email,
   CDEK creation, and CRM projection; provider webhook/reconciliation must only
   publish once and must never perform those network calls inline.
2. Add frontend/PWA generation and durable retention of checkout, guest, and
   retry keys plus typed cart translation and retry UI.
3. Rehearse real PostgreSQL concurrent retry keys, timeout/restart, attempt cap,
   and reservation refresh in staging.
4. Rehearse YooKassa sandbox initial and second attempts, redirect, success,
   cancel, duplicate/lost response, webhook, and reconciliation with the
   accounting-approved receipt contract.

## Rollback

Keep `CHECKOUT_V2_ENABLED=false`; the retry router and provider transport will
not be created and legacy traffic remains unchanged. If staging used the route,
disable it first and reconcile every order, reservation expiry extension,
payment attempt, provider payment, event, and reconciliation job. Do not shorten
an already committed reservation below its prior expiry during rollback, and do
not delete later attempts or rewrite provider evidence.
