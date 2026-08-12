# Stage 34: idempotent CRM staff lifecycle commands

Status: complete locally; live PostgreSQL concurrency and terminal project aggregation pending

Quality score: 94/100

## Safety boundary

This stage enables only assignment and non-terminal lifecycle commands. It adds
a second default-off flag, `CRM_WRITES_ENABLED`, which cannot be enabled unless
the read-only `CRM_API_ENABLED` boundary is already active. Every command uses
the target bearer identity and `crm.access` dependency from stage 33.

Commands never return an ORM entity. They return a durable receipt containing
the command ID/type, target ID, and result aggregate version. The cabinet must
then re-read the target DTO. This makes an exact retry return the original
receipt even when the target has advanced again.

Planning, material ledger commands, reference-data writes, private files, and
terminal project completion/cancellation remain outside this slice.

## Delivered

- revision `20260812_0026` adds durable staff command receipts and append-only
  project/unit assignment events;
- `CRM_WRITES_ENABLED=false` in settings, example environment, and both Compose
  variants;
- guarded write-router registration independent from the CRM read router;
- global CRM `Idempotency-Key` contract: 16-128 allowlisted characters;
- only SHA-256 of the normalized key and canonical command bytes are persisted;
  raw keys and request bodies are not stored;
- an atomic insert-on-conflict command acquisition runs in the same transaction
  as the target row lock, version check, domain mutation, audit event, and
  completed receipt;
- a crash or validation/domain failure rolls back the processing receipt and the
  target change together; no partially committed `processing` command is part
  of the intended state;
- exact retry returns the original receipt; the same key with a different actor,
  target, expected version, status, assignee, or reason fails with `409`;
- project and unit assignment require `expected_version`, reason code, actor,
  and a changed assignee;
- a non-null assignee must be an active target user with `crm.access`, preventing
  customer or disabled accounts from becoming production assignees;
- closed projects/units cannot be reassigned; unassignment remains explicit and
  audited;
- assignment events record one exact target, aggregate version, previous/new
  assignee, reason, actor, and time; database constraints reject unchanged
  assignments, including null-to-null;
- unit status transitions reuse the pinned production workflow and its allowed
  state machine;
- completion/cancellation of a unit now refuses while its active plan has an
  open material reservation, preventing terminal work with stranded stock;
- project completion/cancellation through HTTP is deliberately refused until a
  later aggregate rule can prove every unit and material reservation is in the
  correct terminal state;
- online downgrade refuses to remove assignment/command evidence.

## HTTP contract

```text
Idempotency-Key: 16..128 characters from A-Z a-z 0-9 . _ ~ : -
Authorization: Bearer <target identity access token>

PUT   /api/crm/projects/{project_id}/assignment
PATCH /api/crm/projects/{project_id}/status
PUT   /api/crm/units/{unit_id}/assignment
PATCH /api/crm/units/{unit_id}/status
```

Assignment body:

```json
{
  "expected_version": 3,
  "assigned_to_user_id": 17,
  "reason_code": "manager_assigned"
}
```

Use `null` as the assignee only for an explicit unassignment. Transition bodies
contain `expected_version`, enum `to_status`, and a lower-snake-case reason.

Successful receipt:

```json
{
  "command_id": 42,
  "command_type": "unit.transition",
  "target_id": 81,
  "result_version": 6
}
```

Error mapping is intentionally small: missing/invalid target is `404`, malformed
idempotency key is `400`, request validation is `422`, and stale version,
invalid transition, ineligible/unchanged assignment, processing/conflicting
key, unsafe material closure, or terminal project request is `409`.

## Transaction model

```text
hash idempotency key + canonical command
  -> INSERT command(status=processing) ON CONFLICT DO NOTHING
  -> lock and verify acquired command
  -> exact completed match? return stored receipt
  -> changed command? conflict
  -> lock target aggregate
  -> verify expected_version and domain state
  -> mutate aggregate + increment version
  -> append domain/assignment event
  -> mark command completed with result_version
  -> COMMIT all rows together
```

The database unique key is global to CRM commands. Clients must create a fresh
key for every intended command and retain it across timeouts/retries.

## Verification

- Ruff lint, format verification, and legacy-entrypoint syntax pass;
- all 276 backend unit/contract tests pass;
- ASGI tests prove write routes are independently default-off, `401/403`, missing
  key validation, exact receipt replay before and after later target changes,
  changed-command key conflict, stale version, active-CRM assignee requirement,
  assignment/unassignment audit, closed-target protection, invalid key, and
  failed-command rollback;
- persistence tests prove raw idempotency keys are absent, both digests are 64
  characters, actor evidence is present, completed status is durable, and the
  database rejects null-to-null assignment events;
- production workflow tests prove active material reservations block terminal
  unit transition;
- local and deployment Compose configurations render with both CRM flags;
- Alembic has one linear `20260812_0026` head and full offline PostgreSQL
  upgrade/downgrade SQL compiles.

No live PostgreSQL contention test was available for simultaneous reuse of one
key or simultaneous commands against one aggregate. SQLite/ASGI contract tests
and PostgreSQL SQL compilation do not replace that proof. Writes remain disabled
outside an isolated staging rehearsal.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Separate flag/router, explicit command service/repository/models, durable receipts, and existing domain services. |
| Security and audit | 20/20 | Target identity/RBAC, hashed keys/commands, actor evidence, eligible assignees, and no request/PII persistence. |
| Reliability and data safety | 20/20 | Atomic acquisition, target locks, expected versions, exact replay, rollback semantics, constraints, and material closure guard. |
| Compatibility | 20/20 | Additive schema and routes; all writes are absent while the second flag is false. |
| Verification | 14/20 | Full local/offline gate passes; live PostgreSQL race, proxy, and browser proof remain. |
| Total | 94/100 | The bounded command slice exceeds the threshold without claiming production concurrency proof. |

## Staging activation checklist

1. Keep `CRM_WRITES_ENABLED=false`, apply `0026`, and verify the read API first.
2. Seed/review manager roles and confirm every eligible assignee has active
   `crm.access`.
3. Run two PostgreSQL transactions concurrently with the same key/same payload;
   prove one mutation and the same receipt.
4. Repeat with the same key/different payload and with two different keys against
   the same expected version; prove one success and one conflict.
5. Kill one request before commit and prove retry creates exactly one completed
   command with no durable processing row.
6. Verify command/event/aggregate versions using SQL and ensure proxy logs never
   contain Authorization or Idempotency-Key values.
7. Enable writes for one staging manager and exercise assignment, unassignment,
   project hold/resume, unit start/QC/complete, and unit cancellation with open
   versus closed material reservations.

## Next bounded slice

1. Add idempotent production planning commands that pin a published tech-card
   revision and stable size through the existing plan service.
2. Add material receipt/reserve/consume/release/adjust commands while preserving
   the ledger's existing per-fabric idempotency contract.
3. Add aggregate terminal project reconciliation after unit/material rules are
   explicit and tested.
4. Add private CRM file upload/download routes with multipart limits and audited
   signed-link issuance.

## Rollback

Set `CRM_WRITES_ENABLED=false` and restart before any rollback work. Do not
delete command rows or assignment events to make a downgrade pass. Export and
reconcile every command receipt against the corresponding aggregate version and
domain event. Online downgrade of `0026` refuses while evidence exists; the
read-only stage 33 remains available under `0025` if its separate flag stays on.
