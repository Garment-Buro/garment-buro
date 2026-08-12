# Stage 22: guarded target checkout HTTP contract

Status: complete as a default-off public route with no production traffic

Quality score: 94/100

## Safety boundary

This stage exposes the Stage 21 orchestrator at `POST /api/orders` only when
`CHECKOUT_V2_ENABLED=true`. The flag is still false by default. Its existing
configuration gate requires reviewed target catalog, identity, order-read, and
payment-creation dependencies before FastAPI can register the route.

With the flag false, no checkout router or provider transport is constructed
and the mounted legacy application continues to own the endpoint. No frontend,
PWA, Nginx, database schema, CDEK, email, CRM, or deployment switch is included
in this stage.

## Delivered

- the guarded target router owns only `POST /api/orders`; existing target GET
  order routes keep their authorization behavior and legacy remains the
  default write fallback;
- the public success response is exactly the current compatibility contract
  `{order_id, payment_url}` rather than the larger internal checkout result;
- every request requires `Idempotency-Key` with the existing 16-128 character
  allowlist, and OpenAPI marks it required without relying on framework
  validation that could echo the submitted value;
- guest checkout requires the previously client-generated 43-character
  `X-Order-Access-Token`; authenticated checkout uses the resolved target user
  and rejects a simultaneous guest capability;
- optional identity accepts a genuinely absent authorization header, but any
  malformed, unsupported, expired, or otherwise invalid supplied credential
  returns 401 and is never treated as anonymous guest traffic;
- auth failures now include `Cache-Control: no-store` while retaining the
  standard Bearer challenge;
- only `application/json` is accepted, a declared body over 512 KiB is refused,
  and the actual ASGI stream independently enforces the same ceiling when no
  trustworthy content length exists;
- empty, malformed, or schema-invalid JSON returns a safe validation response
  containing field locations/types/messages without raw input or PII;
- actor/header/method errors return 400, invalid email/total/receipt returns
  422, catalog/stock/idempotency/payment-state conflicts return 409, known
  provider create rejection returns 502, and an unknown provider outcome or
  unavailable storage returns a replayable 503;
- unknown outcome responses expose only the safe retained order ID and an
  allowlisted public code, add a short `Retry-After`, and preserve the same
  order/payment/provider request for exact replay;
- all handled route responses use `Cache-Control: no-store`; unexpected service
  failures are converted to the same safe unavailable contract rather than
  exposing an exception string;
- the FastAPI factory builds one instance-scoped aiohttp transport,
  `YooKassaProviderClient`, durable creation service, and checkout orchestrator
  when enabled, then closes the transport during lifespan shutdown;
- aiohttp Basic authorization is emitted through an instance session header,
  avoiding deprecated global/auth-parameter behavior while keeping credentials
  out of source, responses, persistence, and route logs;
- the reverse-proxy configuration is deliberately unchanged: its current
  standard access format does not name either sensitive header, while adding an
  exact 512 KiB Nginx limit before the coordinated flag switch would change the
  legacy endpoint and is deferred to deployment rehearsal.

## Request contract

```http
POST /api/orders
Content-Type: application/json
Idempotency-Key: <16-128 allowlisted characters>
Authorization: Bearer <target access token>       # authenticated path
X-Order-Access-Token: <43-character capability>  # guest path only
```

The JSON document is the typed `OrderCreationCommand`: customer contact and
delivery fields, `card` or `qr`, line identity/product/variant selections,
claimed total, delivery price, and RUB currency. Client titles, prices, and
availability remain untrusted; the Stage 21 service reloads server catalog
prices and locks/reserves target inventory.

The browser/PWA must create and durably retain the checkout idempotency key and,
for guest checkout, the order-access capability before the first request. It
must reuse both values after a timeout, reload, process restart, or lost
response. This stage does not yet implement that consumer behavior.

## Response and retry contract

Successful current compatibility response:

```json
{
  "order_id": 123,
  "payment_url": "https://..."
}
```

`payment_url` may be null when provider/order state is already terminal. A
caller must not invent a new checkout key merely because the confirmation URL
is absent.

Safe unknown-outcome response:

```json
{
  "detail": {
    "code": "payment_outcome_unknown",
    "order_id": 123
  }
}
```

Retry this response with the same JSON, checkout key, and guest capability or
authenticated identity. The Stage 20/21 boundaries reuse the same order,
payment attempt, UUIDv4 provider key, and byte-identical canonical body.

Known provider rejection returns `payment_rejected` with the retained order ID
and never repeats that resolved provider POST. A separately authorized payment
retry contract is required to create a later numbered attempt for the retained
order; that is not part of this route.

