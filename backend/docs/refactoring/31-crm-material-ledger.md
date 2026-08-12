# Stage 31: append-only CRM material ledger

Status: complete locally; staff API and real PostgreSQL concurrency proof pending

Quality score: 94/100

## Safety boundary

This stage replaces the prototype's mutable fabric `stockMeters` and
`reservedMeters` fields with an append-only source of truth. A compact balance
row exists only as a locked projection for fast commands and reads; every
change also writes an immutable movement containing the resulting balances.

Reservations are pinned to exact immutable production-plan revisions. A plan
with active material reservations cannot be superseded, and consumption rejects
a reservation whose plan is no longer active. This prevents fabric from being
accounted against technological instructions that were silently replaced.

No HTTP route or runtime flag is introduced.

## Delivered

- revision `20260812_0024` adds fabric balance projections, plan/fabric
  reservations, and append-only material movements;
- balances enforce non-negative on-hand/reserved quantities and reserved not
  exceeding on-hand;
- receipts and explicit in/out adjustments change unreserved physical stock;
- reserve changes reserved only; consume decreases both reserved and on-hand;
  release decreases reserved without changing on-hand;
- adjustment-out cannot touch fabric already reserved for production;
- one plan revision can own one reservation per fabric, while a plan may reserve
  multiple fabrics;
- reservation accounting always satisfies `requested = remaining + consumed +
  released`, and closes exactly when remaining reaches zero;
- quantities are finite, positive, bounded, and exact to 0.001 meter;
- every command accepts a raw idempotency key but persists only its SHA-256;
- exact command retry returns the original movement; reusing a key with changed
  command parameters fails closed;
- movement rows store safe reason/actor evidence plus exact on-hand/reserved
  balances after the command, allowing deterministic replay/reconciliation;
- fabric, plan, reservation, and balance rows are locked in command paths;
- planning checks active reservations before superseding a plan, and reservation
  creation locks the active plan before linking stock to it;
- online downgrade refuses to delete any balance, reservation, or movement row.

## Accounting equations

```text
available = on_hand - reserved

receipt / adjustment_in:
  on_hand += quantity

reserve:
  reserved += quantity

consume:
  reserved -= quantity
  on_hand -= quantity

release:
  reserved -= quantity

adjustment_out:
  allowed only when available >= quantity
  on_hand -= quantity
```

Each reservation separately satisfies:

```text
requested = remaining + consumed + released
active  <=> remaining > 0
closed  <=> remaining = 0
```

## Reconciliation query

Before staff API activation, recompute each fabric from ordered movements and
compare with `crm_material_balances`. At minimum verify:

```sql
SELECT fabric_id,
       on_hand_meters,
       reserved_meters,
       version
FROM crm_material_balances
ORDER BY fabric_id;

SELECT fabric_id,
       balance_on_hand_after,
       balance_reserved_after,
       id
FROM crm_material_movements
ORDER BY fabric_id, id;
```

For every fabric, the last movement balances must equal the projection. The
number of state-changing commands equals `balance.version - 1`; the initial
projection starts at version 1. Reservation sums must match the reserved
balance per fabric.

## Verification

- Ruff lint, format verification, and legacy-entrypoint syntax pass;
- all 269 backend unit/contract tests pass;
- tests prove exact receipt replay, changed-command key conflict, bounded
  reservation, protected reserved stock, consume/release accounting, closed
  reservation totals, ordered immutable movement balances, active-plan lock,
  and re-plan blocking until material release;
- Alembic has one linear `20260812_0024` head and full offline PostgreSQL
  upgrade/downgrade SQL compiles;
- database constraints cover balances, reservation equations/status, movement
  types, reservation linkage, command digests, and downgrade protection.

No live PostgreSQL was available for simultaneous reserve/adjust/re-plan races
or migration apply/downgrade. No API/RBAC path exists yet, so operator access,
request DTO, and browser verification remain for the staff cabinet stage.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Fabric reference, projection, reservation aggregate, movement ledger, and production plan have explicit ownership. |
| Security and audit | 20/20 | Raw idempotency keys are hashed; PII is absent; movements retain safe actor/reason evidence. |
| Reliability and accounting | 20/20 | Row locks, command fingerprints, equations, balance snapshots, plan pinning, and guarded rollback. |
| Compatibility | 20/20 | Additive private schema/service only; no current runtime path changes. |
| Verification | 14/20 | Full local/offline gate passes; live PostgreSQL races and staff API evidence remain. |
| Total | 94/100 | The bounded ledger exceeds the requested threshold without claiming production-grade staging proof. |

## Next bounded slice

1. Add a deterministic ledger replay/audit command and metrics for projection
   drift, negative availability attempts, and active reservation age.
2. Add private CRM MinIO storage metadata and bucket policy for patterns,
   tech-card sources, and production evidence.
3. Expose paginated staff reads and explicit commands behind `crm.access`, with
   idempotency, stale-version, negative RBAC, and PII-leak tests.
4. Build the manager cabinet only after real PostgreSQL and private MinIO
   staging checks pass.

## Rollback

Stop any future staff command path before rollback. Online downgrade of `0024`
refuses while any balance, reservation, or movement exists. Export and reconcile
the complete ordered ledger before removal. Production plans and fabric
reference data remain intact under revision `0023`.
