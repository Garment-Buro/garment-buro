# Stage 25: crash-safe fulfillment worker and encrypted email handoff

Status: complete as default-off email handoff; no live SMTP traffic

Quality score: 94/100

## Safety boundary

This stage consumes only `customer_payment_email` fulfillment commands. It
does not claim `cdek_order_create` or `crm_order_project`, so unfinished CDEK
and CRM integrations remain durable `pending` rows rather than becoming false
successes or dead letters.

The fulfillment worker performs no network I/O. It locks verified paid-order
evidence, builds the email payload in memory, encrypts it into the existing
notification outbox, and marks the fulfillment command completed in one local
database transaction. The existing notification worker remains the only owner
of SMTP delivery, retry, stale recovery, and payload erasure.

Both `FULFILLMENT_OUTBOX_ENABLED` and `FULFILLMENT_EMAIL_ENABLED` remain false
by default. No public route, response, frontend/PWA behavior, legacy checkout,
CDEK behavior, CRM state, or live email path changes until the flags and worker
profiles are explicitly enabled after staging rehearsal.

## Delivered

- revision `20260812_0018` adds immutable fulfillment-attempt history with one
  numbered row per job attempt;
- attempt state is constrained to `processing`, `retry`, `completed`, `dead`,
  or `abandoned`; a processing attempt cannot have a finish timestamp and every
  terminal/nonprocessing attempt must have one;
- the worker claims only registered handler kinds with `FOR UPDATE SKIP LOCKED`,
  commits ownership before work, and records the worker ID and start time;
- transient failures use capped exponential backoff; permanent failures and an
  exhausted retry budget become `dead` with a safe error code;
- stale processing attempts are changed to `abandoned`; a remaining budget
  creates the next numbered attempt, while an exhausted stale claim becomes
  `dead` without another handler call;
- due retry/pending rows already at their budget are also closed as `dead`
  instead of remaining unclaimable forever;
- completion and failure verify the current worker still owns both the job and
  its processing attempt before mutation;
- handler preparation locks order, then successful payment evidence, and only
  then the fulfillment job, preserving the publisher's lock direction and
  avoiding an order/job inversion;
- handlers are an explicit database-only protocol; this stage registers only
  `OrderPaymentEmailHandler` and does not expose a generic inline-network hook;
- the email handler revalidates `paid` plus `processing/shipped/completed`, the
  same order ID, and the exact succeeded source payment attempt before handoff;
- notification deduplication is `order:payment-confirmed:<order_id>`, so a
  recovered fulfillment attempt reuses the same encrypted notification row;
- the notification payload contains recipient, optional first name, immutable
  item title/size/color/quantity/price, and exact stored totals/currency; phone,
  delivery address, city, pickup code, guest capability, and provider evidence
  are deliberately omitted;
- recipient and template context remain AES-256-GCM ciphertext in PostgreSQL;
  fulfillment job/result/attempt rows contain only `notification:<id>`;
- the Russian paid-order template validates positive line prices, quantity,
  exact line totals, item subtotal, nonnegative delivery, final total, RUB,
  bounded text/item counts, and finite two-decimal money before SMTP;
- Jinja strict autoescaping prevents stored product/customer text from becoming
  HTML markup in the email;
- notification enqueue now uses native PostgreSQL/SQLite
  `INSERT ... ON CONFLICT DO NOTHING` instead of a nested savepoint; rollback of
  the fulfillment transaction cannot leave an orphaned notification;
- successful SMTP delivery still erases encrypted recipient/template payload,
  retaining only delivery lifecycle/audit evidence;
- an opt-in `fulfillment-worker` Compose profile and bounded `--once` mode are
  available; log lines contain job ID, kind, attempt, state, and safe error only.

## Two durable transactions

```text
fulfillment-worker
------------------
claim email job + create attempt
commit claim
        |
        v
lock order -> succeeded payment attempt -> owned job/attempt
build payload in memory
encrypt + upsert notification dedup row
mark fulfillment completed with notification:<id>
commit both together

notification-worker
-------------------
claim encrypted notification + create SMTP attempt
commit claim
        |
        v
decrypt in memory -> validate/escape template -> SMTP
mark sent and erase ciphertext, or retry/dead
commit result
```

A crash before the first handoff commit leaves no notification and the stale
fulfillment attempt is recoverable. A crash after that commit leaves a completed
fulfillment command and one pending notification. SMTP delivery remains
at-least-once: if SMTP accepts the message and the notification worker crashes
before its result commit, the customer may receive a duplicate. The paid-order
message is designed to be safe to repeat; this stage does not claim exactly-once
email delivery.

## Configuration and operation

```dotenv
FULFILLMENT_OUTBOX_ENABLED=false
FULFILLMENT_EMAIL_ENABLED=false
FULFILLMENT_MAX_ATTEMPTS=5
FULFILLMENT_RETRY_BASE_SECONDS=30
FULFILLMENT_RETRY_CAP_SECONDS=1800
FULFILLMENT_PROCESSING_TIMEOUT_SECONDS=300
FULFILLMENT_POLL_SECONDS=5
NOTIFICATION_ENCRYPTION_KEY=<url-safe-base64-of-32-random-bytes>
```

Email handoff requires the database, fulfillment publisher, and notification
encryption key. Retry/cap/timeout/poll values must be positive; cap cannot be
below base. The encryption factory still validates exact key length/encoding.

