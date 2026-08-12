# Stage 14: secure target order reads and guarded cutover

Status: complete behind a default-off backend flag

Quality score: 93/100

## Safety boundary

`ORDER_READS_ENABLED` defaults to false. With the flag off, all existing legacy
behavior is unchanged. With it on, only GET order paths move to PostgreSQL;
`POST /api/orders`, YooKassa webhooks, CDEK, email, and legacy admin mutations
remain on the mounted application. A contract test proves POST still reaches
legacy while GET detail is owned by the protected target router.

The flag requires the target database, guarded identity API, and a reviewed
64-character order migration fingerprint. Startup verifies the imported
baseline before serving traffic. No schema revision is added in this stage.

## Delivered

- target response mapper preserves the current `LegacyOrderResponse` contract;
- imported orders return exact raw legacy `cart_items` and quarantined
  YooKassa/CDEK fields, while target-created orders serialize normalized line
  snapshots, variant/SKU, image, and customization into the same string shape;
- `/api/auth/orders` switches from the read-only SQLite bridge to PostgreSQL
  without changing its response model;
- active users with a verified normalized email claim matching imported IDs;
  claims use the existing keyed digest and unique source ID, survive later email
  changes, and never depend on phone-only matching;
- new orders are visible through direct `order.user_id` ownership;
- authenticated customer detail requires `orders.read_own`; an unowned or
  missing ID returns the same `404` and does not reveal existence;
- anonymous detail returns `401`, removing the legacy numeric-ID disclosure;
- staff list/detail requires live `orders.read_all` RBAC and list reads are
  bounded to 1-500 rows with a non-negative offset;
- customers receive `403` on the all-orders list;
- repository ownership uses an `EXISTS` claim query rather than loading an
  unbounded ID list into application memory;
- startup verifies one reviewed migration run, exact import/order/item/provider
  counts, exact source-to-target ID mapping, no imported reservations, and at
  least the imported initial history baseline;
- later target-created orders and additional legitimate history are allowed by
  the read guard without weakening the immutable imported baseline;
- Compose and environment examples expose both read flag and fingerprint.

## Compatibility boundary

The account/PWA response shape is preserved, and existing identity refresh and
claim behavior remains compatible. However, the public order-result page still
requests `/api/orders/{id}` without an authenticated session or opaque guest
capability. Enabling this secure router would correctly return `401` there.

Production activation is therefore intentionally blocked on one of these
explicit frontend/backend contracts:

1. require the authenticated account that owns the order; or
2. issue a high-entropy order-scoped guest token at checkout, store only its
   digest, and send it outside the numeric path identifier.

The second option is required for a true guest checkout. Guessable order IDs,
email/phone query parameters, and reusable provider IDs are not acceptable
capabilities.

## Verification

- complete backend gate passed: Ruff lint/format, 126 unit/contract tests, and
  offline PostgreSQL Alembic upgrade/downgrade through `20260811_0011`;
- anonymous detail `401`, owner detail/list success, foreign detail `404`, and
  customer all-list `403` passed through the real FastAPI dependency path;
- manager `orders.read_all` list/detail and pagination passed after live RBAC
  assignment;
- exact imported raw cart/customization and provider reference output passed;
- direct target order serialization retained variant, SKU, customization, and
  quantity;
- verified-email claim digest did not contain the email and continued granting
  ownership after the account email changed;
- wrong fingerprint and tampered import counts prevented application startup;
- read-enabled GET overrode the legacy public route while POST continued to the
  legacy writer;
- existing guarded identity contracts remained green;
- production and local Compose rendering and repository whitespace passed;
- stage 14 changes no frontend file and makes no browser/PWA success claim.

Docker/OrbStack remains unavailable, so this does not prove PostgreSQL query
plans, concurrent claim insertion, deployment startup, browser behavior, or an
installed-PWA session. SQLite and TestClient prove authorization and response
semantics; offline DDL is not runtime PostgreSQL evidence.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Router, service, repository, mapper logic, cutover verification, and identity/RBAC dependencies remain separated. |
| Security and privacy | 20/20 | Authentication is mandatory, ownership is fail-closed, foreign IDs return 404, staff uses permissions, and claims store digests. |
| Reliability and data safety | 19/20 | Fingerprint/count startup guard, stable source mapping, bounded staff reads, claim replay, and explicit method split are covered. |
| Compatibility | 18/20 | Account and admin JSON contracts are preserved and POST stays legacy; guest public detail intentionally needs a coordinated frontend capability change. |
| Verification | 17/20 | Full automated/offline gates and HTTP authorization paths pass; real PostgreSQL, browser/PWA, staging, and guest flow remain outstanding. |
| Total | 93/100 | The secure default-off read boundary exceeds the threshold and clearly refuses an unsafe production guest cutover. |

## Next bounded slices

1. Add an opaque guest order capability and update the order-result frontend
   path, or explicitly require authenticated checkout ownership.
2. Rehearse identity/catalog/cart/order reads together against real PostgreSQL,
   MinIO, web, and installed PWA sessions.
3. Add YooKassa attempt/event tables, durable verified webhook intake, and
   reconciliation before payment can invoke the order lifecycle.
4. Add server-owned delivery/promotion snapshots and guarded target checkout.
5. Move CDEK state out of quarantine into delivery shipment/event models.

## Rollback

Because target order creation remains disabled, rollback is configuration-only:
set `ORDER_READS_ENABLED=false` and restart. PostgreSQL imports and claims remain
as inert evidence while `/api/auth/orders` and GET order routes return to
legacy. Do not drop the imported data or `0011` tables. After any later target
checkout write, switching the read source back would require explicit reverse
reconciliation and is no longer a safe rollback.
