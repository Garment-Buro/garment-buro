# Stage 18: guarded YooKassa webhook HTTP boundary

Status: complete behind a default-off route ownership flag

Quality score: 93/100

## Safety boundary

`PAYMENT_WEBHOOK_V2_ENABLED` is false by default in settings and both Compose
files. When false, the refactored router is not registered and the mounted
legacy application continues to own `POST /api/webhooks/yookassa`. No production
or staging traffic was switched in this stage.

Enabling the target route requires the async database. It persists a durable
event and commits before acknowledging the provider, but it does not execute the
event inline. Provider verification and order/inventory mutation remain in the
bounded worker delivered in stage 17.

## Delivered

- a dedicated payments router can take ownership of the existing webhook path
  without changing its successful `{"status":"ok"}` response shape;
- target ownership is controlled by one default-off setting and the factory
  registers the target route before the legacy mount only when enabled;
- `Content-Type` must be JSON and the official `type` field must equal
  `notification`;
- declared and streamed bodies are independently capped at 256 KiB, so a false
  or absent `Content-Length` cannot bypass the application limit;
- the direct ASGI socket peer is authoritative unless it belongs to an explicit
  `PAYMENT_WEBHOOK_TRUSTED_PROXY_CIDRS` network;
- forwarded chains are limited in bytes/hops, require valid IP literals, and are
  walked from the direct peer right-to-left until the first untrusted address;
- a spoofed leftmost official address therefore cannot override a real attacker
  address appended by a trusted proxy;
- trusting all IPv4 or all IPv6 is rejected at configuration load;
- the exact nginx webhook location precedes the general API location, replaces
  caller-supplied forwarding data with `$remote_addr`, and applies the same body
  cap;
- the resolved source must still match the official YooKassa IPv4/IPv6 ranges;
- only validated, PII-minimized scalar evidence and raw/canonical SHA-256 hashes
  are stored; extra customer/payment-method details are discarded;
- the transaction commits before HTTP 200; an exact semantic duplicate receives
  the same 200 response without adding another row;
- malformed, unsupported, untrusted, oversized, conflicting, and unavailable-DB
  paths return bounded generic errors without reflecting provider IDs, payloads,
  credentials, or database details;
- the response is `Cache-Control: no-store`.

The implementation follows the official YooKassa contract: notifications use
`type=notification`, the supported payment events are
`payment.waiting_for_capture`, `payment.succeeded`, and `payment.canceled`, only
HTTP 200 acknowledges delivery, non-200 responses are retried for up to 24
hours, and authenticity should be checked through current object state and/or
the published source networks. See
[incoming notifications](https://yookassa.ru/developers/using-api/webhooks).

## Proxy trust contract

```text
socket peer is not a configured proxy
        -> ignore all forwarding headers
        -> validate socket peer as YooKassa

socket peer is a configured proxy
        -> parse bounded X-Forwarded-For
        -> append socket peer
        -> remove configured proxies from right to left
        -> validate first untrusted hop as YooKassa
```

Production should set `PAYMENT_WEBHOOK_TRUSTED_PROXY_CIDRS` to the smallest
actual network containing the nginx peer. It must not guess a Docker subnet or
trust every private network. Keep the target flag false until this value has
been observed and verified on staging.

## HTTP acknowledgement policy

- `200`: the durable event exists and its transaction committed, including an
  exact duplicate already in the database;
- `400`: invalid length or notification schema;
- `404`: missing/invalid peer evidence or source outside YooKassa networks;
- `409`: the same provider event identity arrived with changed semantic
  evidence;
- `413`: the body exceeded the declared or streamed limit;
- `415`: the request is not JSON;
- `503`: SQLAlchemy could not durably store/commit the event.

Only the 200 path stops provider delivery. The others deliberately request a
retry or operator attention instead of acknowledging evidence that was not
accepted.

## Compatibility boundary

The path and successful response remain compatible with the legacy integration.
No frontend/PWA, checkout, order read, CDEK, email, provider-create, capture,
cancel, or refund code changed. Existing provider traffic remains on legacy
until the flag is explicitly enabled.

The webhook route may accept an event that races ahead of the local provider
snapshot; it stores the event unlinked and the worker resolves the attempt by
provider ID later. It never creates a payment or order from untrusted webhook
data.

## Verification

- complete backend gate passed: Ruff lint/format, 167 unit/contract tests, and
  offline PostgreSQL Alembic upgrade/downgrade through `20260811_0014`;
- a real ASGI request from an official direct peer returned 200 twice while one
  committed event row remained;
- a configured trusted proxy forwarded the official peer successfully;
- an untrusted peer could not spoof an official IP through
  `X-Forwarded-For`;
- right-to-left chain selection, invalid IPs, missing forwarding evidence,
  oversized header chains, and excessive hops are covered;
- missing `type`, non-JSON content, and an oversized body returned 400, 415, and
  413 respectively;
- a factory contract proves the default flag still delegates the same route to
  legacy;
- both Compose files render with the route disabled by default;
- whitespace checks pass.

Docker/OrbStack and a local nginx binary remain unavailable. Nginx syntax was
therefore reviewed statically and through Compose rendering, not executed with
`nginx -t`. There is no real TLS request through nginx, real PostgreSQL commit,
provider redelivery, YooKassa sandbox event, staging proxy address, deployed
worker, or monitoring/alert evidence.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Router, pure peer resolver, service, repository, worker, settings, and factory ownership remain separated. |
| Security and privacy | 20/20 | Direct-peer authority, explicit proxy networks, right-to-left parsing, official IP validation, bounded body/schema, generic errors, and PII-minimized persistence fail closed. |
| Reliability and data safety | 19/20 | Commit-before-200, semantic dedup/conflict handling, and provider retry semantics are covered; deployed proxy/database behavior is unproven. |
| Compatibility | 20/20 | Default ownership and success response remain legacy-compatible with no frontend or provider action changes. |
| Verification | 15/20 | Full ASGI/offline gates pass; real nginx, PostgreSQL, sandbox, TLS, and redelivery remain unavailable. |
| Total | 93/100 | The guarded intake exceeds the requested threshold without being mislabeled as a production cutover. |

## Next bounded slices

1. Add a durable reconciliation job for provider-linked active/unknown attempts,
   with claim-before-network, bounded retry, current-object verification, and an
   atomic order/payment transition when a webhook was missed.
2. Add operational counters/alerts for dead, rejected, conflicting, unlinked,
   and stale events before enabling the route.
3. Add typed provider creation only after receipt/VAT/tax fields are agreed;
   persist before network and reuse the stored provider idempotence key.
4. Rehearse exact proxy address, TLS, duplicate/redelivery, worker recovery, and
   payment success/cancel paths on staging PostgreSQL and YooKassa sandbox.

## Rollback

Set `PAYMENT_WEBHOOK_V2_ENABLED=false` and restart the backend to return route
ownership to legacy. Stop the payment worker if it was separately enabled.
Never delete accepted provider evidence; reconcile any stored event with the
provider and target order before changing consumers.
