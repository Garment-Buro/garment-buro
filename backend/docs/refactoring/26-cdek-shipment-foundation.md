# Stage 26: immutable CDEK shipment foundation

Status: complete as a default-off database handoff; no CDEK network traffic

Quality score: 95/100

## Safety boundary

This stage does not register the `cdek_order_create` fulfillment handler in the
runtime factory and does not replace the legacy CDEK client. It adds the durable
boundary that must exist before a provider worker is allowed to perform OAuth,
`POST /orders`, `GET /orders`, or webhook work.

The fulfillment worker can exercise the new handler only when it is explicitly
constructed in tests or future worker wiring. Its database-only transaction
revalidates the paid order and exact succeeded payment attempt, creates one
encrypted immutable request, records a `prepared` shipment event, and completes
the PII-free fulfillment command together. CDEK, CRM, frontend/PWA, public API,
and legacy production traffic are unchanged by default.

## Source contract and removed guesses

The existing admin form labels product `weight`, `height`, `width`, and `length`
as logistics data for CDEK. Variant width/height are garment measurements and
are not used for packaging. The official CDEK v2 SDK documentation describes
package weight in grams, package dimensions in centimeters, item unit weight,
client order number, recipient, tariff, locations, and a successful creation
response containing an entity UUID. It also requires transport failures and
provider validation errors to be handled separately.

The legacy backend and frontend used fallback packages of 500/1000 grams and
20x20x10 centimeters. Those guesses are intentionally not copied. Target CDEK
checkout now requires every selected product to have all four positive product
logistics values. Missing data fails before an order/payment is committed.

References used for this contract:

