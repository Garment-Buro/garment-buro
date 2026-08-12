# Stage 17: typed YooKassa verification adapter and durable worker

Status: complete as an unrouted worker behind an explicit Compose profile

Quality score: 92/100

## Safety boundary

This stage still adds no payment/webhook HTTP route and performs no payment
creation, capture, cancellation, or refund. Production and staging do not start
the payment worker unless the explicit `payments` Compose profile is selected.
Legacy remains the owner of all current provider traffic.

The new adapter implements authenticated GET verification only. It can process
durable events inserted by tests or a later guarded HTTP intake, but nothing in
the current application routes a YooKassa notification into the new tables.

## Delivered

- revision `20260811_0014` adds database checks that a processing event always
  has a lock owner/time, only a processed event has `processed_at`, and a
  composite dispatch index supports state/availability scans;
- an instance-scoped async transport uses `aiohttp`, per-client Basic Auth,
  explicit timeout, no redirects, a 256 KiB response cap, and a fixed safe user
  agent without touching YooKassa SDK global configuration;
- provider IDs are path-safe before any request;
- production/staging configuration permits only
  `https://api.yookassa.ru/v3`, network timeout is 1-60 seconds, and the worker
  lock timeout must exceed it;
- response mapping retains only the validated provider payment snapshot;
- response bodies, credentials, receipt/contact data, provider IDs, and URLs do
  not appear in errors or worker logs;
- HTTP 404 becomes a rejected unknown payment, authentication/request failures
  are terminal, 429/5xx/timeouts/network/malformed success are retryable, and
  unexpected status handling is fail-closed;
- one event is claimed with row lock and `SKIP LOCKED`, then the claim is
  committed before the external GET;
- stale processing locks can be reclaimed by another worker;
- a stale last permitted attempt is finalized as `dead` without incrementing
  beyond its constraint or issuing another provider request;
- retry delay is bounded exponential backoff and event attempts are persisted;
- the current provider object must match payment ID, metadata order ID, exact
  amount/currency, method, environment, and an allowed progression from the
  received event;
- `pending` current provider state is retried rather than treated as success;
- verified `waiting_for_capture` is recorded without pretending capture exists;
- verified cancellation closes the attempt but leaves order/reservation pending
  so a new attempt remains possible;
- verified success, payment evidence, inventory consumption, order transition,
  status history, and event processing commit in one transaction;
- exact success replay remains idempotent through payment/order/inventory state;
- an already-paid order with invalid/expired inventory rolls the transaction
  back and marks the event `dead` for explicit compensation instead of
  publishing a false fulfilled state;
- a bounded operational script and opt-in local/production Compose worker are
  available with environment-driven retry/timeout policy.

## Transaction boundary

```text
DB claim + commit
        |
        v
YooKassa GET current payment (no DB transaction held)
        |
        v
DB lock event + attempt + order + inventory
        |
        +-- verify provider/order/money/environment
        +-- record payment state
        +-- confirm inventory and order when succeeded
        +-- mark event processed
        |
        v
single commit
```

This prevents a slow provider call from holding order/inventory locks while
retaining crash recovery. The processing timeout must exceed the network
timeout so a healthy in-flight request is not reclaimed prematurely.

## Compatibility boundary

No frontend, legacy route, response model, order creation, email, or CDEK code
changes. The current `payments.py` SDK client remains mounted only through
legacy. Imported provider references remain quarantined and cannot be attached
to target payment aggregates.

The worker does not create missing webhook events and does not reconcile active
attempts without events yet. It also does not enqueue confirmation email or
CDEK work: those side effects require their own durable outbox/domain events
after the payment/order transaction commits.

## Verification

- complete backend gate passed: Ruff lint/format, 154 unit/contract tests, and
  offline PostgreSQL Alembic upgrade/downgrade through `20260811_0014`;
- provider mapping and safe classification covered 200, malformed 200, 302,
  400, 401, 403, 404, 429, 500, and 503 without exposing response content;
- unconfigured credentials and path-unsafe provider IDs failed before network;
- source inspection proves the refactored provider does not import or call the
  global YooKassa SDK configuration;
- a separate database session observed the committed `processing` claim while
  the fake provider GET was executing;
- stale reclaim, stale-final-attempt reaping, retry availability, backoff,
  success, cancellation, mismatch rejection, and provider error paths passed;
- successful processing consumed inventory exactly once and wrote payment,
  order, reservation, history, and event states together;
- expired inventory after confirmed payment rolled payment/order changes back
  and produced a terminal manual-action event;
- environment URL/range/timeout relationships and both Compose files passed;
- no application HTTP route or frontend file changed.

Docker/OrbStack remains unavailable. There is no runtime PostgreSQL evidence
for `SKIP LOCKED`, concurrent workers, transaction isolation, constraint races,
or migration apply. There is also no real YooKassa sandbox GET, TLS/auth/error
response, proxy, deployment worker, alert, or web/PWA evidence.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Provider protocol/transport, validation, repository, payment service, order lifecycle, worker, and CLI remain separated. |
| Security and privacy | 19/20 | Official endpoint restriction, Basic Auth isolation, redirect/body caps, typed PII-minimized mapping, safe errors/logs, and environment verification fail closed. |
| Reliability and data safety | 20/20 | Commit-before-network, stale recovery including final-attempt crash, bounded retry, current-object verification, and atomic payment/order/inventory/event commit are covered. |
| Compatibility | 19/20 | Legacy traffic and frontend are unchanged; downstream notification/CDEK orchestration is intentionally absent. |
| Verification | 15/20 | Strong fake-provider/SQLite/offline gates pass; real PostgreSQL concurrency, provider sandbox, HTTP intake, reconciliation, and deployment are unproven. |
| Total | 92/100 | The bounded verification worker exceeds the requested threshold without being mislabeled as a production payment cutover. |

## Next bounded slices

1. Add the default-off HTTP webhook boundary using direct-peer/trusted-proxy
   rules, raw size limiting, durable commit before acknowledgement, and equal
   safe responses for semantic duplicates.
2. Add reconciliation selection for active/unknown attempts and missed events;
   GET current state without inventing a second provider operation.
3. Add typed payment creation only after the receipt/tax contract is confirmed;
   persist the attempt before network and reuse its provider key within the
   documented 24-hour window.
4. Enqueue order confirmation and CDEK handoff as durable post-commit work.
5. Run real PostgreSQL concurrent workers plus YooKassa sandbox scenarios before
   any payment cutover flag can be enabled.

## Rollback

The worker is opt-in and no runtime route feeds it. Stop the `payment-worker`
service/profile to roll back execution. Revision `0014` can remain as inert
constraints/index. Never downgrade or delete payment evidence after any real
provider event; stop consumers and reconcile provider/order state first.
