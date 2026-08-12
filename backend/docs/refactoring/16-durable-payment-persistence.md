# Stage 16: durable YooKassa payment persistence

Status: complete as an unrouted, default-inert domain foundation

Quality score: 92/100

## Safety boundary

This stage adds no payment HTTP route, SDK/network call, webhook response, order
state transition, email, or CDEK action. Existing `POST /api/orders` and
`POST /api/webhooks/yookassa` continue through legacy unchanged. No production
or staging provider traffic writes the new tables.

The new domain separates provider evidence from the order lifecycle. Even a
persisted `succeeded` observation cannot mark an order paid until the next
worker stage fetches the current payment from YooKassa, verifies all ownership
and money fields, and commits the processed event with the order transition.

## Provider contract reviewed

The design was checked against current YooKassa documentation on 2026-08-11:

- POST/DELETE operations use `Idempotence-Key`, the same key and data replay the
  original result, and YooKassa guarantees this for 24 hours:
  [interaction format](https://yookassa.ru/developers/using-api/interaction-format);
- an HTTP 5xx leaves the result unknown and should be retried with the same data
  and key or reconciled with GET:
  [response recommendations](https://yookassa.ru/developers/using-api/response-handling/recommendations);
- incoming notifications require an official source IP and a current-object
  status check:
  [webhook guidance](https://yookassa.ru/developers/using-api/webhooks);
- payment states are `pending`, optional `waiting_for_capture`, `succeeded`, and
  `canceled`, with succeeded/canceled terminal:
  [payment process](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process).

## Delivered

- revision `20260811_0013` adds `payments`, `payment_attempts`, and
  `payment_events` with PostgreSQL-compatible constraints and downgrade;
- one payment aggregate owns an immutable order amount/currency snapshot and
  cannot be attached to imported historical orders;
- numbered attempts have unique client-key digests, request fingerprints,
  persisted canonical UUIDv4 provider keys, methods, provider IDs, redirect
  URLs, state, safe errors, and terminal evidence;
- raw client attempt keys are never stored; the provider idempotence key is
  intentionally durable so a network retry can reuse it;
- same client key and request replay the same attempt/provider key; reuse for a
  different order or snapshot fails as a conflict;
- only one prepared/unknown/pending/waiting attempt can exist for an order;
- an unknown network outcome remains active and cannot silently mint another
  provider payment;
- canceled attempts permit a new numbered attempt, while succeeded attempts
  are terminal and reject regression;
- aggregate success/resolution timestamps and cancellation evidence are
  database-constrained and preserved across exact terminal replays;
- direct provider snapshots must match provider ID, order metadata, amount,
  currency, payment method, and runtime environment;
- staging refuses live provider objects and production refuses test objects;
- webhook intake accepts only 1-262144 raw bytes from the documented YooKassa
  IPv4/IPv6 networks, including normalized IPv4-mapped IPv6 peers;
- the exact raw bytes are parsed and hashed together, preventing split body vs
  observation evidence;
- event type/status, positive RUB amount, order metadata, payment shape, paid
  semantics, cancellation evidence, HTTPS redirect, and timezone-aware provider
  timestamps are validated;
- event identity is a digest of provider, event type, and provider payment ID;
  repeated JSON formatting/extra fields deduplicate, while changed normalized
  evidence under the same identity fails closed;
- full webhook bodies are not retained; only a body digest and bounded scalar
  evidence needed for later verification/processing are stored;
- events can be linked to known attempts but unknown provider IDs remain
  representable for controlled rejection/reconciliation;
- order migration replay counts the new tables, and target-read startup refuses
  a payment attached to an imported order.

## Compatibility boundary

The new models do not change the legacy response or frontend contract. Imported
provider IDs remain quarantined in `legacy_order_imports`; they are not promoted
to verified payment attempts/events. Existing historical paid orders keep their
imported order state but receive no fabricated YooKassa evidence.

The target order creation service is not composed with `PaymentService` yet.
The current frontend therefore receives its payment URL only from legacy. A
future checkout orchestration must create/commit the order first, prepare and
commit the payment attempt, call YooKassa outside the order transaction with the
persisted key, then persist the result. It must safely resume after a process
crash at every boundary.

## Security and operational requirements

- an HTTP route must use the direct peer address or a trusted-proxy policy; an
  arbitrary `X-Forwarded-For` value is attacker-controlled;
- IP allowlisting is only an intake filter, never payment verification;
- the event worker must call YooKassa GET and verify provider payment ID,
  metadata order ID, exact amount/currency, payment method, `test`, and current
  status before changing payment/order state;
- the provider secret, complete webhook body, receipt email, confirmation URL,
  and idempotence keys must be redacted from request/error/tracing logs;
- unknown create outcomes reuse the same provider key only inside the current
  24-hour provider guarantee; afterward they require reconciliation/manual
  review, not a new blind POST;
- event claim/retry/dead-letter handling must use bounded row locks and commit
  before the external GET;
- payment success and order inventory confirmation must commit together, then
  email/CDEK work must be enqueued through durable outbox/event boundaries.

## Verification

- complete backend gate passed: Ruff lint/format, 135 unit/contract tests, and
  offline PostgreSQL Alembic upgrade/downgrade through `20260811_0013`;
- preparation, exact replay, cross-order key conflict, active-attempt exclusion,
  unknown network result, pending/succeeded/canceled transitions, retry after
  cancellation, terminal replay, and regression refusal passed;
- digest-only client key persistence and stable UUIDv4 provider key reuse passed;
- imported-order refusal and startup tamper refusal passed;
- money, method, metadata, environment, terminal timestamp, cancellation, and
  changed-evidence checks passed;
- raw-body parsing, size limit, official IPv4/IPv6 allowlist, mapped IPv6,
  semantic duplicate handling, PII discard, attempt linking, and invalid JSON
  rejection passed;
- production and local Compose rendering and repository whitespace passed;
- no frontend or runtime route changed.

Docker/OrbStack remains unavailable. These checks do not prove PostgreSQL row
locks, unique-conflict races, query plans, runtime migration, proxy peer
handling, real SDK behavior, YooKassa sandbox responses/webhooks, worker crash
recovery, or installed web/PWA checkout. Offline DDL and SQLite semantics are
not substitutes for that evidence.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Models, validation, security, repository, and service are separated; provider networking and order transitions remain outside persistence. |
| Security and privacy | 19/20 | Direct-source allowlist, raw-body binding, PII-minimized evidence, environment isolation, money/ownership checks, and log requirements fail closed; trusted-proxy HTTP handling is pending. |
| Reliability and data safety | 19/20 | Durable provider key reuse, unknown state, active-attempt exclusion, semantic event dedup, terminal invariants, and import guards are covered. |
| Compatibility | 19/20 | Legacy routes/data/response behavior remain untouched, and imported provider IDs stay quarantined. |
| Verification | 16/20 | Full automated/offline gates pass; real PostgreSQL concurrency, provider sandbox, HTTP, worker, and staging paths remain outstanding. |
| Total | 92/100 | The bounded persistence/intake layer exceeds the threshold without claiming that provider verification or payment processing exists. |

## Next bounded slice

1. Add a typed async YooKassa adapter that never mutates global SDK
   configuration, maps safe provider snapshots, classifies retryable/permanent
   failures, and reuses the persisted operation key.
2. Add a bounded event/reconciliation worker: claim/commit, GET current object,
   verify all fields, atomically process payment plus `OrderLifecycleService`,
   retry/dead-letter safely, and enqueue email/CDEK follow-up work.
3. Add the IP-guarded HTTP webhook only after the direct-peer/trusted-proxy
   contract is explicit; acknowledge only after durable intake commit.
4. Rehearse create timeout, same-key retry, succeeded/canceled/duplicate/unknown
   webhook, missed webhook reconciliation, worker crash, and provider outage in
   YooKassa sandbox with real PostgreSQL.
5. Compose the verified payment path with guarded target checkout and the guest
   capability/frontend contract.

## Rollback

Before any target payment route exists, rollback is code-only and revision
`0013` may remain as empty inert tables. Do not downgrade after target payment
evidence has been written. Preserve financial records, disable future claims,
and reconcile provider/order state explicitly before changing ownership.
