# Stage 42: staging PostgreSQL/MinIO rehearsal preflight

Status: tooling and runbook complete locally; live staging execution pending

Quality score: 92/100

## Scope

This stage turns the accumulated staging requirements into one safe preflight
command plus an ordered operator runbook. It does not deploy, migrate, seed,
grant roles, or enable flags automatically.

From `backend/` with the reviewed deployment environment loaded:

```bash
.venv/bin/python -m scripts.rehearse_staging
.venv/bin/python -m scripts.rehearse_staging --require-database-tls
.venv/bin/python -m scripts.rehearse_staging --storage-roundtrip
.venv/bin/python -m scripts.rehearse_staging \
  --require-crm-writes \
  --require-crm-files \
  --storage-roundtrip
```

Exit codes are stable:

```text
0 = every requested safety check passed
1 = configuration, schema, role, policy, or requested-flag drift found
2 = preflight could not inspect the environment safely
```

The output never contains a database DSN, database/user name, bucket name,
object key, access key, secret key, signed URL, customer data, or raw provider
error. It contains only the expected environment/head, PostgreSQL version/TLS
boolean, roundtrip status, and stable issue codes.

## Automated checks

### PostgreSQL

- the loaded environment exactly matches `staging` by default;
- the target URL is PostgreSQL, not SQLite;
- the database reports the one repository Alembic head and no second head;
- the connection is not default read-only and is not a recovery replica;
- the application database role is not a PostgreSQL superuser;
- backend/identity/CRM read flags required for the cabinet are enabled;
- optional flags require CRM writes/files at the relevant rehearsal step;
- `--require-database-tls` proves TLS on this exact backend connection.

The TLS option is mandatory when the database crosses an untrusted network. A
private workload network may use a separately reviewed encryption boundary;
record that decision rather than silently omitting the check.

### MinIO/S3

- both environment-derived media and CRM-private buckets exist and are
  reachable with application credentials;
- any public-principal `Allow` or `Allow` with `NotPrincipal` in the CRM-private
  bucket policy fails preflight;
- malformed policy JSON fails inspection rather than being assumed private;
- public application and object URLs are HTTPS.

The policy check is deliberately conservative: a public principal with a
restrictive condition still requires a human security review rather than
passing automatically.

`--storage-roundtrip` is the only write in the tool. It creates a random object
under `rehearsal/private/`, verifies `stat`, requires an HTTPS signed URL with a
query signature, removes the exact object in `finally`, and confirms absence.
Production refuses this option unless
`--allow-production-storage-roundtrip` is also present.

## Ordered staging rehearsal

### 1. Freeze a release candidate

1. Record the Git commit, container image digests, Python lock/requirements
   hash, frontend build flags, and single Alembic head.
2. Run local gates from the exact release worktree:

   ```bash
   cd backend
   make PYTHON=.venv/bin/python check
   cd ../frontend
   npm run check
   ```

3. Render deployment configuration without printing resolved secret values into
   an artifact or ticket.
4. Keep CRM writes/files and every payment/CDEK worker off for the first boot.

### 2. Prove backup and restore before migration

Use a PostgreSQL service definition or secret manager injection so passwords do
not appear in shell history or process arguments. On a disposable staging
restore target:

```bash
PGSERVICE=garment-staging-source pg_dump --format=custom --no-owner \
  --file=garment-staging-before-refactor.dump
PGSERVICE=garment-staging-restore pg_restore --clean --if-exists --no-owner \
  --dbname=garment_staging_restore garment-staging-before-refactor.dump
```

1. Store the dump encrypted with retention/ownership recorded.
2. Compare source/restore table counts using reviewed aggregate queries; never
   attach rows containing PII to the release record.
3. Record restore duration and prove an application connection to the restored
   target.
4. Confirm object-store versioning/snapshot/replication and perform a documented
   restore of one disposable media object.
5. Do not proceed if there is no tested database and object recovery path.

### 3. Rehearse migrations on the disposable restore

Load the same staging secret/config source that the release will use, pointed at
the restored database:

```bash
.venv/bin/python -m alembic -c alembic.ini current
.venv/bin/python -m alembic -c alembic.ini heads
.venv/bin/python -m alembic -c alembic.ini upgrade head
.venv/bin/python -m scripts.rehearse_staging
```

Record migration duration, locks/waits, database size before/after, and the
preflight JSON. Review application tables and immutable migration evidence.

Downgrade is not the normal production rollback because later revisions remove
tables/evidence. If rollback SQL must be rehearsed, restore another disposable
copy, run only the reviewed downgrade target, inspect data loss, then destroy
that copy. Never downgrade the only staging/production target to recover an
application release.

### 4. Provision and verify object storage

1. Create the exact environment-derived media and CRM-private buckets.
2. Make only the storefront media policy public as required; keep CRM-private
   without anonymous list/get/put/delete.
3. Configure lifecycle/versioning/retention and backup ownership.
4. Run:

   ```bash
   .venv/bin/python -m scripts.rehearse_staging --storage-roundtrip
   .venv/bin/python -m scripts.reconcile_crm --verify-objects
   ```

5. From an unauthenticated network client, prove a known CRM object/key cannot
   be listed or downloaded. Then authenticate as a manager, request a short
   signed download, prove expiry, and retain only status/timing evidence—not the
   URL or filename.

### 5. Boot the read-only application cutover

Initial coordinated flags:

```dotenv
DATABASE_ENABLED=true
MINIO_ENABLED=true
IDENTITY_API_ENABLED=true
CRM_API_ENABLED=true
CRM_WRITES_ENABLED=false
CRM_FILES_ENABLED=false
NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=true
NEXT_PUBLIC_CRM_CABINET_ENABLED=true
```

Keep catalog/cart/order/payment/fulfillment flags at their previously reviewed
state; do not infer migration fingerprints. Deploy backend before the rebuilt
frontend, then verify:

```text
GET /health/live  -> 200 {status: ok}
GET /health/ready -> 200 {status: ready, database: postgresql, storage: minio}
```

Run preflight and CRM reconciliation again from the running release environment.
Confirm logs redact cookies, bearer tokens, OTPs, DSNs, provider keys, signed
URLs, filenames, and customer fields.

### 6. Identity/RBAC and cabinet acceptance

1. Create disposable customer and staff identities through normal staging auth.
2. Inspect the intended manager grant before applying it:

   ```bash
   .venv/bin/python -m scripts.bootstrap_role \
     --email '<reviewed-staff-email>' --role manager
   ```

3. Compare the returned numeric user ID with the reviewed identity, then apply
   using `--apply --expect-user-id <id>`.
4. Prove customer `/api/auth/access` lacks `crm.access` and all CRM endpoints
   return 403; prove manager access contains it and project reads return 200.
5. In desktop web and installed PWA, verify login, refresh rotation, reload,
   offline/online recovery, multi-tab state, logout, navigation visibility,
   pagination, empty/error states, and no token/permission persistence.
6. Remove the manager role in staging and prove backend denial immediately; UI
   navigation may remain visible for at most its 60-second in-memory projection
   TTL but must never receive CRM data.

### 7. Controlled write/file rehearsal

Enable one backend layer at a time; rebuild of the current read-only frontend is
not required because it exposes no command UI:

```dotenv
CRM_WRITES_ENABLED=true
CRM_FILES_ENABLED=false
```

Run preflight with `--require-crm-writes`. Through reviewed API tooling, prove
exact retry, changed-payload idempotency conflict, expected-version conflict,
concurrent assignment/status, plan/material reserve-consume-release, terminal
project reconciliation, immutable receipts, and final healthy CRM reconciliation.

Then enable files:

```dotenv
CRM_FILES_ENABLED=true
```

Run preflight with `--require-crm-writes --require-crm-files
--storage-roundtrip`. Prove supported upload sniffing, oversize/unsupported
rejection, exact replay, changed-file conflict, signed download, anonymous
denial, expiry, object presence, and reconciliation. Use disposable evidence
only and remove it through an explicit reviewed cleanup path; never delete
immutable audit rows to make a check green.

