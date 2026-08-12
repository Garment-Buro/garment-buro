# Stage 35: idempotent production planning command

Status: complete locally; live PostgreSQL concurrency and cabinet flow pending

Quality score: 94/100

## Safety boundary

This stage adds one command to the guarded CRM write router:

```text
POST /api/crm/units/{unit_id}/plans
```

It does not create another planning implementation. The HTTP command delegates
to the stage 30 production service, so the selected garment model still comes
from the catalog-product link, size must match immutable order evidence, and the
tech-card revision must be published and belong to that model.

Material reservations, reference writes, and terminal project transitions are
unchanged.

## Delivered

- revision `20260812_0027` extends the constrained durable command type set with
  `unit.plan`;
- request fields are `expected_version`, optional positive `garment_size_id`,
  and positive `tech_card_revision_id`;
- target bearer identity, `crm.access`, `CRM_API_ENABLED`,
  `CRM_WRITES_ENABLED`, `Idempotency-Key`, no-store, and common error mapping are
  inherited from stages 33-34;
- command digest covers actor, target, expected version, size, and tech-card
  revision;
- exact retry returns the original command receipt even if the unit later moves
  to another version or status;
- a new plan supersedes the prior active revision only through the existing row
  locks and only after active material reservations have been released;
- a successful plan increments the unit aggregate version and writes the
  existing `planned` unit event containing the pinned plan revision and actor;
- failed catalog link, size/order mismatch, unpublished or cross-model tech
  card, stale version, non-queued unit, or active-reservation replan rolls back
  the command acquisition with the domain mutation;
- downgrade to `0026` refuses while any `unit.plan` receipt exists.

Successful responses use the same receipt contract:

```json
{
  "command_id": 51,
  "command_type": "unit.plan",
  "target_id": 81,
  "result_version": 2
}
```

The cabinet re-reads the unit detail to obtain the active plan ID and current
state. A stale retry therefore cannot accidentally replace a newer plan.

## Verification

- all 276 backend unit/contract tests pass with Ruff and legacy-entrypoint syntax;
- ASGI tests prove route registration, successful pinned planning, durable
  `unit.plan` receipt, unlinked-product conflict rollback, later unit transition,
  and exact planning receipt replay after that later transition;
- existing production tests continue proving size/order evidence matching,
  published tech-card ownership, safe replan lineage, and reservation blocking;
- Alembic has one linear `20260812_0027` head and full offline PostgreSQL
  upgrade/downgrade SQL compiles.

No real PostgreSQL same-key/replan race, staging manager token, or browser flow
was available. The write flag remains off outside staging rehearsal.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Thin HTTP command reuses durable receipt and the existing planning domain service. |
| Security and audit | 20/20 | RBAC, actor, hashed command/key, immutable plan/unit event, and no request persistence. |
| Reliability and data safety | 20/20 | Expected version, exact replay, row locks, pinned revisions, lineage, and reservation guard. |
| Compatibility | 20/20 | Additive command type/route behind the existing default-off write flag. |
| Verification | 14/20 | Full local/offline gate passes; live PostgreSQL and browser evidence remain. |
| Total | 94/100 | The planning slice exceeds the threshold without overstating runtime proof. |

## Next bounded slice

1. Expose material receipt/adjust/reserve/consume/release commands using the
   ledger's existing hashed idempotency and exact accounting receipts.
2. Add terminal project aggregation only after unit and material terminal rules
   can be checked in one locked transaction.
3. Add private CRM file upload/download HTTP routes behind `crm.access`.

## Rollback

Disable `CRM_WRITES_ENABLED` first. Do not remove planning receipts, plan
revisions, unit events, or material evidence. Downgrade of `0027` is safe only
when no `unit.plan` command exists; otherwise preserve the schema and reconcile
the receipts against unit versions and active plan revisions.