After applying migration `20260812_0018`, one bounded handoff batch can run from
`backend/`:

```bash
FULFILLMENT_OUTBOX_ENABLED=true \
FULFILLMENT_EMAIL_ENABLED=true \
../.venv/bin/python -m scripts.process_fulfillment_jobs --once --max-items 100
```

For continuous Compose operation, the fulfillment and notification profiles
must both be intentional:

```bash
docker compose --profile fulfillment --profile notifications up \
  fulfillment-worker notification-worker
```

Before doing this in staging, inspect pending email counts, verify that every
row points to a target paid order/succeeded attempt, configure SMTP secrets,
and add alerts for `dead`, stale, and queue-age thresholds. Do not enable only
SMTP and assume fulfillment commands will be consumed, or enable only the
fulfillment worker and assume notification rows have been delivered.

## Verification

- the exact backend gate passed with Ruff lint/format, legacy-entrypoint syntax,
  241 unit/contract tests, and offline PostgreSQL upgrade/downgrade generation
  through the single `20260812_0018` head;
- production and local Compose rendered with the opt-in fulfillment profile;
- a paid CDEK order produced three fulfillment commands, while the email worker
  completed only `customer_payment_email` and left CDEK/CRM `pending`;
- the completed job and attempt stored only `notification:<id>`, while persisted
  notification/job representations contained no email, phone, address, pickup
  point, first name, or raw provider/access evidence;
- decrypting the test payload recovered the intended normalized recipient,
  order/items/totals and confirmed that phone/address/pickup data was absent;
- the real notification dispatcher rendered and delivered the new template to
  a fake transport, then erased ciphertext/nonce/tag;
- malicious-looking stored first name/product title were HTML-escaped, and bad
  line/final totals plus nonfinite money were rejected;
- one transient handoff failed to `retry`, was unavailable before its 30-second
  due time, then completed as attempt 2 with exact attempt history;
- a stale attempt was abandoned and recovered; a stale last attempt became
  `dead` without invoking the handler again;
- a synthetic failure after notification upsert rolled back the notification
  and fulfillment completion together; the due retry later created exactly one
  notification and completed;
- existing auth OTP enqueue/dedup/dispatch, identity contract tests, config
  guards, and migration metadata tests remained green after the native upsert
  change;
- the worker CLI help path executes without loading provider/network state; the
  runtime rejects batch sizes outside 1–1000 and nonpositive poll intervals.

Docker/OrbStack remains unavailable, so there is no live PostgreSQL proof of
multi-worker `SKIP LOCKED`, conflict waits, lock ordering, or process-kill
recovery. There is no SMTP connection/delivery evidence, staging queue drain,
duplicate-delivery observation, alert, dashboard, or production traffic proof.
Both fulfillment flags and profiles must remain off for live traffic.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Fulfillment owns only durable local handoff; notification owns SMTP, and unsupported CDEK/CRM kinds cannot be claimed. |
| Security and privacy | 20/20 | PII is encrypted, unnecessary delivery data is omitted, template text is escaped, and logs/results use safe identifiers only. |
| Reliability and data safety | 19/20 | Claim-before-work, attempt history, ownership checks, bounded backoff/dead/stale recovery, native atomic upsert, and dedup handoff; SMTP remains at-least-once. |
| Compatibility | 20/20 | Default-off flags/profile, unchanged API/frontend/legacy paths, and existing OTP notification behavior remains tested. |
| Verification | 15/20 | Full local/contract/offline-PostgreSQL and Compose gates pass; real PostgreSQL, SMTP, concurrency, observability, and staging remain unavailable. |
| Total | 94/100 | The email-handoff slice exceeds the requested threshold without treating local tests as live delivery proof. |

## Next bounded slices

1. Add CDEK delivery aggregate/events and canonical request evidence before any
   provider call; package dimensions/tariff must come from stored validated
   order/catalog snapshots rather than fallback constants.
2. Implement an instance-scoped async CDEK token/create/get adapter with
   commit-before-network idempotency, webhook/reconciliation, retry, and sandbox
   evidence; register the CDEK fulfillment kind only after those are complete.
3. Add CRM order projection tables and a local idempotent handler, then register
   only the CRM kind and preserve internal/public data separation.
4. Add queue-age/dead/stale metrics, alerts, operator inspection/replay actions,
   and staging process-kill/concurrency tests for both handoff layers.
5. Rehearse the complete paid checkout -> fulfillment -> encrypted notification
   -> SMTP flow with real PostgreSQL and staging SMTP before enabling traffic.

## Rollback

Stop/disable `FULFILLMENT_EMAIL_ENABLED` and the fulfillment-worker first. This
halts handoff without deleting commands; new email commands may continue to
accumulate while the publisher remains enabled. Stop the notification worker
separately if SMTP delivery must halt. Set `FULFILLMENT_OUTBOX_ENABLED=false` on
all payment paths only when new command publication must also stop.

Already sent messages cannot be recalled. Do not delete completed jobs,
notification rows, or attempt history to hide a delivery. Online downgrade of
revision `20260812_0018` refuses to discard nonempty attempt history, and stage
24's downgrade still refuses a nonempty fulfillment outbox. Reconcile pending,
processing, retry, dead, completed, and sent evidence before any schema rollback.
