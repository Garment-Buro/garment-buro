# Stage 38: terminal CRM project reconciliation

Status: complete locally; live PostgreSQL lock-order contention pending

Quality score: 94/100

## Safety boundary

This stage enables `completed` and `cancelled` on the existing idempotent project
transition route. It does not add a bulk unit mutation or infer unit outcomes
from a project button. Units must already have passed their own guarded workflow
and material closure rules.

Terminal rules are strict and explicit:

```text
project completed <=> every expected unit is completed
project cancelled <=> every expected unit is cancelled
```

A mix of completed and cancelled units is not silently mapped to either state.
It remains a `409` until the product defines an explicit partial-completion
business state and its downstream payment, delivery, and reporting semantics.

## Delivered

- the aggregate guard lives in `CrmProjectService`, so direct/internal calls and
  the staff command route share the same rule;
- the existing project row/version/state-machine check runs before aggregate
  work;
- terminal transition locks every project unit in deterministic ID order;
- actual locked unit count must equal immutable `project.units_count` and may
  not be empty;
- completed requires every unit to be `completed`; cancelled requires every
  unit to be `cancelled`;
- active material reservations are selected across every plan revision of every
  project unit, locked in deterministic ID order, and block closure;
- project mutation, version increment, append-only status event, durable staff
  command completion, and transaction commit remain atomic;
- the command digest still covers actor, project, expected version, target
  status, and reason; an exact retry returns the original receipt after closure;
- failed aggregate checks roll back the newly acquired command, leaving no
  durable processing receipt or project change;
- no schema revision or new route was needed.

## Lock and decision sequence

```text
lock/acquire staff command by hashed Idempotency-Key
  -> lock project
  -> verify expected project version and allowed transition
  -> lock every project unit ordered by ID
  -> verify expected count and one exact terminal status
  -> lock active reservations for all unit plan revisions ordered by ID
  -> require no active reservation
  -> set terminal project state and closed_at
  -> append actor-bound project status event
  -> complete command receipt with new project version
  -> commit
```

The unit workflow already blocks terminal unit transitions while its active plan
has an open reservation. The project-level reservation scan is an intentional
second defense for imported, historical, or manually inconsistent evidence.

## Verification

- all 279 backend unit/contract tests pass with Ruff, format verification, and
  legacy-entrypoint syntax;
- ASGI tests prove early closure refusal, exact all-cancelled project closure,
  durable result version, replay, actor-bound project event, closed-project
  assignment refusal, and mixed/non-terminal unit refusal;
- domain tests prove all-completed closure and reject an artificially retained
  active reservation even when its unit is completed; explicit release then
  allows closure;
- unit-count mismatch remains a conflict before mutation;
- all previous assignment, planning, material, and file tests remain green;
- Alembic remains at one linear `20260812_0027` head and full offline PostgreSQL
  upgrade/downgrade SQL compiles;
- local and deployment Compose configurations still render.

No live PostgreSQL test exercised simultaneous last-unit transition, material
release, and project closure. SQLite contract tests and PostgreSQL SQL
compilation do not replace lock-wait/deadlock proof; `CRM_WRITES_ENABLED` remains
off outside staging rehearsal.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Aggregate invariant is in the domain service and reuses project/material repositories. |
| Security and audit | 20/20 | Existing RBAC/idempotency plus actor-bound immutable project event and no extra data exposure. |
| Reliability and data safety | 20/20 | Deterministic locks, version check, exact unit/count rule, reservation defense, atomic receipt/event. |
| Compatibility | 20/20 | Existing route/DTO/schema; only formerly blocked valid terminal commands are enabled. |
| Verification | 14/20 | Full local/offline gate passes; live PostgreSQL contention and operator flow remain. |
| Total | 94/100 | The terminal aggregate slice exceeds the threshold without overstating concurrency proof. |

## Staging concurrency rehearsal

1. Prepare one project whose last unit is in quality control and has an active
   material reservation.
2. Race consume/release, unit completion, and project completion from separate
   PostgreSQL transactions; verify closure succeeds only after both prior
   commits and no deadlock remains.
3. Race two project terminal commands with different keys and the same expected
   version; prove one success and one version conflict.
4. Retry the winning command with the same key/body; prove the exact receipt and
   one project event.
5. Repeat for all-cancelled and mixed completed/cancelled projects.
6. Inspect `pg_locks`, command rows, unit/project events, reservations, and
   aggregate versions after each run.

## Next bounded slice

1. Add read-only CRM reconciliation checks for project/unit counts, event
   versions, material projection drift, attachment/object evidence, and stuck
   commands.
2. Expose only safe health summaries/metrics needed by staging operations; keep
   repair actions explicit and offline until their rules are proven.
3. Run full PostgreSQL/MinIO staging rehearsal before manager cabinet and PWA
   integration.

## Rollback

Set `CRM_WRITES_ENABLED=false` and restart. No schema rollback is required. Do
not reopen terminal projects by direct SQL or delete command/events. If a closed
aggregate is disputed, preserve all evidence and design an explicit audited
compensation command rather than mutating historical rows.