- [CDEK SDK v2 documentation and create-order example](https://github.com/cdek-it/sdk2.0/wiki#создание-заказа)
- [CDEK SDK package fields and units](https://github.com/cdek-it/sdk2.0/blob/master/src/BaseTypes/Package.php)
- [CDEK SDK item fields and unit weight](https://github.com/cdek-it/sdk2.0/blob/master/src/BaseTypes/Item.php)

## Delivered

- revision `20260812_0019` adds nullable logistics snapshots to `order_items`;
  all four are null for historical/unsupported data or all four are positive;
- new target orders copy logistics only from locked product rows, never from
  client cart JSON or variant garment measurements;
- CDEK target checkout requires a valid 7-15 digit recipient phone after
  removing display separators, and pickup delivery requires a pickup-point code;
- CDEK orders are limited by `CDEK_MAX_PACKAGES` before inventory reservation or
  payment creation; the default is 100 and the accepted configuration range is
  1-1000;
- each purchased unit becomes one deterministic package, matching the existing
  checkout quantity expansion while replacing fallback dimensions with trusted
  snapshots; decimal grams and centimeters round upward so physical values are
  never understated;
- canonical JSON is stable (`sort_keys`, compact separators, UTF-8, no NaN),
  uses `GB-<zero-padded-order-id>` as the client order number, configured tariffs
  and sender city/name, paid item value (`payment.value = 0`), exact declared
  item cost, RUB, recipient, destination, and one unique package number per unit;
- one `cdek_shipments` row is linked to the order, source fulfillment job, and
  exact succeeded payment attempt; each link and client order number is unique;
- the exact canonical bytes are SHA-256 hashed before any future provider call;
  only the digest, safe references, lifecycle state, and provider references are
  readable in PostgreSQL;
- request bytes, including recipient and address PII, are AES-256-GCM encrypted;
  authenticated additional data binds ciphertext to order ID, request digest,
  request schema, and key version, preventing undetected row swaps;
- key version plus previous-key configuration supports later rotation without
  rewriting existing shipment evidence;
- shipment lifecycle fields already reserve bounded pending/processing/unknown/
  retry/created/dead state, lock ownership, attempt count, provider UUID/number,
  observed status, and safe error metadata for the next worker stage;
- a separate append-only event table records a deduplicated `prepared` event and
  reserves sanitized provider lifecycle event types without storing raw bodies;
- replay of the same order/job/request reuses one shipment; conflicting source
  job, payment attempt, client number, digest, or schema fails closed;
- staging/production configuration now rejects credential-bearing/non-HTTPS
  CDEK URLs and requires the exact official `https://api.cdek.ru/v2` base URL.

## Durable handoff

```text
paid order + exact succeeded payment attempt
                 |
                 v
PII-free cdek_order_create fulfillment job
                 |
                 v
lock order/items -> verify payment evidence
build canonical bytes from immutable snapshots
SHA-256 -> AES-256-GCM
insert shipment + prepared event
complete fulfillment job with cdek-shipment:<id>
commit all local evidence together
                 |
                 v
future CDEK provider worker (not registered in this stage)
```

A crash before the local commit leaves the fulfillment attempt recoverable and
no shipment. A crash after the commit leaves one pending shipment with exact
encrypted bytes. The future network worker must commit a create attempt before
sending, then recover an unknown outcome by the same client order number before
any repeat POST. This stage deliberately does not claim provider exactly-once
behavior.

## Configuration

```dotenv
CDEK_API_URL=https://api.cdek.ru/v2
CDEK_REQUEST_ENCRYPTION_KEY=<url-safe-base64-of-32-random-bytes>
CDEK_PREVIOUS_REQUEST_ENCRYPTION_KEYS={}
CDEK_REQUEST_ENCRYPTION_KEY_VERSION=1
CDEK_SENDER_NAME=GARMENT BURO
CDEK_SENDER_CITY_CODE=245
CDEK_WAREHOUSE_TO_WAREHOUSE_TARIFF=136
CDEK_WAREHOUSE_TO_DOOR_TARIFF=137
CDEK_MAX_PACKAGES=100
CDEK_CREATION_MAX_ATTEMPTS=5
```

The encryption key is not required at application startup yet because no live
CDEK handler/worker is registered. It becomes mandatory before the next stage's
feature flag can be enabled. Generate an independent random 32-byte key; do not
reuse the notification, JWT, provider, or MinIO secret.

Before target checkout is enabled, audit every active product that can be sent
through CDEK and fill exact logistics values. Existing orders created before
revision `0019` have null snapshots and must not be automatically reconstructed
from today's catalog: historical packaging needs operator review.

## Verification

- the exact backend gate passes Ruff lint/format, legacy-entrypoint syntax, 246
  unit/contract tests, and offline PostgreSQL upgrade/downgrade generation
  through the single `20260812_0019` head;
- target checkout tests use positive server catalog logistics and prove all four
  values are persisted on immutable order items;
- a missing product weight is rejected before an order, idempotency request,
  inventory reservation, or payment can be committed;
- a paid order with quantity two produces two deterministic packages with exact
  per-unit item contents; 0.425 kg remains 425 grams and fractional dimensions
  round upward to 10x22x31 centimeters;
- the database-only CDEK handler completes only `cdek_order_create`, leaves email
  and CRM commands pending, and persists one shipment plus one prepared event;
- persisted shipment/event/job representations contain no email, phone, name,
  delivery address, or pickup point; decrypting the test row recovers the exact
  hashed canonical request;
- ciphertext authentication fails after tag tampering or when moved to another
  order context;
- existing checkout, payment retry, webhook, reconciliation, email, auth,
  catalog, inventory, MinIO, and migration contract tests remain green.

Docker/OrbStack remains unavailable, so there is no live PostgreSQL evidence
for concurrent unique-key waits, `SKIP LOCKED`, online migration timing, or
process-kill recovery. No CDEK sandbox credential, OAuth token, create/get call,
webhook, status reconciliation, or real shipment exists. The CDEK fulfillment
handler must remain unregistered until the provider worker and recovery path are
implemented and tested.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Order snapshots, fulfillment handoff, shipment aggregate, future provider worker, and public reads have separate ownership. |
| Security and privacy | 20/20 | Canonical request PII is authenticated ciphertext bound to order/digest/schema/key; readable rows and events contain safe evidence only. |
| Reliability and data safety | 20/20 | Exact pre-network bytes/digest, source payment/job links, conflict checks, bounded package count, and atomic shipment/event/job commit. |
| Compatibility | 20/20 | Runtime handler remains unregistered/default-off; target checkout contract is preserved and only rejects unsafe CDEK data before payment. |
| Verification | 15/20 | Full local/contract/offline-PostgreSQL gates pass; real PostgreSQL concurrency and CDEK sandbox/network evidence are unavailable. |
| Total | 95/100 | The bounded CDEK persistence slice exceeds the requested threshold without presenting local evidence as provider validation. |

## Next bounded slice

1. Add a shared instance-scoped `aiohttp` CDEK v2 adapter with bounded timeout,
   response size, strict JSON/schema parsing, token lock/cache, sanitized errors,
   and production URL pinning.
2. Add shipment attempt history and a claim-before-network worker. Decrypt and
   verify the stored hash immediately before sending; never rebuild from order.
3. On timeout/disconnect/5xx, move to `unknown` and reconcile by immutable client
   order number. Repeat POST only after a verified not-found result and within a
   bounded recovery window.
4. Parse create `requests[]` errors separately from transport outcome; persist
   entity UUID before marking created and retrieve provider number/status by GET.
5. Add authenticated CDEK webhook intake, semantic deduplication, provider GET
   verification, status events, and target order-read projection.
6. Run the exact timeout-after-provider-acceptance and duplicate-worker cases
   against CDEK sandbox plus real PostgreSQL before registering the handler.

## Rollback

Because no live handler is registered, rollback starts by leaving all CDEK
worker flags absent/off. Do not delete `cdek_order_create` fulfillment jobs;
they remain the repair source.

Online downgrade of revision `20260812_0019` refuses to discard any shipment or
any non-null logistics snapshot. Reconcile and export durable evidence before a
schema rollback. Existing legacy CDEK records are unaffected by this revision.
