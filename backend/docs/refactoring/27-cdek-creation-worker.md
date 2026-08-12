# Stage 27: guarded CDEK creation worker

Status: complete locally, default-off; sandbox and real PostgreSQL proof pending

Quality score: 94/100

## Safety boundary

This stage registers the database-only CDEK fulfillment handoff only when
`FULFILLMENT_CDEK_ENABLED=true` and adds a separate provider worker guarded by
`CDEK_CREATION_ENABLED=true`. Both flags default to false. Legacy CDEK traffic,
public checkout, webhook/status reads, and production behavior remain unchanged.

The worker never rebuilds a provider request from current catalog/order data.
It claims one prepared shipment, writes numbered attempt evidence, commits that
claim, decrypts and verifies the exact stored SHA-256 bytes, and only then calls
CDEK. Provider responses and logs retain safe references/error codes only; raw
request/response bodies and recipient PII are never written to lifecycle rows.

## Confirmed provider contract

The official CDEK v2 SDK uses `POST /oauth/token` with the client-credentials
form, Bearer authorization, `POST /orders` for creation, and `GET /orders/{uuid}`
after the entity UUID is known. A 2xx response can still contain errors inside
the top-level or nested `requests[]` structure, so HTTP success alone is not
treated as order creation.

References:

- [official CDEK SDK v2 repository](https://github.com/cdek-it/sdk2.0)
- [official SDK create/get example](https://github.com/cdek-it/sdk2.0#readme)
- [official SDK order action](https://github.com/cdek-it/sdk2.0/blob/master/src/Actions/Orders.php)
- [official SDK response parser](https://github.com/cdek-it/sdk2.0/blob/master/src/Http/ApiResponse.php)

The official SDK path reviewed here does not expose a confirmed lookup by the
client's internet-shop number. An independent SDK documents that lookup, but it
also warns that ambiguous test-server failures can create duplicates. That is
not enough evidence to automate a second POST in a production boundary.

Therefore timeout, disconnect, oversized/malformed create response, HTTP 429,
HTTP 5xx, an unexpected exception after the claim, or a stale processing claim
all move the shipment to terminal operator-review state `unknown`. The worker
does not select `unknown` rows again. Only failures known to occur before the
order POST, such as a retryable OAuth failure, enter bounded automatic retry.

## Delivered

- revision `20260812_0020` adds append-only `cdek_shipment_attempts`, unique by
  shipment and attempt number, with exact request digest, safe worker ID,
  status, provider UUID/error code, and start/completion timestamps;
- claims use `FOR UPDATE SKIP LOCKED`, increment the bounded attempt count and
  create `processing` attempt plus `create_started` event before network I/O;
- a stale `processing` claim is quarantined as `unknown`, because the previous
  process may have completed the provider POST before it died;
- the instance-scoped `aiohttp` transport owns a bounded session, disables
  redirects, caps request/response sizes, uses a synchronized expiring OAuth
  token cache, and sends the exact immutable request bytes;
- token, request, recipient, address, raw body, and provider messages never
  enter persisted error fields or structured worker messages;
- response parsing validates the entity UUID and optional provider references,
  distinguishes nested request rejection from transport ambiguity, and checks
  a returned client order number against the immutable local number;
- known pre-POST transient failures retry with capped exponential backoff and
  the same request digest/bytes; permanent validation/auth rejection becomes
  `dead`; accepted evidence becomes `created` with provider UUID;
- `FULFILLMENT_CDEK_ENABLED` activates only the local encrypted handoff, while
  `CDEK_CREATION_ENABLED` separately activates external order creation and
  requires PostgreSQL, the handoff flag, CDEK credentials, and the encryption
  key;
- production/staging continue to pin the API to `https://api.cdek.ru/v2`;
- local and production Compose files contain independent opt-in `cdek-worker`
  profiles and pass `docker compose config --quiet`.

## Runtime flow

```text
paid order fulfillment job
        |
        v
encrypted pending shipment (stage 26)
        |
        v
claim + attempt + create_started
COMMIT BEFORE NETWORK
        |
        v
decrypt + authenticate + SHA-256 verify
        |
        v
OAuth -> exact POST /orders
   |          |             |
   |          |             +-- ambiguous -> unknown, never auto-POST again
   |          +---------------- validation/auth rejection -> dead
   +--------------------------- accepted UUID -> created

OAuth/pre-POST transient -> bounded retry with same bytes
stale processing attempt -> unknown, never auto-POST again
```

## Configuration and activation order

```dotenv
FULFILLMENT_OUTBOX_ENABLED=true
FULFILLMENT_CDEK_ENABLED=false
CDEK_CREATION_ENABLED=false
CDEK_REQUEST_ENCRYPTION_KEY=<url-safe-base64-of-32-random-bytes>
CDEK_CLIENT_ID=<secret>
CDEK_CLIENT_SECRET=<secret>
CDEK_TIMEOUT_SECONDS=15
CDEK_RETRY_BASE_SECONDS=30
CDEK_RETRY_CAP_SECONDS=1800
CDEK_PROCESSING_TIMEOUT_SECONDS=120
CDEK_POLL_SECONDS=5
```

Activation is deliberately two-step. First run migration `0020`, audit product
logistics and the independent encryption key, enable only the fulfillment CDEK
handoff, and drain prepared rows without starting the network profile. Then use
CDEK sandbox credentials, inspect the exact prepared digest/package contract,
and start one worker instance:

```bash
docker compose --profile fulfillment up fulfillment-worker
docker compose --profile cdek up cdek-worker
```

Do not set `CDEK_CREATION_ENABLED=true` in production until sandbox create/get,
timeout-after-acceptance, duplicate-worker, and real PostgreSQL concurrency
tests pass. Never manually flip an `unknown` row to `retry` before provider-side
search or support confirms that no order exists.

## Verification

- exact backend gate passes Ruff lint/format, legacy-entrypoint syntax, 256
  unit/contract tests, and offline PostgreSQL upgrade/downgrade generation
  through the single `20260812_0020` head;
- provider tests prove OAuth form fields, Bearer reuse, exact bytes, response
  parsing, nested rejection, malformed response ambiguity, 5xx ambiguity, GET
  UUID consistency, and safe provider-reference validation;
- worker tests prove known pre-POST retry/backoff, byte equality across retry,
  success evidence, permanent rejection, timeout quarantine, stale-process
  quarantine, no repeat POST for unknown/dead, and attempt digest history;
- configuration tests prove default-off behavior, timeout/backoff bounds,
  processing timeout separation, dependent flags, and required secrets;
- production and local Compose models pass syntax expansion.

Docker/OrbStack remains unavailable for actual service startup, so there is no
live PostgreSQL `SKIP LOCKED` race/process-kill evidence. No CDEK sandbox
credentials were available; no OAuth, create, get, or real shipment was sent.
Those are explicit staging blockers, not claimed as completed verification.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Fulfillment handoff, immutable shipment, provider adapter, attempt repository, and worker are separate layers. |
| Security and privacy | 20/20 | Exact private bytes stay authenticated ciphertext at rest; logs/history retain safe codes and references only. |
| Reliability and data safety | 20/20 | Claim-before-network, exact-byte verification, attempt history, bounded retry, and fail-closed unknown handling prevent blind duplicate POST. |
| Compatibility | 20/20 | Two independent default-off flags and profiles preserve legacy/public behavior. |
| Verification | 14/20 | Full local/offline gate and failure-path contracts pass; real PostgreSQL and CDEK sandbox are unavailable. |
| Total | 94/100 | The locally verifiable provider-creation slice exceeds the requested threshold without overstating exactly-once behavior. |

## Next bounded slice

1. Confirm and exercise provider search by immutable client order number against
   the real CDEK sandbox contract before adding any automated `unknown` recovery.
2. Add a separate reconciliation worker that GETs known provider UUIDs and can
   resolve operator-confirmed unknown rows without rebuilding or repeating POST.
3. Add authenticated webhook intake, semantic deduplication, GET verification,
   append-only status events, and the target order delivery projection.
4. Add metrics/alerts for `unknown`, `dead`, stale claims, auth failures, retry
   age, and prepared backlog before production activation.

## Rollback

Stop the `cdek-worker` profile and set both CDEK flags false. Prepared, unknown,
dead, and created rows remain durable for repair/audit. Do not delete attempts or
encrypted requests.

Online downgrade of `0020` refuses to discard any attempt evidence. Export and
reconcile it before schema rollback. Revision `0019` separately refuses to drop
shipment/logistics evidence.
