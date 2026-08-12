# Stage 36: guarded CRM material commands

Status: complete locally; live PostgreSQL contention and staging operator flow pending

Quality score: 94/100

## Safety boundary

This stage exposes the stage 31 append-only material ledger through the existing
default-off CRM write router. It does not introduce a second stock calculation,
mutable stock endpoint, or public object-storage path.

Every route requires the target bearer identity, `crm.access`,
`CRM_API_ENABLED`, `CRM_WRITES_ENABLED`, and an `Idempotency-Key`. Responses are
private accounting receipts with `Cache-Control: no-store`.

## HTTP contract

```text
POST /api/crm/materials/fabrics/{fabric_id}/receipts
POST /api/crm/materials/fabrics/{fabric_id}/adjustments
POST /api/crm/materials/reservations
POST /api/crm/materials/reservations/{reservation_id}/consume
POST /api/crm/materials/reservations/{reservation_id}/release
```

Receipt, consume, and release bodies contain a positive quantity exact to
`0.001` meter and a lower-snake-case reason. Adjustment additionally requires
`direction` equal to `in` or `out`. Reservation creation pins a positive fabric
ID and exact production-plan revision ID.

Successful commands return the immutable movement evidence rather than a
mutable balance or reservation entity:

```json
{
  "movement_id": 301,
  "fabric_id": 12,
  "reservation_id": 77,
  "movement_type": "consume",
  "quantity_meters": "1.250",
  "balance_on_hand_after": "48.750",
  "balance_reserved_after": "3.000",
  "balance_available_after": "45.750",
  "occurred_at": "2026-08-12T13:18:18.877613Z"
}
```

## Delivered

- strict request and response DTOs bound quantities to the database precision,
  reason-code allowlist, positive IDs, and closed movement enum;
- all five routes delegate to `CrmMaterialService`; accounting remains
  `router -> service -> repository -> model`;
- successful service work and the immutable movement commit in one database
  transaction; domain errors are mapped to stable `404` or `409` responses;
- material keys use the CRM 16-128 character allowlist, but preserve the
  ledger's original per-fabric key scope and persist SHA-256 only;
- exact retry returns the original movement receipt, including its historical
  balances and normalized UTC timestamp, even after later movements changed the
  current balance;
- same fabric/key with changed command bytes fails closed;
- actor ID is recorded on every new material movement; raw keys and request
  bodies are absent from persistence;
- reservation creation now locks and accepts only an active plan whose unit is
  `queued` or `in_progress`; cancelled, completed, or quality-control units
  cannot acquire new material;
- an existing exact reservation retry is resolved before the current unit-state
  check, preserving deterministic retry after a later lifecycle transition;
- consume retains the active-plan guard, while release remains available so an
  unsafe reservation can always be closed without consuming stock;
- no schema revision was needed because stage 31 already stored the required
  immutable command and balance evidence.

Material idempotency is deliberately per fabric because its uniqueness is
enforced by `(fabric_id, idempotency_key_sha256)`. Clients must not share a key
between intended commands, and must retain the original key and body across
timeouts.

## Verification

- Ruff lint and format checks, legacy-entrypoint syntax, and all 276 backend
  unit/contract tests pass;
- ASGI tests cover `401/403`, flag-controlled route registration, receipt,
  reserve, consume, release, adjustment, exact historical replay, changed-body
  conflict, missing target, malformed key, excessive precision, and reservation
  refusal after unit cancellation;
- persistence assertions prove ordered movement types, actor evidence, exact
  resulting balances, and absence of raw idempotency keys;
- existing ledger tests continue proving adjustment protection, reservation
  equations, consume/release accounting, and replay conflict behavior;
- Alembic still has one linear `20260812_0027` head and full offline PostgreSQL
  upgrade/downgrade SQL compiles;
- deployment and local Compose configurations render successfully. Missing
  secret warnings are expected because validation used no live credential file.

No real PostgreSQL same-fabric race, staging manager token, or browser cabinet
was available. The write flag remains off outside a controlled rehearsal.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Thin guarded routes reuse the append-only ledger and its service/repository ownership. |
| Security and audit | 20/20 | RBAC, default-off flags, hashed keys, actor evidence, no-store, and no request/PII persistence. |
| Reliability and accounting | 20/20 | Immutable receipts, exact replay, row locks, precision bounds, lifecycle guard, and ledger equations. |
| Compatibility | 20/20 | Additive routes only; schema, existing reads, and disabled production behavior are unchanged. |
| Verification | 14/20 | Full local/offline gate passes; live PostgreSQL contention and browser proof remain. |
| Total | 94/100 | The bounded material command slice exceeds the threshold without overstating runtime proof. |

## Next bounded slice

1. Add private CRM upload and audited signed-download routes with explicit size,
   media-type, target, expiry, and default-off storage controls.
2. Add terminal project reconciliation after every unit and active reservation
   can be locked and checked in one transaction.
3. Rehearse CRM reads/writes/files against real PostgreSQL and private MinIO in
   staging before enabling a cabinet frontend.

## Rollback

Set `CRM_WRITES_ENABLED=false` and restart. The routes disappear without a
schema rollback. Never delete material movements, reservations, or balance rows
to undo a command; reconcile from ordered immutable movements and correct stock
with an explicit audited adjustment using a fresh idempotency key.
