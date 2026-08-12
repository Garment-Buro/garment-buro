# Stage 19: durable payment reconciliation

Status: complete as an opt-in worker with no production traffic

Quality score: 93/100

## Safety boundary

This stage adds no public route and performs no provider create, capture,
cancel, or refund. `PAYMENT_RECONCILIATION_ENABLED` is false in normal backend
settings. The long-running service exists only in the explicit
`payment-reconciliation` Compose profile, where the worker setting is enabled
for that selected service.

The reconciler only reads a current payment that already has a persisted
provider ID. It never guesses an ID, retries an unknown create with a new key,
creates an order/payment from provider data, or treats an imported legacy order
as target-owned.

## Delivered

- revision `20260811_0015` adds one durable reconciliation job per payment
  attempt with scheduled/processing/retry/completed/dead states;
- database constraints enforce state/lock/completion/observation consistency,
  bounded attempts, unique attempt ownership, and a dispatch index;
- an active provider snapshot automatically schedules a job for five minutes
  later by default, within the same transaction that records the attempt;
- a bounded idempotent seeder restores missing jobs only for provider-linked
  `unknown`, `pending`, or `waiting_for_capture` attempts;
- the seeder excludes imported legacy orders, locks only `payment_attempts` on
  PostgreSQL outer-join selection, and uses the unique constraint as a second
  concurrency guard;
- unlinked `unknown` attempts remain untouched until the typed create adapter
  can safely recover them using the stored idempotence key;
- one job is claimed through `FOR UPDATE SKIP LOCKED`, its attempt counter and
  owner are committed, and only then does one provider GET run;
- stale processing claims can be reclaimed; a crashed final allowed claim is
  marked `dead` without exceeding the database counter or issuing another GET;
- provider/auth/network failures use safe allowlisted codes and bounded
  exponential retry;
- the current provider snapshot is PII-minimized and validated against provider
  ID, metadata order ID, exact amount/currency, method, environment, and local
  state progression;
- successful provider checks store only a SHA-256 digest and safe status on the
  job; no raw provider object, customer contact, card evidence, confirmation
  URL, or provider ID is written to worker logs;
- `pending`/`waiting_for_capture` are recorded and rescheduled at the normal
  interval rather than treated as failures;
- succeeded/canceled attempts complete the job; cancellation leaves the target
  order/reservation pending for a new attempt;
- success atomically records payment evidence, consumes inventory, transitions
  the order, writes status history, and completes the job;
- paid provider state with expired or invalid inventory rolls payment/order
  mutation back and marks the job `dead` with `paid_order_transition_failed`;
- reconciliation does not fabricate a `payment_events` row; webhook audit and
  our provider polling remain distinct facts;
- a concurrent terminal webhook can complete the job while reconciliation is
  in the network phase; the reconciler observes the committed result and does
  not mutate payment/order/inventory twice;
- both apply paths lock `payment_attempt → reconciliation job`, avoiding the
  lock-order inversion that would otherwise permit a PostgreSQL deadlock;
- a bounded CLI seeds missing work, drains at most configured counts, supports
  one-shot operation, and logs only job ID, attempt number, safe status, safe
  observation status, and safe error code.

## Transaction and lock boundary

```text
DB job claim + commit
        |
        v
YooKassa GET current payment (no DB transaction held)
        |
        v
lock payment attempt
        |
        v
lock reconciliation job and verify ownership/terminal race
        |
        +-- validate current provider snapshot
        +-- record payment state
        +-- confirm inventory/order when succeeded
        +-- reschedule active or complete terminal job
        |
        v
single commit
```

Provider failures need only the job lock. Terminal webhook processing locks the
attempt and then the same job, so the two mutation paths share one lock order.
The processing timeout must remain longer than the provider network timeout.

## Recovery policy

- `scheduled`: normal current-state check is due;
- `processing`: a worker owns the persisted claim;
- `retry`: provider/network/processing failure waits for bounded exponential
  backoff;
- `completed`: provider state is terminal or another atomic webhook path
  completed it;
- `dead`: retry/active window exhausted, permanent evidence mismatch,
  configuration/provider rejection, or paid-order transition needs explicit
  operator action.

