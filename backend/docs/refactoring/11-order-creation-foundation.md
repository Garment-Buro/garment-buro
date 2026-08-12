# Stage 11: immutable order creation foundation

Status: complete for the bounded persistence/service slice; not routed

Quality score: 92/100

## Safety boundary

This stage does not own any HTTP route and has no activation flag. Current
`POST`, list, and detail requests under `/api/orders` continue through legacy
SQLite. Existing stock decrement, YooKassa, CDEK, webhook, and email behavior is
untouched.

Revision `20260811_0009` creates empty PostgreSQL tables. It does not import
legacy orders, modify inventory, contact providers, enqueue notifications, or
change frontend behavior. The new service must remain internal until the
delivery quote, promotion, reservation, ownership, migration, and provider
boundaries are ready together.

## Delivered

- final-name PostgreSQL `orders`, `order_items`, `order_status_history`, and
  `order_creation_requests` tables with a linear Alembic migration;
- normalized order lines with no live product/variant foreign key, preserving
  historical readability after the catalog's contract-compatible hard delete;
- server-owned product title, price, variant ID, and SKU snapshots; client title
  and price are accepted only as compatibility input and never used for money;
- exact `NUMERIC(12,2)` unit, line, subtotal, delivery, and total values with
  database consistency and non-negative constraints;
- constructor `customization`, requested size/color, and display image retained
  per immutable line; the client image remains presentation-only, not trusted
  catalog or financial data;
- canonical SHA-256 request fingerprints and digest-only idempotency keys;
- insert-on-conflict plus row-lock acquisition that serializes simultaneous
  first attempts, returns one completed order on exact replay, and rejects a
  reused key with different user/input;
- product and variant row locks while the order snapshot is built, preventing a
  price or selection edit from crossing the transaction boundary;
- active-product and exact variant validation plus server-total comparison;
- initial version-1 `new` history with a PII-free item count and optional
  authenticated actor/user ownership;
- bounded command validation: required contact/delivery fields, 1-100 unique
  items, quantity limits, 512 KiB normalized payload, and 64 KiB customization.

No stock availability promise is made by this slice. Product and variant stock
remain unchanged in the tests by design. Delivery price is currently an
internal trusted command value, discounts are not modeled, and no payment or
delivery identifier is stored on the order row. Routing this service before
those boundaries exist would turn a sound persistence foundation into an unsafe
checkout, so runtime ownership remains with legacy.

## Verification

- complete backend gate: Ruff lint/format passed, 113 tests passed, and offline
  PostgreSQL Alembic upgrade/downgrade through `20260811_0009` passed;
- one exact replay created one order/request/history set and returned the same
  order ID; same-key changed input was rejected;
- raw idempotency key absence and digest/fingerprint persistence passed;
- tampered client title and price were ignored, current server title and price
  were stored, and the server-computed subtotal/total matched exactly;
- unknown variant, claimed-total mismatch, duplicate line ID, and invalid key
  rejection passed with failed transactions leaving no request/order rows;
- selected variant/SKU, nested customization, normalized email, initial status,
  and unchanged product stock passed;
- metadata head/linearity and offline PostgreSQL DDL generation passed;
- frontend ESLint, 196 tests, TypeScript, and production build had passed before
  this backend-only slice; no frontend file changed in stage 11;
- repository whitespace check passed.

Docker/OrbStack remains unavailable, so this evidence does not claim a real
PostgreSQL simultaneous-request/row-lock test, a migration against production
data, or a live checkout. SQLite exercises the service contract; offline DDL
proves PostgreSQL syntax, not runtime locking behavior.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Order service/repository/models and catalog snapshot boundary follow the modular-monolith dependency direction without provider calls. |
| Security and privacy | 19/20 | Raw idempotency keys are not stored, request mismatch is fail-closed, PII is absent from history, and untrusted client prices do not drive totals. |
| Reliability and data safety | 19/20 | Exact money constraints, request and catalog locks, atomic order/lines/history, replay handling, and rollback-on-error are covered. |
| Compatibility | 19/20 | Runtime routes and frontend remain unchanged; schemas retain existing cart detail fields while intentionally refusing an unsafe partial cutover. |
| Verification | 16/20 | Full automated/offline gates pass; real PostgreSQL concurrency, target migration, provider, browser, and staging proof remain outstanding. |
| Total | 92/100 | The bounded foundation exceeds the requested threshold while clearly separating persistence proof from a production-ready checkout cutover. |

## Next bounded slices

1. Add order transition rules and transactional stock reservations with expiry,
   confirm/release actions, lock ordering, and reconciliation.
2. Create a deterministic, dry-run-first legacy-order migration that preserves
   IDs, line customization, statuses, contacts, provider references, and counts
   without trusting historical totals blindly.
3. Add secure authenticated/guest ownership and compatible order read mappers.
4. Add server-owned delivery quotes and promotion snapshots, then expose the
   idempotent create path behind a guarded cutover.
5. Add separate YooKassa/CDEK attempt/event models, verified webhooks, outbox
   actions, and reconciliation before enabling live checkout.

## Rollback

Because no runtime path writes these tables, rollback before future cutover is
simply application rollback; the empty `0009` schema may remain. If isolated
tests wrote target data, preserve it before downgrade. Once any future route
creates target orders, schema downgrade is not a rollback: order, line, history,
and idempotency data must be retained and reconciled explicitly.