### 8. Payment, fulfillment, email, and CDEK gates

Keep each worker disabled until its own dependency check passes:

1. run the SMTP connectivity check, then prove one encrypted outbox OTP and one
   fulfillment email reaches a controlled staging mailbox without logging
   payload or recipient;
2. use YooKassa sandbox credentials to prove canonical persisted creation,
   unknown-outcome retry with the same provider key, webhook redelivery,
   reconciliation, success/cancel, receipt fields, and no duplicate inventory
   consumption;
3. enable fulfillment outbox only after payment success evidence is stable;
4. use CDEK sandbox/test credentials to prove exact request persistence,
   creation retry, remote lookup/reconciliation, label/tracking state, and no
   duplicate shipment;
5. finally prove a paid order produces exactly one CRM project and expected
   units without storing customer PII in CRM.

Provider responses and live credentials must never be copied into this document
or CI logs. Record safe IDs only where the provider contract requires them and
retain them in the appropriate encrypted operational system.

### 9. Observation and production decision

Record readiness/reconciliation status, 4xx/5xx rates, pool usage, slow queries,
outbox backlog/age, payment/CDEK retry age, storage failures, browser/PWA errors,
and backup freshness over the agreed staging window. Establish thresholds from
the observed baseline before enabling alerts.

Production promotion requires a reviewed checklist with owner, time window,
backup reference, image digests, exact flags/fingerprints, provider modes,
rollback decision points, and a second operator. Re-run the read-only preflight
with `--expect-environment production`; use production storage roundtrip only if
the change record explicitly authorizes its second guard.

## Rollback order

1. Stop CRM files/writes, checkout/payment creation, payment/CDEK/fulfillment
   workers, and other mutation producers first.
2. Set `NEXT_PUBLIC_CRM_CABINET_ENABLED=false`, rebuild frontend, and retain the
   backend read API for diagnosis if safe.
3. Roll traffic back to the previous application images without downgrading the
   migrated database.
4. Preserve PostgreSQL, MinIO objects, outbox rows, idempotency records,
   immutable events, reconciliation output, and provider IDs.
5. Reconcile every accepted/unknown provider outcome before re-enabling a
   previous writer; use the same canonical request bytes/key for unknown
   payment/CDEK outcomes.
6. Restore PostgreSQL/object backups only for a declared data-loss disaster,
   with writes stopped and a forward reconciliation/import plan. A restore is
   not an ordinary code rollback.

## Verification

- positive tests prove a safe report, private object put/stat/signed/delete
  roundtrip, cleanup, and output redaction boundaries;
- drift tests prove schema mismatch, default read-only, superuser, missing TLS,
  disabled required flags, and public private-bucket policy detection;
- policy tests cover no policy, named principals, wildcard lists,
  `NotPrincipal`, and malformed statements;
- production storage mutation requires the second explicit guard;
- CLI help is executable and documents every guard;
- all 285 backend tests, Ruff lint/format, legacy syntax, and the full offline
  PostgreSQL Alembic upgrade/downgrade chain pass;
- frontend remains green at 201 tests, ESLint, and production build from the
  preceding guarded-cabinet stage;
- both Compose files render successfully (warnings only reflect absent local
  secrets).

No live staging database, object store, backup restore, migration duration,
authenticated cabinet, provider sandbox, SMTP mailbox, or deployed rollback was
available in this environment. This stage makes those checks reproducible; it
does not count them as passed.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Repository/service/CLI split with stable safe report and explicit mutation guard. |
| Security | 20/20 | Least-privilege DB check, conservative private policy, redacted output, production double guard. |
| Reliability | 19/20 | Schema/primary/read-write/storage checks, cleanup in finally, ordered restore/rollback procedure. |
| Compatibility | 19/20 | Additive operator tooling; existing runtime flags and APIs unchanged. |
| Verification | 15/20 | Full local backend/frontend/offline/Compose gates pass; real staging remains unavailable. |
| Total | 92/100 | The rehearsal is executable and guarded while live evidence is stated as pending. |
