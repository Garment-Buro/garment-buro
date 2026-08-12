# Stage 4: deterministic catalog migration and guarded read cutover

Status: complete for the branch

Quality score: 94/100

## Delivered

- a read-only SQLite catalog planner with explicit schema validation;
- deterministic extraction of products, variants, ordered media roles, and
  local `/uploads/` objects;
- validation for negative values, missing product references, duplicate variant
  identities, unsafe paths, missing files, unsupported media, and invalid scalar
  media cardinality;
- content-derived MIME, stored-byte SHA-256, byte size, target key, unused-file
  reporting, and a source plan fingerprint;
- the fingerprint covers every product/variant value, media reference, object
  checksum, error, and warning, not only aggregate counts;
- `--apply` requires the reviewed dry-run fingerprint, rebuilds the current
  plan, and refuses changed sources or a non-empty target;
- every object is re-read and rechecked immediately before MinIO upload;
- current `/uploads/<filename>` keys are preserved in MinIO, so response values
  do not change;
- explicit PostgreSQL sequence synchronization after preserving legacy IDs;
- a `catalog_migration_runs` audit row with fingerprint and all cutover counts;
- runtime startup guard: catalog reads cannot enable without an exact applied
  fingerprint and matching product, variant, ready-media, and link counts;
- repository/service/response-mapper GET path behind `CATALOG_READS_ENABLED`;
- current list ordering, nullable fields, numeric values, CSV media lists,
  variants, `404`, and `/api/products` paths preserved;
- `/uploads/{filename}` immutable redirect to the corresponding MinIO object;
- POST/PUT/DELETE continue through the mounted legacy app during this read-only
  cutover slice;
- configuration-only rollback to legacy reads;
- migration code split into typed planning, application, comparison, and data
  modules instead of one new monolith.

## Current source snapshot evidence

A read-only dry-run against the developer SQLite database and uploads directory
completed successfully on 2026-08-11:

| Check | Result |
| --- | ---: |
| Products | 4 |
| Variants | 14 |
| Media references | 69 |
| Unique referenced assets | 69 |
| Missing/unsupported assets | 0 |
| Unused local upload files | 69 |
| Plan fingerprint | `01e023f42d9d98def691722b53b6f7cf43e872c754b01e210524c920982f0e81` |

The unused files are retained. They are mostly original PNG/JPG files next to
the referenced WebP versions, plus other unreferenced local artifacts. Nothing
in the planner or importer deletes source data.

The fingerprint is snapshot-specific. Any catalog field, media reference,
checksum, missing/unused file set, error, or warning change produces a different
fingerprint and requires a new review.

## Compatibility evidence

The comparison tool imported the current snapshot into an isolated temporary
database using the same ORM/service/mapper path and a no-network object-storage
double. Results:

- list responses compared: 4;
- detail responses compared: 4;
- products migrated: 4;
- variants migrated: 14;
- assets/references migrated: 69/69;
- field/value/order mismatches: 0.

An HTTP contract test separately proves that the feature-flagged FastAPI router
returns the legacy list/detail/404 shapes, redirects old upload URLs to MinIO,
and still routes catalog POST requests to legacy.

## Verification

- `make -C backend check PYTHON=../.venv/bin/python`: passed;
- Ruff lint and format checks: passed;
- all unit/contract/auth/storage/database/migration tests: 57 passed;
- offline Alembic upgrade through `20260811_0003`: passed;
- offline downgrade from head to base: passed;
- focused planner/importer/HTTP cutover tests: passed;
- actual read-only dry-run: valid, no errors;
- actual snapshot service comparison: zero mismatches;
- local and production Compose configuration validation: passed;
- source SQLite read-only behavior and fingerprint change detection: tested.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 24/25 | GET follows router/service/repository/mapper and migration responsibilities are split; catalog writes intentionally remain legacy. |
| Data safety | 25/25 | Read-only source, full fingerprint approval, checksum revalidation, empty-target guard, ID/sequence handling, audit row, and no deletion. |
| Compatibility | 25/25 | Current snapshot list/detail values show zero mismatches; HTTP path, legacy writes, upload redirect, ordering, and 404 are covered. |
| Verification | 20/25 | Full tests, real dry-run, isolated import, comparison, Compose, and offline migrations pass; real PostgreSQL + MinIO apply remains blocked by the unavailable Docker runtime. |
| Total | 94/100 | Stage threshold exceeded. |

## Rollback and safety boundary

The new catalog read path stays disabled by default. Enabling it requires the
refactored `app.main:app` entrypoint, `CATALOG_READS_ENABLED=true`, MinIO and
PostgreSQL enabled, and the exact applied `CATALOG_MIGRATION_FINGERPRINT`.

Rollback before catalog writes move is:

1. set `CATALOG_READS_ENABLED=false`;
2. restart the refactored application;
3. verify `/api/products` through the legacy facade;
4. retain target PostgreSQL/MinIO for diagnosis; do not delete source SQLite or
   uploads during the observation period.

Because uploaded object keys are deterministic legacy paths, a failed apply
before the database commit may leave retry-safe MinIO objects but no target
catalog rows. Re-running the same reviewed plan overwrites the same keys with
checksum-verified bytes. The target database must remain empty for the retry.

## Required before staging and write cutover

1. Select the supported staging/production S3-compatible deployment described
   in the storage foundation report.
2. Apply Alembic and the importer against isolated real PostgreSQL and MinIO.
3. Run the comparison tool against that real target, plus HTTP/browser checks
   for images and MP4 Range requests through the redirect.
4. Switch staging to `app.main:app`, enable the reviewed fingerprint, and
   observe logs/readiness before production.
5. Add manager/admin RBAC, catalog write service, media association updates, and
   a dual-write or short maintenance-window strategy before moving writes.
6. Migrate site settings JSON and define cleanup approval for unused uploads.

These items block staging/production traffic changes, but not the next bounded
refactoring slice.
