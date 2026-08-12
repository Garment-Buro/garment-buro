# Stage 12: transactional inventory reservations and order state machine

Status: complete for the bounded persistence/service slice; not routed

Quality score: 92/100

## Safety boundary

This stage still does not own `/api/orders`. Legacy SQLite remains the only live
order writer and preserves the current YooKassa, CDEK, email, list, and detail
behavior. Revision `20260811_0010` only extends the empty target schema; it does
not import orders, call a provider, enable checkout, or change the frontend.

The new reservation and lifecycle services are deliberately internal. They are
ready to be composed with future payment and delivery event handlers, but
exposing them now would leave delivery totals, promotions, order ownership, and
provider reconciliation incomplete.

## Delivered

- target products and variants have non-negative physical and reserved counters
  with database constraints that prevent reservations from exceeding stock;
- one `inventory_reservations` row per order item preserves product/variant IDs,
  quantity, expiry, resolution status/reason, and a monotonic version;
- database checks require active rows to have no resolution metadata and every
  terminal row to have both a resolution timestamp and reason;
- order creation aggregates quantities across all lines before any mutation,
  checks both product and selected-variant availability, and reserves in the
  same transaction as order/items/history/idempotency state;
- catalog products and variants are locked in stable ID order; partial in-memory
  counter mutation cannot occur after a later item fails validation;
- public catalog mappers expose available quantity (`physical - reserved`) while
  preserving physical stock until payment succeeds;
- payment confirmation atomically marks reservations confirmed, decrements both
  physical and reserved counters, and transitions `new/pending` to
  `processing/paid`;
- pending cancellation releases reserved counters without consuming physical
  stock and transitions the order to `cancelled/failed`;
- shipment and completion require `processing/paid` and `shipped/paid`
  respectively and append versioned status-history events;
- exact payment-confirmation and cancellation replays are idempotent, while
  invalid transitions and confirmation at or after reservation expiry fail
  closed;
- the expiry service selects bounded batches, uses PostgreSQL `SKIP LOCKED`,
  releases counters, records `expired`, and cancels each pending order;
- an expiry command supports full drain or `--once` execution and validates its
  batch bounds;
- product replacement/deletion and standalone variant edits fail with conflict
  while active counters exist, preventing catalog changes underneath checkout;
- reservation snapshots intentionally have no catalog foreign keys, matching
  immutable order-line history after the current hard-delete catalog contract.

## Lock order and transaction boundary

New order creation acquires the idempotency request, product rows, then variant
rows in sorted order before it inserts the order and reservations. Lifecycle
actions acquire the order, its reservation rows, products, then variants.
Expiry workers first claim orders with `SKIP LOCKED` and then use the same
reservation/product/variant sequence. Catalog product mutation serializes on
the product row; standalone variant mutation serializes on its variant row.

All stock, reservation, order-state, history, and idempotency changes are
flushed in the caller's single database transaction. Provider I/O is not inside
that boundary. Future verified webhook/event processing must persist the event
and invoke this service transactionally rather than changing counters itself.

## Verification

- complete backend gate passed: Ruff lint/format, 117 unit/contract tests, and
  offline PostgreSQL Alembic upgrade/downgrade through `20260811_0010`;
- exact creation replay produced no second reservation and aggregate duplicate
  lines could not exceed the remaining variant stock;
- reserved product and variant quantities appeared as unavailable in catalog
  responses while physical quantities remained unchanged;
- successful payment consumed physical stock once, cleared reserved counters,
  and exact replay left version/counters unchanged;
- shipment and completion produced the expected versioned history, and a
  completed order could not be cancelled as pending;
- confirmation after expiry failed without consuming stock; expiry then
  released counters, preserved physical stock, cancelled once, and repeated
  cleanup found no work;
- active reservation blocked catalog deletion;
- metadata constraints/index names, Compose rendering, expiry CLI help, and
  repository whitespace checks passed;
- frontend checks/build had already passed for the preceding backend-only order
  slice, and stage 12 changes no frontend file or runtime route.

Docker/OrbStack is unavailable on this workstation. The evidence therefore does
not claim live PostgreSQL row-lock behavior, simultaneous payment-versus-expiry
proof, migration on production data, real HTTP checkout, or staging/provider
behavior. SQLite validates service semantics; offline DDL validates generated
PostgreSQL syntax only.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Inventory repository/service and order lifecycle follow the existing modular-monolith direction and keep provider I/O outside transactions. |
| Security and privacy | 19/20 | History/reasons contain codes rather than PII, client stock/price cannot drive counters, and runtime exposure remains closed. |
| Reliability and data safety | 19/20 | Aggregate validation, row locks, database invariants, atomic confirm/release, expiry, replay handling, and catalog guards are covered. |
| Compatibility | 19/20 | Legacy order routes and frontend are unchanged; catalog output keeps its schema and now reports genuinely available stock on the target path. |
| Verification | 16/20 | Full automated/offline gates pass; real PostgreSQL concurrency, target migration, HTTP, browser/PWA, and staging evidence remain outstanding. |
| Total | 92/100 | The bounded internal slice exceeds the requested threshold without overstating production checkout readiness. |

## Next bounded slices

1. Build a deterministic dry-run/apply legacy-order migration with count,
   fingerprint, status, customization, contact, provider-reference, and money
   reconciliation.
2. Add secure target order reads for authenticated owners, verified legacy
   claims, and privileged staff without leaking guest orders.
3. Persist server-owned delivery quotes and promotion/discount snapshots, then
   connect cart ownership and the guarded checkout HTTP boundary.
4. Add separate YooKassa attempt/event models, durable verified webhook intake,
   idempotent provider calls, and reconciliation before payment can drive this
   lifecycle in staging.
5. Add CDEK quote/shipment/event models and outbox-based customer messages.

## Rollback

There is no target order runtime writer yet, so application rollback leaves the
empty `0010` schema inert. If isolated tests or manual checks wrote target data,
preserve it before downgrade. After any future cutover, disabling code or
downgrading columns is not a data rollback: orders, histories, reservations,
and physical/reserved counters must be reconciled together before any schema
change or writer switch.
