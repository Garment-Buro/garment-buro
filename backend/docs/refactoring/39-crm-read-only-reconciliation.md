# Stage 39: read-only CRM reconciliation

Status: complete locally; live PostgreSQL/MinIO baseline and scheduler pending

Quality score: 93/100

## Safety boundary

This stage adds an operator inspection command, not an automatic repair worker.
It never updates project, unit, material, command, media, attachment, or object
state. A drift report is evidence for investigation; correction still requires
an explicit domain command or a reviewed offline procedure.

The command returns only safe issue codes, entity kinds, numeric IDs, aggregate
counts, and timestamps. It never renders customer/order PII, actor email,
filename, bucket/object key, checksum, signed URL, idempotency key, or command
digest.

## Command

From `backend/` with the target environment loaded:

```bash
.venv/bin/python -m scripts.reconcile_crm
.venv/bin/python -m scripts.reconcile_crm --verify-objects
```

Options:

- `--verify-objects` performs a MinIO `stat` for every ready attachment and
  requires `MINIO_ENABLED=true`;
- `--max-issues` bounds rendered issue examples from 1 to 10,000 while retaining
  the exact total issue count;
- `--stale-after-seconds` controls stale pending-media/processing-command
  detection and cannot be below 60 seconds.

Exit codes are operationally stable:

```text
0 = healthy
1 = reconciliation drift found
2 = configuration, database, or storage inspection failure
```

Database failures return a generic JSON error so DSNs and driver details are
not printed by this command.

## Checks

### Project and unit aggregates

- project unit count and distinct order-item count match immutable aggregate
  counters;
- project status events plus project assignment events cover every aggregate
  version exactly once;
- unit workflow events plus unit assignment events cover every unit version
  exactly once;
- latest status and assignment evidence matches each current aggregate;
- completed/cancelled projects contain only the exact matching terminal unit
  status;
- in-progress, quality-control, and completed units have exactly one active
  pinned plan;
- terminal projects/units have no active material reservation.

### Material accounting

- every fabric with movement/reservation state has a balance projection;
- ordered movements replay from zero using the receipt/reserve/consume/release/
  adjustment equations, and every immutable after-snapshot matches replay;
- final replayed balances equal the current projection;
- balance version equals movement count plus the initial projection version;
- active reservation remaining sums equal reserved balance by fabric;
- reserve/consume/release movement totals equal each reservation's requested,
  consumed, and released fields.

### Private files

- attachments point to ready, non-public media in the exact environment CRM
  private bucket;
- ready private media has an attachment;
- pending private media older than the threshold is reported;
- optional object verification confirms each attachment object exists;
- missing individual objects are drift; bucket/API failure is a separate
  infrastructure error rather than thousands of false missing-object issues.

### Staff commands

- durable `processing` staff commands older than the threshold are reported as
  stuck. Completed row shape remains enforced by database constraints.

## Snapshot and output guarantees

On PostgreSQL the inspector must be the first operation in its session. It sets
`REPEATABLE READ` and `READ ONLY` before loading data, preventing one report from
mixing rows committed at different points in time. SQLite tests run in one read
transaction.

Issue output is deterministic by table/entity order. If examples are truncated,
`total_issues` remains exact and `issues_truncated=true` is explicit. Object
verification is labeled `performed` or `skipped` in every report.

The current implementation loads the full CRM reconciliation domain into one
consistent snapshot. That favors cross-table correctness for the current data
volume. Before CRM reaches high-volume history, replace the repository load
with repeatable-read keyset batches and database-side aggregate checks while
preserving the same report contract.

## Verification

- all 281 backend unit/contract tests pass with Ruff, format verification, and
  legacy-entrypoint syntax;
- a complete production-plan/material/project workflow reconciles healthy;
- a drift fixture proves project terminal mismatch, material version drift,
  missing private object, orphan/stale private media, and stuck command
  detection;
- the drift test proves the inspector leaves application rows byte-for-byte
  unchanged and omits private filename from output;
- bounded issue examples preserve the exact total and truncation marker;
- MinIO tests prove private object existence before removal and absence after
  removal;
- CLI argument/help contract executes successfully;
- Alembic remains at one linear `20260812_0027` head and full offline PostgreSQL
  upgrade/downgrade SQL compiles;
- deployment and local Compose configurations render.

No live repeatable-read PostgreSQL run, real MinIO `stat`, large-history memory/
duration measurement, monitoring integration, or scheduled execution was
available. The command should first run manually in staging and its baseline
report should be reviewed before any scheduler treats exit code 1 as an alert.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Separate repository/service/CLI and stable safe report; full-snapshot loading still needs batching at scale. |
| Security and audit | 20/20 | Read-only transaction, no repair path, no PII/secrets/object identifiers in output. |
| Reliability and data safety | 20/20 | Repeatable-read snapshot, deterministic ledger replay, cross-table version/aggregate checks, infra/drift separation. |
| Compatibility | 20/20 | No schema/API/runtime flag changes; operator command is additive. |
| Verification | 14/20 | Full local/offline gate passes; live PostgreSQL/MinIO, scale, and monitoring evidence remain. |
| Total | 93/100 | The operational inspection slice exceeds the threshold without overstating staging proof. |

## Staging baseline

1. Run without object checks; archive the safe JSON report and investigate every
   issue before enabling CRM writes.
2. Run with `--verify-objects`; separately confirm private bucket readiness and
   anonymous/CDN denial.
3. Record duration, peak memory, row counts, and PostgreSQL snapshot age.
4. Create one disposable issue of each category, prove the expected nonzero
   exit/report, remove it through normal domain cleanup, and prove health.
5. Run during controlled CRM writes to validate repeatable-read behavior and
   acceptable database load.
6. Only then add a scheduler/monitor with alert deduplication and retained safe
   output; never attach raw SQL dumps or object URLs to alerts.

## Next bounded slice

1. Build a repeatable staging rehearsal script/runbook for migrations, CRM
   concurrency, private MinIO policy, reconciliation, and rollback flags.
2. Add safe metrics after the first real baseline establishes useful thresholds.
3. Begin manager cabinet/frontend integration only against staging-verified API
   contracts and default-off production flags.

## Rollback

Remove the scheduled invocation or stop running the CLI; it has no durable state
and no schema rollback. Do not respond to drift by editing projections or event
history directly. Preserve the report and reconcile against immutable evidence
before designing an explicit compensation.
