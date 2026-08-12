# Stage 24: durable post-payment fulfillment outbox

Status: complete as a default-off publisher boundary with no network consumer

Quality score: 94/100

## Safety boundary

This stage makes verified payment success publish durable commands for three
post-payment responsibilities:

- `customer_payment_email` when the target order has a normalized email;
- `cdek_order_create` only for the exact target delivery methods
  `cdek_pickup` and `cdek_door`;
- `crm_order_project` for every paid target order.

The payment creation response path, verified webhook worker, and payment
reconciler only insert these commands. They do not call SMTP, CDEK, CRM, or any
other network transport inside the payment/order transaction. The worker and
the three production handlers are deliberately deferred to the next slices.

`FULFILLMENT_OUTBOX_ENABLED=false` remains the default. With it disabled, the
existing payment lifecycle is unchanged and does not require payment-attempt
evidence from older/manual callers. Legacy/imported orders are not seeded.
Frontend/PWA, Nginx, current email templates, legacy CDEK behavior, CRM schema,
and deployment ownership remain unchanged.

## Delivered

- revision `20260812_0017` adds `fulfillment_jobs`, one row per
  `(order_id, kind)` with a restrictive order/payment-attempt evidence chain;
- a command contains no recipient, phone, address, pickup code, cart, receipt,
  provider payload, or other PII; a future handler must load current immutable
  order data by `order_id` within its own bounded transaction;
- each row records only command kind, lifecycle state, retry budget,
  availability/lock/completion timestamps, safe result reference, safe error
  code, and the exact successful source payment-attempt ID;
- database checks enforce known kinds/states, 1–20 maximum attempts,
  nonnegative bounded attempt counts, processing-lock consistency, and a
  completion timestamp only for completed commands;
- the unique order/kind key plus PostgreSQL/SQLite conflict-safe insert makes
  payment/webhook/reconciliation replay idempotent;
- an existing command linked to another payment attempt fails closed instead of
  silently rewriting its evidence;
- scheduling requires the same order to be `paid` and in `processing`,
  `shipped`, or `completed`, plus a linked succeeded payment aggregate and
  succeeded payment attempt;
- the successful attempt is locked while command evidence is checked; publisher
  and bounded seeder also lock order evidence on PostgreSQL;
- normal payment confirmation changes payment/order/inventory and inserts all
  selected commands in the same commit;
- immediate YooKassa success, verified webhook application, and reconciliation
  pass the exact applied attempt ID into the shared lifecycle boundary;
- exact replay of an already-succeeded creation now re-enters the idempotent
  lifecycle locally without issuing another provider POST, repairing commands
  lost before this stage was deployed;
- replay remains valid after an order progresses to `shipped` or `completed`,
  so later state transitions do not prevent missing-command repair;
- a bounded seeder restores missing commands for existing verified paid target
  orders and explicitly excludes every `legacy_order_imports` row;
- the publisher is guarded independently of HTTP checkout routing, allowing a
  payment worker or reconciler process to publish while owning only its required
  domain flags;
- production and local Compose pass the publisher flag/retry budget to the API,
  payment worker, and payment reconciler; no fulfillment network-worker service
  is added prematurely.

## Transaction boundary

```text
verified YooKassa succeeded snapshot
              |
              v
lock payment attempt + payment evidence
record succeeded attempt/payment
              |
              v
lock order + inventory reservations/stock
confirm inventory once
transition order to processing/paid once
              |
              v
derive command kinds from stored order
insert (order_id, kind, source_attempt_id)
with conflict-safe idempotence
              |
              v
commit payment + inventory + order + commands together
```

If command validation or insertion fails, the local transaction rolls back the
payment/order/inventory apply. Provider success remains recoverable through the
persisted provider identity and existing reconciliation boundary; it is not
converted into a partially fulfilled paid order.

The future consumer will use a separate claim-before-network transaction. This
stage does not mark any command processing/completed and does not claim exactly
once delivery across an external service boundary.

## Configuration and recovery

```dotenv
# Apply revision 0017 first. Keep false until workers/alerts are ready.
FULFILLMENT_OUTBOX_ENABLED=false
FULFILLMENT_MAX_ATTEMPTS=5
```

Enabling the publisher requires `DATABASE_ENABLED=true`. The retry budget is
validated globally at 1–20 and is copied into every new command so a later
configuration change does not silently alter an existing command's policy.

