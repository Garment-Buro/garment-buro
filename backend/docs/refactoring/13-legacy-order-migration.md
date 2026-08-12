# Stage 13: deterministic legacy order migration

Status: complete for dry-run/apply data preparation; not routed

Quality score: 93/100

## Safety boundary

This stage does not enable any target order HTTP route, payment action, delivery
action, email, or inventory change. Legacy SQLite remains the live order source.
Revision `20260811_0011` adds empty import-evidence tables and makes historical
contact columns nullable; new checkout still requires those values through its
strict command schema.

The planner opens SQLite with `mode=ro` and `query_only`. Apply requires an
explicit reviewed fingerprint and an empty target order store. Source files are
never modified. Reports contain paths, counts, order IDs in validation errors,
and a digest; they do not contain email, phone, address, item text/customization,
raw provider IDs, or raw cart JSON.

## Delivered

- deterministic source validation for the complete legacy `orders` schema;
- strict parsing of non-empty cart arrays, positive product IDs/quantities,
  bounded strings, object customization, finite two-decimal money, supported
  order/payment states, and UTC-normalized creation timestamps;
- a SHA-256 plan fingerprint over every normalized order/item/source row while
  keeping sensitive values out of the rendered report;
- separate source/planned order, item, provider-reference, synthetic-item-ID,
  and total-reconciliation counts;
- stable synthetic IDs for missing/duplicate legacy item IDs and the legacy
  quantity default of one, both surfaced as review warnings;
- exact preservation of legacy order IDs and PostgreSQL sequence synchronization
  so the next target-created order cannot collide;
- normalized immutable item snapshots including size, color, image, SKU/variant
  when present, and arbitrary constructor customization JSON;
- exact legacy `total_price` and delivery price preservation; item subtotal is
  derived as `total - delivery`, and a mismatch with summed item snapshots is
  reported instead of silently rewriting historical money;
- current order/payment status plus one version-1 `legacy.imported` history row
  at the original creation time; unavailable intermediate history is not
  invented;
- nullable historical contact/delivery fields in persistence while the new
  checkout Pydantic command remains strict;
- `legacy_order_imports` quarantine records with source-row digest, exact raw
  cart JSON, legacy statuses, and YooKassa/CDEK IDs/statuses for later verified
  provider-domain migration;
- `order_migration_runs` evidence with reviewed fingerprint and exact counts;
- same-fingerprint replay is idempotent only when target counts still match;
  altered, partial, or non-empty targets fail closed;
- historical imports intentionally create neither inventory reservations nor
  idempotency creation requests, avoiding a second stock mutation for orders
  that legacy already processed.

## Current source snapshot evidence

The real source at the time of this stage contained two orders and two item
rows. Both orders used supported `new/pending` states, had valid contact,
delivery, cart JSON, timestamps, and non-negative money. Both item sums matched
`total_price - delivery_price` exactly. Two payment provider references and no
CDEK shipment references were present.

The dry-run returned `source_orders=2`, `planned_orders=2`, `items=2`, zero
synthetic IDs, zero money mismatches, no errors, and no warnings. The reviewed
snapshot was applied to an isolated target SQLite database and applied again:
both runs produced two orders, two items, two history rows, two quarantine rows,
one migration run, zero reservations, and zero creation requests. IDs `1..2`
and the aggregate historical total were preserved. This is concrete source-data
proof, but it is not a production migration or PostgreSQL runtime proof.

## Verification

- complete backend gate passed: Ruff lint/format, 122 unit/contract tests, and
  offline PostgreSQL Alembic upgrade/downgrade through `20260811_0011`;
- planner fingerprint determinism and source-change sensitivity passed;
- PII/provider/item values were absent from valid and invalid reports and CLI
  output;
- malformed cart JSON and unsupported status failed the plan;
- customization, money, timestamps, provider references, raw source JSON, and
  preserved IDs passed the apply test;
- exact replay produced no duplicates, changed source against a populated
  target failed, and deliberately corrupted target counts invalidated replay;
- ORM metadata now includes the existing status-history timestamp that Alembic
  revision `0009` had already created;
- repository whitespace and the real-source dry-run/apply reconciliation passed;
- stage 13 changes no frontend file and does not claim browser/PWA behavior.

Docker/OrbStack remains unavailable, so real PostgreSQL inserts, sequence
behavior, constraints, transaction rollback, and target performance are not yet
demonstrated. Offline PostgreSQL DDL generation proves syntax only. Staging must
repeat dry-run/apply on a production copy and compare counts before any route
cutover.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Planner/types/service/repository/models are separated; provider snapshots are quarantined instead of treated as final payment/delivery events. |
| Security and privacy | 20/20 | SQLite is read-only, apply is fingerprint-guarded, reports are PII-minimized, and invalid emails cannot silently become ownership identifiers. |
| Reliability and data safety | 19/20 | Exact IDs/money/raw JSON, count guards, idempotent replay, target-empty enforcement, sequence sync, and no invented reservations/history are covered. |
| Compatibility | 19/20 | Live routes and frontend remain unchanged; exact raw source plus normalized snapshots supports the later legacy response mapper. |
| Verification | 16/20 | Full automated/offline gates and the real-source isolated apply pass; PostgreSQL, staging, HTTP, provider, and production-copy evidence remain outstanding. |
| Total | 93/100 | The bounded migration slice exceeds the threshold and preserves all available evidence without claiming a runtime cutover. |

## Next bounded slices

1. Add secure target order reads: authenticated owner through verified claims or
   direct user ownership, staff permission for list/detail, and no public ID-only
   guest disclosure.
2. Build a response mapper that preserves current `cart_items` and order-detail
   shapes from normalized target rows/quarantined raw source.
3. Add guarded order read cutover checks that require the reviewed migration
   fingerprint and count reconciliation.
4. Add YooKassa attempt/event persistence and verified durable webhook intake,
   then move quarantined payment references into that domain.
5. Add trusted delivery/promotion snapshots before guarded target checkout.

## Rollback

Before apply, rollback is code-only and the empty `0011` schema can remain.
After apply, preserve `orders`, `order_items`, status history, quarantine rows,
and the migration run. Downgrading nullable columns or dropping evidence tables
can lose source/provider data and can fail when historical contacts are absent.
Because target routes are still disabled, source ownership remains legacy; fix
or rerun the isolated target after review rather than deleting the legacy file.