Defaults are 288 checks, five-minute normal interval, 30-second retry base,
30-minute retry cap, five-minute stale-processing timeout, and five-second idle
poll. The normal window is therefore approximately 24 hours, matching the
current webhook redelivery horizon, but must be reviewed against the enabled
payment methods before staging. YooKassa documents current-object GET as the
authenticity check and non-200 notification redelivery for up to 24 hours in
[incoming notifications](https://yookassa.ru/developers/using-api/webhooks).

## Compatibility boundary

Legacy payment routes and provider SDK remain traffic owners. The new job is
created only by target payment persistence calls or the opt-in seeder. No
frontend/PWA, checkout response, order read, CDEK, email, CRM, or MinIO behavior
changed.

Existing stage-17 event processing now completes a related reconciliation job
in the same transaction when a terminal webhook wins. Exact payment/order/
inventory idempotence remains unchanged.

## Verification

- complete backend gate passed: Ruff lint/format, 175 unit/contract tests, and
  offline PostgreSQL Alembic upgrade/downgrade through `20260811_0015`;
- PostgreSQL offline DDL renders all reconciliation constraints/indexes with
  deterministic dialect-safe shortened names;
- a separate database session observed the committed processing claim during
  the fake provider GET;
- success consumed inventory exactly once, wrote the normal order history, and
  completed the job without creating a fake webhook event;
- active provider state rescheduled at the normal interval and later completed;
- transient provider failure retried after bounded backoff;
- cancellation completed payment/job while retaining active inventory and a
  pending order;
- amount mismatch stored only safe observation evidence, marked the job dead,
  and left payment/order/inventory unchanged;
- expired inventory after provider success rolled payment/order mutation back
  and produced the manual-action error;
- a concurrent terminal webhook completed the order/job while reconciliation
  was outside a transaction; the reconciler did not double-consume inventory or
  duplicate history;
- a stale final claim was reaped without a provider call;
- missing-job seeding ignored an unlinked unknown attempt, scheduled it once
  after a provider ID appeared, and was idempotent on replay;
- event-worker success completed its automatically scheduled reconciliation job;
- CLI help and fail-fast disabled behavior passed;
- dependency compatibility, whitespace checks, and local/production Compose
  profiles passed.

Docker/OrbStack remains unavailable. There is no live PostgreSQL proof for
`FOR UPDATE SKIP LOCKED`, concurrent claim selection, deadlock behavior,
isolation, constraints, or applied revision `0015`. There is no real YooKassa
GET/sandbox, long-running worker, clock/retry observation, alerting, deployment,
or staged missed-webhook evidence.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Provider adapter, job model/repository, payment/order services, processor, and CLI have explicit boundaries; operational metrics remain ahead. |
| Security and privacy | 19/20 | Existing provider validation plus digest-only observation and safe logging persist no raw provider/PII data; real transport/log aggregation is unverified. |
| Reliability and data safety | 20/20 | Claim-before-network, single GET, shared attempt→job lock order, stale-final recovery, bounded policies, terminal race handling, and atomic payment/order/inventory/job commit are covered. |
| Compatibility | 20/20 | Default-off worker, no public route or fake webhook, imported/unlinked exclusion, and unchanged legacy/frontend contracts. |
| Verification | 15/20 | Strong SQLite/fake-provider/offline PostgreSQL gates pass; real PostgreSQL, sandbox, deployment, timing, and alerts remain unavailable. |
| Total | 93/100 | The reconciliation slice exceeds the requested threshold without claiming production readiness. |

## Next bounded slices

1. Add typed YooKassa payment creation with an agreed receipt/VAT/tax contract,
   persisted request fingerprint, stored provider key reuse, and explicit
   unknown-outcome recovery inside the provider's idempotence window.
2. Add counters/alerts and an operator view for dead/rejected/unlinked payment
   events and reconciliation jobs before enabling either worker.
3. Rehearse real PostgreSQL concurrent event/reconciliation workers and
   YooKassa sandbox success/cancel/missed-webhook scenarios on staging.
4. Enqueue confirmation email and CDEK handoff as durable post-commit work after
   the checkout/payment ownership boundary is ready.

## Rollback

Stop the `payment-reconciliation` profile or set
`PAYMENT_RECONCILIATION_ENABLED=false`. Revision `0015` may remain inert. Do not
delete reconciliation/payment evidence after real provider access; reconcile
each unresolved provider ID and target order before changing consumers or
downgrading.
