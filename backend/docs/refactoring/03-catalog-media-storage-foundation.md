# Stage 3: catalog schema and MinIO storage foundation

Status: complete for the branch

Quality score: 92/100

## Delivered

- normalized SQLAlchemy 2 models for products and product variants;
- `NUMERIC` money and dimensions, JSONB ordered size/color lists, timestamps,
  deterministic constraints, and non-negative data checks;
- normalized `media_objects`, `product_media`, and `product_variant_media`
  tables instead of comma-separated object URLs;
- every current frontend media field represented as an explicit role, including
  desktop/mobile sliders, video posters, size charts, and variant images;
- object metadata for bucket, key, MIME type, byte size, SHA-256 checksum, ETag,
  version, visibility, and lifecycle status;
- Alembic revision `20260811_0002` with upgrade and complete downgrade;
- a typed asynchronous boundary over the official MinIO Python SDK;
- safe object-key validation, URL encoding, upload size limits, bucket readiness,
  public URLs, deletion, and presigned reads;
- a media repository and service following `service -> repository/model`;
- durable upload intent: metadata is committed as `pending` before object upload,
  then becomes `ready` or `failed`, allowing later reconciliation after crashes;
- content-based JPEG/PNG/WebP/MP4/WebM detection rather than trusting the file
  extension or client MIME header;
- SVG/arbitrary-file rejection, decompression-bomb rejection, optional image
  optimization, safe filenames, and checksum of the stored bytes;
- environment-isolated bucket naming and MinIO-aware application readiness;
- pinned local MinIO server/client containers and an idempotent bucket bootstrap;
- no change to the legacy storefront API or its active production data path.

## Compatibility boundary

The target schema deliberately keeps the existing product IDs and every public
media role, but stores lists as ordered relations. A compatibility mapper in the
catalog cutover slice will turn those relations back into the exact current
single-URL and comma-separated fields expected by the frontend.

The existing `/api/upload` endpoint still writes to local disk. The new MinIO
service is not exposed through an unauthenticated route: switching admin uploads
must be done together with authorization, migration reporting, and rollback.

The current production Compose entrypoint and SQLite reads are unchanged. The
new PostgreSQL tables are empty until the next slice performs a dry-run import,
count/checksum comparison, dual-path API comparison, and explicit cutover.

## Existing-data audit

The current SQLite catalog contains four products and fourteen variants. The
target uniqueness and non-negative checks are compatible with this snapshot:

- no duplicate `(product_id, size, color)` variant combinations;
- no negative product or variant stock;
- no empty product titles;
- no null product prices;
- all four products use desktop, mobile, and product-page slider media roles.

The audit was read-only and did not modify the developer database.

## Evidence

- `make -C backend check PYTHON=../.venv/bin/python`: passed;
- Ruff lint and format checks: passed;
- unit, contract, auth, image, database, storage, and model tests: 50 passed;
- focused catalog/media/storage tests: 9 passed independently;
- offline PostgreSQL Alembic upgrade through `20260811_0002`: passed;
- offline downgrade from head to base: passed;
- local and production Compose configuration validation: passed;
- pinned MinIO server and client image manifests are available for supported
  local development architectures;
- legacy facade and frontend characterization contracts remain green.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 24/25 | Schema, integration, service, repository, and lifecycle boundaries are separated; catalog read repositories begin in the next slice. |
| Data and security | 24/25 | Typed constraints, checksum/status metadata, content sniffing, size/key checks, safe filenames, and environment bucket isolation are enforced. |
| Compatibility | 23/25 | All legacy media roles and IDs are represented and legacy tests pass; the relation-to-legacy response mapper is intentionally part of cutover. |
| Verification | 21/25 | Full/focused tests, offline migrations, source-data audit, Compose validation, and image manifests pass; Docker runtime was unavailable for a live PostgreSQL + MinIO upload. |
| Total | 92/100 | Stage threshold exceeded. |

## MinIO lifecycle decision

The official MinIO Python SDK remains the application client and is suitable for
S3-compatible storage. The community MinIO server repository, however, became
source-only and was archived in 2026; historical prebuilt images are no longer a
production support channel. The pinned images in local Compose are therefore
strictly for development.

Before staging, select and document one production path:

1. supported MinIO AIStor with an appropriate license and SLA;
2. a reviewed self-built MinIO deployment with AGPL obligations accepted; or
3. another managed S3-compatible service using the same application boundary.

Source: <https://github.com/minio/minio>.

## Required before catalog production cutover

1. Run the migration and a real upload/download/delete cycle against isolated
   PostgreSQL and the chosen staging object storage.
2. Implement a deterministic SQLite/uploads importer with counts, SHA-256
   checksums, unknown-role fallback, and repeatable dry-run output.
3. Implement catalog repository/service and a compatibility response mapper.
4. Compare old and new `/api/products` responses field by field.
5. Protect new catalog/media writes with manager/admin permissions.
6. Add orphan/pending media reconciliation and bucket backup/restore runbooks.

These items define the next catalog migration slice and block production
cutover; they do not invalidate this completed storage/schema foundation.