## Compatibility boundary

No route ownership changes when the default flag remains false. The target
route deliberately uses the current success response shape, but the current
frontend still sends the legacy cart document and does not yet persist the two
replay credentials. Therefore enabling the flag before the consumer stage
would reject the current frontend request rather than silently accepting an
unsafe partial translation.

No reverse-proxy change is committed here. FastAPI enforces the actual stream
limit, but the generic production Nginx location may buffer up to its broader
global limit before forwarding. The coordinated staging/production switch must
add and verify an exact-path 512 KiB proxy limit at the same time the legacy
consumer is retired.

## Verification

- complete backend suite passed: 211 unit/contract tests;
- Ruff lint and format passed for all target app/tests/migrations and the legacy
  entrypoint retained syntax validation;
- offline PostgreSQL Alembic upgrade through the single `20260811_0016` head and
  full downgrade SQL rendered successfully; this stage needs no revision;
- normal and all-worker Compose configurations rendered successfully;
- target-route registration overrode a mounted legacy POST only under the
  enabled flag, while a disabled application still returned the legacy result;
- a successful guest request and exact replay returned the compatibility shape,
  called the fake provider once, and retained one order, creation request, and
  payment attempt;
- the same key with changed command failed as 409 without a duplicate;
- a timeout returned safe 503 evidence, then exact replay recovered the same
  order with byte-identical provider body/key;
- a known provider rejection returned the same safe 502 on replay and performed
  one provider POST;
- a real OTP login/access-token flow completed authenticated checkout without a
  guest capability; mixed authenticated/guest identity failed before payment;
- malformed authorization failed 401 instead of becoming guest traffic;
- wrong media, oversized declared/streamed body, invalid content length,
  malformed JSON, invalid key/email/method/total, unavailable inventory, and
  absent guest capability exercised the documented safe statuses and no-store
  headers;
- malformed JSON containing an email address did not echo that address;
- FastAPI startup created the instance provider session and shutdown closed it
  without aiohttp deprecation or resource warnings;
- OpenAPI contains the JSON command and required idempotency header contract.

Docker/OrbStack remains unavailable, so no container was started. There is no
real PostgreSQL proof for concurrent identical HTTP requests and row-lock
behavior, no YooKassa sandbox redirect/payment/webhook/reconciliation round
trip, no browser/PWA retention or reload proof, no exact-path Nginx buffering
test, and no staging/production logging evidence. The route must remain off.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Thin guarded router, optional-identity dependency, lifespan-owned provider transport, and existing domain orchestration remain separated; operator metrics remain ahead. |
| Security and privacy | 20/20 | Fail-closed supplied auth, guest/account exclusivity, bounded real stream, no PII echo, safe errors, no-store, and no raw capability/key persistence. |
| Reliability and data safety | 20/20 | Required idempotency, exact timeout replay, one-provider-POST rejection replay, safe fallback errors, and transport cleanup are covered. |
| Compatibility | 20/20 | Default-off routing preserves legacy; success shape is unchanged and no consumer/proxy/domain switch is hidden in this slice. |
| Verification | 15/20 | Full local/contract/offline-PostgreSQL gates pass; live PostgreSQL concurrency, provider sandbox, browser/PWA, proxy, container, and staging proof remain unavailable. |
| Total | 94/100 | The guarded HTTP slice exceeds the requested threshold without claiming readiness to receive current frontend or production traffic. |

## Next bounded slices

1. Add an explicitly authorized payment-retry route for a retained target order
   after a known failed/canceled attempt; never create another order for it.
2. Add frontend/PWA generation and durable local retention of checkout/guest
   credentials, translate the legacy cart into the typed command, and rehearse
   timeout, reload, installed-PWA, auth, and guest flows on staging.
3. At coordinated staging cutover, add the exact-path Nginx 512 KiB limit and
   verify headers are absent from access/error/APM logs before sending traffic.
4. Rehearse real PostgreSQL concurrency plus YooKassa sandbox create/redirect/
   webhook/reconciliation with accounting-approved receipt configuration.
5. After payment ownership is live-safe, add durable post-payment email/CDEK
   commands and CRM projections without coupling them to provider callbacks.

## Rollback

Keep `CHECKOUT_V2_ENABLED=false`. The target router and provider transport will
not be created, and the mounted legacy checkout remains the write owner. If the
flag has received staging traffic, disable it first, then reconcile every
retained order, guest capability, reservation, payment attempt, provider
payment, event, and reconciliation job before changing consumer state. Never
delete target evidence to make a rollback resemble an untouched legacy order.