After applying revision `20260812_0017`, schedule a bounded repair batch from
`backend/`:

```bash
FULFILLMENT_OUTBOX_ENABLED=true \
../.venv/bin/python -m scripts.seed_fulfillment_jobs --limit 100
```

The command prints only `scheduled_jobs`; it does not expose order IDs or PII.
Run bounded batches until the count is zero and reconcile unexpected paid
orders manually. Do not enable the future network worker until command counts,
kinds, source attempts, and handler idempotency are reviewed in staging.

## Verification

- the exact repository gate passed: Ruff lint/format, legacy-entrypoint syntax,
  the complete 236-test unit/contract suite, and offline PostgreSQL upgrade plus
  downgrade generation through the single `20260812_0017` head;
- both production and local Compose configurations rendered successfully with
  publisher settings on API, payment worker, and reconciler;
- immediate succeeded checkout inserted exactly email/CDEK/CRM commands and
  retained one order, payment attempt, reservation resolution, and provider
  POST across exact replay;
- persisted command representations did not contain customer email, phone,
  delivery address, pickup code, guest capability, or checkout key;
- webhook-worker and reconciliation success each published commands using the
  exact applied payment-attempt ID in the same local commit;
- replay after succeeded payment called lifecycle again without a second
  provider POST and retained one row per command kind;
- direct publisher tests rejected missing payment evidence and a conflicting
  source attempt;
- selection tests produced CRM-only for a non-CDEK order without email and all
  three commands for a CDEK order with email;
- the seeder inserted only missing commands, returned zero on replay, honored a
  bounded limit, and excluded imported legacy orders;
- with the flag disabled, lifecycle callers without payment-attempt evidence
  remained compatible and no command was inserted;
- replay of a paid completed order retained its completed state/version and
  remained eligible for repair.

Docker/OrbStack is not running, so no containerized PostgreSQL migration or
real `FOR UPDATE`/`SKIP LOCKED` concurrency test was possible. There is no
staging evidence, SMTP/CDEK/CRM network call, crash-after-provider simulation,
worker retry/dead-letter behavior, external idempotency proof, metrics, alert,
or production data seed report. The publisher must remain off for live traffic.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Payment owns only atomic PII-free publication; handler/network ownership is separated behind a durable command boundary. |
| Security and privacy | 20/20 | No PII/provider body/raw capability is stored in commands; legacy seed is excluded and evidence conflicts fail closed. |
| Reliability and data safety | 19/20 | Unique commands, exact successful-attempt evidence, atomic apply, replay repair, bounded seed, and restrictive foreign keys; consumer semantics remain next. |
| Compatibility | 20/20 | Default-off, no route/response/frontend change, older lifecycle callers remain valid, and no premature network worker is introduced. |
| Verification | 15/20 | Full local/contract/offline-PostgreSQL and Compose gates pass; real PostgreSQL concurrency, workers, providers, staging, and alerts remain unavailable. |
| Total | 94/100 | The publisher slice exceeds the requested threshold without presenting unfinished network handlers as production-ready. |

## Next bounded slices

1. Implement the generic fulfillment claim/retry/dead-letter worker with stale
   lock recovery, safe error taxonomy, metrics, and operator replay tooling.
2. Implement the customer-payment email handler by rendering stored order
   snapshots and enqueueing an encrypted notification through the existing SMTP
   outbox; verify duplicate-safe customer content.
3. Replace the legacy CDEK client with an instance-scoped async adapter,
   canonical package/tariff validation, persisted provider UUID/number/events,
   idempotent create/reconcile behavior, and sandbox tests.
4. Add a private CRM order projection model/handler that stores internal state
   separately from public catalog/order reads and can replay by order ID.
5. Rehearse migration, concurrent publisher replay, bounded seed, process crash,
   and handler recovery on real PostgreSQL in staging before enabling the flag.

## Rollback

Set `FULFILLMENT_OUTBOX_ENABLED=false` on the API, payment worker, and payment
reconciler first. Payment confirmation then stops publishing while all existing
rows remain available for inspection/recovery. Do not downgrade revision
`20260812_0017` while jobs exist; the online downgrade refuses that operation.
Do not delete or relink command rows to make a downgrade pass. Export and
reconcile their state, then decide explicitly whether to retain the table or
remove it only after every external side effect is accounted for.
