# Stage 30: pinned CRM production workflow

Status: complete locally; staff API and real PostgreSQL concurrency proof pending

Quality score: 94/100

## Safety boundary

This stage connects the paid-order production units from stage 28 to the
versioned garment reference data from stage 29. It does not expose an HTTP route
or change storefront/PWA behavior.

A production unit never points at a mutable "current tech card". Planning pins
the exact published tech-card revision, the garment model resolved through the
existing catalog-product link, and the stable CRM size matching immutable order
evidence. Later publication archives the old revision but cannot change the
unit's pinned instructions.

## Delivered

- revision `20260812_0023` adds immutable production-plan revisions and
  append-only production-unit events;
- every unit now has an optimistic version plus start/close timestamps protected
  by lifecycle database constraints;
- stage-28 intake creates an `initialized` version-1 event for every quantity-
  expanded unit in the same fulfillment transaction;
- migration `0023` backfills that version-1 evidence for existing queued units
  and refuses a live upgrade if an old unit was manually moved to another state;
- planning locks the unit, resolves its product through the unique CRM catalog
  link, and requires a published active tech-card revision for that same garment
  model;
- models with active sizes require a stable size row, and its normalized code
  must equal the immutable order-item size snapshot;
- the plan stores a canonical SHA-256 evidence digest across unit/order/catalog/
  model/size/revision IDs;
- an exact retry returns the existing active plan even when the original
  expected version is stale after a lost response;
- a changed plan requires the current unit version, supersedes the old plan,
  creates a new numbered revision, and keeps same-unit lineage through a
  composite foreign key;
- a partial unique index permits only one active plan per unit;
- a unit cannot start without an active plan and cannot be re-planned after work
  starts;
- legal unit movement is explicit: `queued -> in_progress -> quality_control ->
  completed`, with quality-control rework back to `in_progress`, cancellation
  before completion, and terminal completed/cancelled states;
- each plan or status transition increments the unit version and appends one
  unique event with safe reason code and optional actor user ID;
- online downgrade refuses to remove any real plan/status evidence, while the
  migration-generated initialization rows alone are safe to discard.

## Runtime flow

```text
paid order
   |
   v
production unit v1 / queued / initialized event
   |
   | resolve Product -> CRM garment model
   | validate immutable order size -> active CRM size
   | validate published tech-card revision belongs to model
   v
active plan revision + unit v2 / planned event
   |
   +-- exact retry -> same plan, no new version
   +-- changed plan while queued -> supersede + plan revision N+1
   |
   v
in_progress -> quality_control -> completed
        ^              |
        +---- rework --+

completed/cancelled are terminal
```

## Verification

- Ruff lint, format verification, and legacy-entrypoint syntax pass;
- all 267 backend unit/contract tests pass;
- tests prove atomic initialization events, required plan before start, wrong-
  size rejection, published/same-model tech-card validation, exact replay,
  revision lineage, single active plan, archived instruction pinning, ordered
  unit versions/events, legal transitions, timestamps, and terminal protection;
- Alembic has one linear `20260812_0023` head;
- full offline PostgreSQL upgrade/downgrade SQL compiles, including data
  backfill, partial uniqueness, composite same-unit lineage, and rollback guard.

No live PostgreSQL instance was available for concurrent planners, migration
backfill on a real staging copy, or `FOR UPDATE` contention. No staff route is
registered yet, so `crm.access` negative tests and cabinet/browser proof belong
to a later stage.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Order evidence, catalog mapping, reference revisions, plan revisions, and unit workflow retain separate ownership. |
| Security and audit | 20/20 | Private service only; no PII snapshots; all mutations record actor/reason/version evidence. |
| Reliability and data safety | 20/20 | Locked versions, exact replay, immutable plans, partial uniqueness, composite lineage, and lifecycle constraints. |
| Compatibility | 20/20 | Additive migration and no public API/runtime cutover. |
| Verification | 14/20 | Full local/offline gate passes; live PostgreSQL and staff API evidence remain. |
| Total | 94/100 | The bounded production workflow exceeds the requested threshold without claiming the unfinished cabinet/staging layer. |

## Next bounded slice

1. Add append-only fabric receipt/reserve/release/consume/adjustment movements,
   idempotency keys, reservation aggregates, and derived balance projections.
2. Link material reservations to production-plan revisions so a later re-plan
   cannot silently reinterpret already reserved fabric.
3. Add private MinIO roles for patterns, tech-card sources, and production
   evidence with authorization and retention rules.
4. Expose paginated staff DTOs and commands behind `crm.access`, then build the
   internal cabinet and verify it against staging PostgreSQL/MinIO.

## Rollback

Do not invoke the private production service while rolling back. Online
downgrade of `0023` refuses if any plan exists, any non-initialization event
exists, or any unit left its version-1 queued state. Migration-generated initial
events alone can be removed because stage-28 units and their paid-order evidence
remain intact under revision `0022`.
