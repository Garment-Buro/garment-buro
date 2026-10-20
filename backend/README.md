# Garment Buro backend

The current source has one ASGI entrypoint: `app.main:app`. Factory assembles
module routers and services; runtime owns async PostgreSQL, storage, provider
transports and background tasks. HTTP startup checks the Alembic head and never
creates tables or mounts a legacy application. The old root `main.py`, SQLite
runtime, SQLAdmin and landing settings API have been removed.

This release is still being prepared locally; production has not switched to
this worktree. See [runtime and diagnostics](docs/runtime.md) and the repository
release journal at `docs/release-refactoring.md` for verified scope and open gates.

## Local environment

From the repository root:

```bash
uv venv --python 3.12 backend/.venv
uv pip sync --python backend/.venv/bin/python --require-hashes backend/requirements-dev.txt
cp .env.example .env
```

Python dependencies are fully pinned and hashed, including transitive packages.
Edit `requirements.in` / `requirements-dev.in`, then regenerate both `.txt`
locks; do not edit generated locks by hand. `make dependency-check` verifies
that development tests use the same versions and hashes as production.
See [dependency audit and update procedure](docs/dependency-audit.md).

Fill `JWT_SECRET` and only the provider credentials required for the scenario
being tested. Staging and production deliberately refuse to start when any
critical secret is missing. Local and test environments allow integrations to
remain disabled; attempting to use a disabled integration fails before a
network request is made.

Start the local stack from the repository root:

```bash
docker compose -f docker-compose.local.yml up --build
```

This starts PostgreSQL 17, applies Alembic migrations, provisions local MinIO
buckets, and starts the modular API, Redis and frontend. PostgreSQL is the
source of truth for catalog, carts, accounts, favorites, projects and orders.
Disabled feature flags remove their routes; they do not activate SQLite.

Health endpoints:

- `GET /health/live` confirms that the HTTP process is running;
- `GET /health/ready` confirms that the configured async database and MinIO
  media bucket are reachable.

Local MinIO is available on `http://localhost:9000`; its console is on
`http://localhost:9001`. The bucket name includes `APP_ENV`, so local, staging,
and production cannot accidentally share media through the default settings.
The media bucket contains public storefront assets. CRM and customer files
use separate private buckets. Projects and profile photos share the customer
bucket, under separate `projects/` and `profiles/` namespaces. Project access
uses short-lived signed URLs; profile photos use gated API bytes with no-store.
The customer bucket must have no public policy; readiness and media access
enforce this.

MinIO remains the selected file store. The upstream Community repository was
archived in 2026 and its README documents source-only distribution; this does
not stop an existing installation. `deploy/minio/Dockerfile` now builds the
official October2025 security release from pinned source commit/SHA-256, with
a pinned Go image digest. The real linux/amd64 build passed; local Compose and
CI use this same Dockerfile. Server Compose requires a prepared `MINIO_IMAGE`
with `pull_policy: never`. See [storage build and transfer](../deploy/minio/README.md)
and [runtime evidence](../docs/superpowers/plans/2026-10-20-minio-source-release.md).
Changing storage provider or moving to AIStor has not been agreed or performed.
The application uses the S3 boundary.

Runtime S3 socket waits are explicit: `MINIO_CONNECT_TIMEOUT_SECONDS=3`
(maximum30) and `MINIO_READ_TIMEOUT_SECONDS=15` (maximum60). Both must be finite
and positive. GET/HEAD permit one retry; PUT/DELETE do not retry after a response
or read failure because a versioned bucket could gain extra versions or delete
markers. One connection retry is allowed before the request is sent. Redirects
are rejected and Retry-After cannot impose a long sleep. TLS verification and
`SSL_CERT_FILE` remain enabled; owned connection pools are cleared on shutdown.
These are per-attempt socket timeouts, not a total upload/DNS deadline. The
one-shot storage bootstrap has a separate transport policy.
See [fault tests and verification limits](../docs/superpowers/plans/2026-10-20-minio-transport.md).

The20 October rehearsal passed the complete backend gate:1369 tests, no skips,
on fresh native PostgreSQL17 and the new Linux MinIO (Python3.14.3). A synthetic
old volume survived upgrade/restart with its objects, versions and access rules;
the pre-upgrade archive restored to a separate old-server volume. This does not
replace the current Python3.12 CI, coordinated DB/S3 restore or Linux Next gate.

The subsequent Linux/Next gate also passed with current Dockerfile/lock-built
backend/frontend images and the source-built MinIO: role/bucket initialization,
migrations, readiness, API rewrites, private image boundary, standalone pages
and 15 JS/CSS assets. A real server-priced cart survived API restart with Redis
stopped and was read directly and through Next. See [runtime scope and cleanup](../docs/superpowers/plans/2026-10-20-linux-next-runtime.md).
This is a disposable HTTP runtime check, not a published release or DB/S3 restore.
After the transport adjustment, the full Linux/Python 3.12.15 backend gate
passed:1406 tests, no skips, with fresh PostgreSQL17 and the source-built
MinIO. This includes34 transport tests. Dependency locks, Ruff/format and
real migration upgrade/downgrade/upgrade also passed. The full suite used
native Linux/arm64; the subsequent actual server-Compose/Next HTTP gate
passed with a newly built linux/amd64 backend and the unchanged frontend
image reused only after all frontend source hashes matched. The HTTP gate
used binfmt amd64 emulation and confirmed the same image/cart boundaries
described above. All owned containers, volumes, VM disks and private CLI
configuration were removed. GitHub Actions, coordinated DB/S3 restore,
cutover and published browser E2E remain open. See the transport verification
plan for the corrected test fixture and the failed preceding run.

After the backup/deployment recovery fixes, a new current-source Linux gate
passed 1409 tests without skips, exact dependency locks, Ruff/format and real
migration upgrade/downgrade/upgrade. Fresh backend arm64/amd64 builds and the
actual amd64 server-Compose/Next HTTP gate passed; the unchanged frontend image
was reused only after its entire source hash set matched. All 1695 source hashes
matched before/after. The synthetic rootless restore/release rehearsals above
are separate proofs. A later real historical-image rehearsal upgraded the old
database and recovered its checkpoint into separate PostgreSQL/MinIO volumes,
comparing all 103 historical application tables and the old API/Next assets.
The old image rejects the new schema; checkpoint recovery discards later writes.
Real CI and production-volume recovery remain open. See
[historical checkpoint scope](../docs/superpowers/plans/2026-10-20-historical-checkpoint-recovery.md). See [current full gate](../docs/superpowers/plans/2026-10-20-current-full-release.md).

The latest local source gate passed **1445 backend tests, no skips** after the
public-maintenance changes and removal of the unused legacy SQLite URL setting.
It used Linux/Python 3.12, fresh PostgreSQL 17 and the source-built MinIO, exact
locks, Ruff/format, actual migrations and real Nginx privacy/maintenance gates
under uid10001. Fresh backend arm64/amd64 images and the actual amd64 Compose/
Next HTTP gate passed. The unchanged frontend image was reused after complete
source-hash matching; a separate clean Node 24 npm-ci/build/test/browser run also
passed 626 tests without skips. All 1705 source hashes matched through the gate.
See [current foundation gates](../docs/superpowers/plans/2026-10-20-current-foundation-gates.md).

OpenAPI describes the enabled module routes. Historical import tools are
explicit commands, separate from HTTP startup and request handling.

## Public user profiles

With `IDENTITY_API_ENABLED`, `GET /api/people` lists published profiles of active
users; `GET /api/people/{slug}` applies the same visibility rule. The directory
accepts literal `query`, `sort=newest|name`, `limit=1..100` (default 24) and a
filter-bound cursor. A page uses one bounded SQL query and returns only the
profile ID, slug, display name, biography and nullable `avatar_id`. Responses use `Cache-Control:
no-store`.

Products, people and community search share literal Unicode substring rules in
`app/db/text.py`. PostgreSQL 17 uses the built-in `pg_c_utf8` collation for casing,
so Cyrillic and accented Latin do not depend on the cluster's default locale.
`%`, `_` and backslash remain literal search characters. SQLite is a lightweight
test dialect; Unicode behavior is verified against real PostgreSQL.

People/community `sort=name` uses the same lowercase expression and ID tie
breaker in ordering, row-value cursor comparison and functional indexes.
Revision `20261017_0067` rebuilds the people name index and replaces the community
status-only index with `(status, UnicodeLower(title), id)`. Existing rows are not
rewritten. Earlier directory cursors return 422 because their ordering differs;
reload the list to obtain a current cursor. These B-tree indexes bound name
pagination; they are not substring-search indexes or a linguistic alphabet.

All three public list endpoints return an invalid cursor as HTTP 422 with
`detail.code=invalid_cursor` and `Cache-Control: no-store`. Parameter validation
keeps its field-error format. The frontend API boundary distinguishes these cases:
on an expired cursor, the catalog keeps visible cards and offers a first-page
refresh instead of repeatedly sending the rejected cursor. Release these protocol
changes together with the frontend.

Authenticated `GET /api/profile/public` returns the caller's separate public
profile or `null`. `PUT /api/profile/public` accepts `slug`, `display_name`,
`bio`, an explicit `is_published` boolean and `version`: 0 creates, while later
writes must match the saved version. Stale edits and an occupied slug return 409.
Private email, phone, orders and projects are never copied into the public
profile; existing accounts are not published or given a profile automatically.
Unpublishing, blocking or deleting an account hides both public reads. The
bounded lifecycle worker also purges profiles of deleted accounts.

Revision `20261015_0063` adds the opt-in profile schema; `20261015_0064` adds a
nullable media FK with `ON DELETE SET NULL`. Avatar IDs are read-only: text
writes cannot attach arbitrary media or remote image URLs.

Create the profile before uploading its photo. Authenticated multipart
`POST /api/profile/public/avatar?expected_version=N` returns the updated owner
DTO with status 201; `DELETE` at the same address removes the attachment and
returns status 200. Both compare the current version and increment it; stale
operations return 409. Removing the attachment does not require available MinIO.
Input is bounded to 8 MiB: single-frame JPEG/PNG/WebP, maximum 16M pixels and
8192 px per side. The backend applies EXIF orientation, drops metadata, produces
a WebP thumbnail at most 512 px per side and stores at most 2 MiB of normalized bytes.

`GET /api/people/{slug}/avatar/{media_id}` returns image bytes only for the
current attachment of a published profile and active account. The authenticated
owner can preview the current draft attachment through
`GET /api/profile/public/avatar/{media_id}`. Both use no-store and nosniff; they
never redirect to a storage URL. Unpublishing, replacing or removing a photo,
blocking or deleting the account revokes subsequent public requests. Browser
UI must request this API directly, bypassing any lasting image optimizer cache.

Cards on the home page and people catalog use
`GET /api/people/{slug}/avatar/{media_id}/preview`: a fixed WebP rendition with
maximum side 320 px and quality 85. It applies the same attachment/publication,
active-account, private-bucket and SHA-256 checks before rendering outside the
event loop. Smaller originals are not enlarged; transparency is preserved.
There are no caller-selected dimensions, persistent derivatives or image caches.
Existing photos work without a new upload. Full profile and owner endpoints
continue returning the canonical lossless file up to 512 px. The card response
also uses no-store/nosniff, so later requests respect publication revocation.
This reduces bytes transferred to the browser; each request still reads the
canonical MinIO object and performs bounded image encoding work.

Upload metadata is committed as pending before storage PUT; version is checked
again after that commit. Cancellation holds the row lock until the storage
write finishes, leaving durable pending metadata for the existing bounded
worker. Attached photos remain protected, including unpublished drafts.
Replacement/removal starts a fresh seven-day retention period for the old
unreferenced image. Deleted-account cleanup uses the same private media worker.
The frontend now renders real People cards and `/people/[slug]`, with an
authenticated editor at `/profile/public`. The editor starts with blank public
fields, creates a private draft, and publishes only through an explicit action.
Photo preview uses authenticated bytes and a temporary blob URL; public images
request the gated API directly. PWA navigation HTML is never persisted offline.
Owner collection/landing editing and production release validation remain pending.

## Page QR codes

`GET /api/qr-code` generates a PNG for a root-relative page on one of the
configured Garment Buro origins. It never accepts an arbitrary absolute URL.

```text
/api/qr-code?path=/nikitamoiseev&size=512
/api/qr-code?path=/partner&surface=partner&size=512
/api/qr-code?path=/workspace&surface=widget&size=512
```

The `site` surface uses `PUBLIC_BASE_URL`; `partner` and `widget` use
`PARTNER_PUBLIC_BASE_URL` and `WIDGET_PUBLIC_BASE_URL`. Keep those values as
bare trusted origins without credentials, a path, query, or fragment. Supported
PNG sizes are 128–1024 pixels.

## Database migrations

Partner withdrawals to sole-proprietor bank accounts are documented in
[Tochka partner payouts](docs/tochka-partner-payouts.md). The integration is
disabled by default; it creates drafts for signing in the bank and reconciles
payment statuses without automatically signing or retrying uncertain transfers.

Run migrations from `backend/` with an explicit `DATABASE_URL`:

```bash
.venv/bin/python -m alembic -c alembic.ini upgrade head
.venv/bin/python -m alembic -c alembic.ini downgrade -1
```

Application startup never creates or changes refactored tables. The deployment
process must apply Alembic migrations before marking a release ready. Revision
`20260811_0002` creates normalized products, variants, media metadata, and
ordered media-role links. Revision `20260811_0003` records verified catalog
imports used by the runtime cutover guard. Revision `20260811_0004` adds the
identity, RBAC, OTP, refresh-session, and security-audit schema. Revision
`20260811_0005` adds the encrypted notification outbox and delivery-attempt
history. Revision `20260811_0006` adds the guarded identity API ownership bridge,
allows PII-safe soft deletion, and gives OTP notifications an explicit delivery
deadline. Revision `20260811_0007` adds catalog write audit events,
settings/options with immutable revisions, content migration runs, and the
uploading-user link on media metadata. Revision `20260811_0008` adds persistent
carts, normalized item snapshots, optional future user ownership, expiry, and
cart migration-run evidence. Revision `20260811_0009` adds immutable order-line
snapshots, initial status history, and idempotent order-creation requests.
Revision `20260811_0010` adds transactional inventory reservations, reserved
catalog counters, expiry lookup indexes, and database-enforced counter/state
invariants. Revision `20260811_0011` adds deterministic legacy-order import
evidence and quarantined source/provider snapshots while allowing incomplete
historical contact fields without weakening the new checkout command schema.
Revision `20260811_0012` adds one-time-issued, revocable, expiring guest-order
capabilities whose raw tokens are never stored in PostgreSQL.
Revision `20260811_0013` adds durable payment aggregates, provider-call
attempts, and PII-minimized webhook event intake without routing provider
traffic to the new domain.
Revision `20260811_0014` adds payment-worker lock/timestamp invariants and a
dispatch index for verified, retryable event processing.
Revision `20260811_0015` adds durable, independently retryable payment
reconciliation jobs for provider-linked unresolved attempts.
Revision `20260811_0016` persists canonical YooKassa creation-request evidence
and terminal known-rejection state for crash-safe same-key recovery. Revision
`20260812_0017` adds the PII-free paid-order fulfillment command outbox, linked
to exact successful payment-attempt evidence. Revision `20260812_0018` adds
numbered fulfillment-worker attempt history for retry, stale recovery,
dead-lettering, and audited local handoff.
Alembic does not copy legacy data.

## Staging rehearsal preflight

After restoring a staging backup and applying the reviewed Alembic head, run
the read-only PostgreSQL/MinIO/RBAC preflight from `backend/`:

```bash
.venv/bin/python -m scripts.rehearse_staging
.venv/bin/python -m scripts.rehearse_staging --storage-roundtrip
.venv/bin/python -m scripts.reconcile_crm --verify-objects
```

The storage roundtrip writes and removes one random object only under the
private `rehearsal/` prefix. It requires a second explicit guard in production.
The complete backup, migration, RBAC, web/PWA, provider, observation, and
rollback sequence is documented in
`docs/refactoring/42-staging-rehearsal-preflight.md`.

## Catalog migration and guarded read cutover

Build a read-only migration plan from `backend/`:

```bash
.venv/bin/python -m scripts.migrate_legacy_catalog \
  --sqlite-db /absolute/path/to/ecommerce.db \
  --uploads-dir /absolute/path/to/uploads \
  --report /absolute/path/to/catalog-dry-run.json
```

The command validates schema and domain constraints, content-sniffs every
referenced object, calculates SHA-256 checksums, reports missing/unsupported and
unused files, and prints a fingerprint covering every catalog value, reference,
and object. It opens SQLite in read-only mode and never deletes uploads.

Compare the exact legacy values with the refactored repository/service/mapper
using an isolated temporary database and no network storage:

```bash
.venv/bin/python -m scripts.compare_catalog_contract \
  --sqlite-db /absolute/path/to/ecommerce.db \
  --uploads-dir /absolute/path/to/uploads
```

Only after reviewing the dry-run report, apply the same source snapshot to an
empty migrated PostgreSQL database and provisioned MinIO bucket:

```bash
.venv/bin/python -m scripts.migrate_legacy_catalog \
  --sqlite-db /absolute/path/to/ecommerce.db \
  --uploads-dir /absolute/path/to/uploads \
  --apply \
  --expect-fingerprint <fingerprint-from-dry-run>
```

`--apply` refuses an invalid plan, a changed fingerprint, or a non-empty target.
It rechecks every object checksum immediately before upload and records the
completed fingerprint/counts in `catalog_migration_runs`.

Enable catalog reads with `app.main:app` and:

```dotenv
CATALOG_READS_ENABLED=true
```

`GET /api/products` and `GET /api/products/{id}` read PostgreSQL. The compact
storefront API is `/api/catalog/products`. Historical import fingerprints are
verified by migration commands, not by HTTP startup. Existing `/uploads` media
references resolve through PostgreSQL metadata to MinIO; there is no filesystem
fallback. Turning reads off removes their routes and is not a legacy rollback.
Preserve historical source backups until migration and restore are verified.

## Guarded catalog writes, content, and privileged roles

`CATALOG_WRITES_ENABLED=true` registers these paths; when disabled, write routes
are absent:

- `POST`, `PUT`, and `DELETE /api/products...`;
- administrative `GET /api/products`, `/counts`, `/{id}` and categories;
- paged model/fabric editor references under `/api/catalog-editor`;
- `POST /api/upload`.

`/api/options`, `/api/variants/{id}` and the old per-product variant list have
been retired. Both login surfaces use the same product editor. Actual sizes,
colors and allowed fabrics come from the production reference tables; there is
no separate editable JSON-style list of labels.

Product detail and write responses include `version`. Both staff and production
product PUT require a strict positive integer `expected_version`; missing/invalid
versions return422. Under the product row lock, the writer refreshes ORM state
and compares the version before changing any fields/variants/media. A stale
version returns409 with code `catalog_product_version_conflict` without a write
or audit event. Successful edits, confirmed physical stock consumption, and
initial CRM model linking advance the version. Idempotent payment/link replays
do not. Migration0070 and the new frontend/backend must be released together.

Identity mutation routes require the refactored Bearer session and the
`catalog.write` permission. Production assortment routes require an authenticated
system administrator through the production session. Customer tokens receive `403`. Product and variant
writes accept only ready media metadata from the environment-specific MinIO
bucket, run in one PostgreSQL transaction, and append an actor-linked checksum
audit. Uploads are content-sniffed, size-bounded, stored through MinIO, and
record their uploading user. Direct SQLAdmin paths and GET/PUT `/api/settings`
return `404`. Server Compose does not publish the backend port.

Product PUT locks the parent and checks its version before loading children.
The complete editable SKU source is limited to200 (LIMIT201 detects overflow);
bad identity/reference/reservation commands stop before mutations.
An oversized source returns409 `catalog_editor_variant_limit` without changing it.
DELETE can remove a larger unreserved, unlinked preset: scalar cursor batches
of256 rows build `catalog.product-deleted.v2` evidence, then database FK cascades
remove its children in the same transaction. Shared media objects remain.
The audit stores `snapshot_schema`, counts and SHA-256, not the full source;
existing audit records and create/update checksums are unchanged. Migration0078
adds the partial `(product_id,id) WHERE reserved_quantity > 0` index for the
ordered reservation probe. Successful PUT replaces old links using SQL DELETE
without reading them, inserts submitted links in batches of256 and reads only the
resulting media. The response reuses the just-flushed parent/SKU scalars without
assigning partial ORM collections. Editor GET reads media in keyset portions
of256 plus one lookahead row, through scalar DTOs, within the existing URL-field
budgets. An oversized full source returns409 `catalog_editor_media_limit` rather
than a truncated editor. PostgreSQL bounds candidates before indexed LATERAL
metadata lookups. Migration0079 removes duplicate owner-only link indexes;
the unique owner/role/order indexes still cover those prefixes. A parent FOR SHARE
protects owned links during the read; the HTTP helper ends the read transaction
before returning the materialized DTO. Link deletion and streamed audit bound Python buffering,
not total database work.
See [command source and audit format](../docs/superpowers/plans/2026-10-19-preset-command-source.md).
See [media replacement and remaining limits](../docs/superpowers/plans/2026-10-19-preset-media-replacement.md).
See [editor media source and query plans](../docs/superpowers/plans/2026-10-19-editor-media-source.md).

Public card images use one batched query over the already selected product IDs.
An ordered point search finds the first eligible image per role; COALESCE stops
after the first successful role. PostgreSQL materializes the chosen link IDs
before LATERAL PK lookups of their fields. This replaces ranking every image of
the page while retaining catalog/collection priorities and current visibility.
Private/pending/non-image prefixes still require searching until a match or the
end: this is not a fixed total-work bound for arbitrary history. There is no
new cache, denormalized image record, photo quota or migration.
See [public card image selection and actual plans](../docs/superpowers/plans/2026-10-19-storefront-card-images.md).

Public catalog continuations seek `(created_at,id)` or `(price,id)` in the
existing ordered indexes. Cheap ordering combines two separately bounded ranges
in one SQL statement because price ASC and ID DESC have opposite directions.
Both ranges keep every filter and publication rule. No cursor, API or migration
change is required; substring and rare-color filters can still scan many rows
after the cursor. See [deep-page plans and limits](../docs/superpowers/plans/2026-10-19-storefront-page-seeks.md).

Public `/api/catalog/options` derives categories and colors from published
products. A category uses EXISTS; palettes are deduplicated in SQL before JSON
expansion, avoiding a repeated expansion for every product sharing those colors.
The response is `no-store`, with no additional cache or derived business store.
This global query still reads public products and returns every distinct choice;
it does not have a fixed work/output bound when all palettes differ.
See [filter plans and publication checks](../docs/superpowers/plans/2026-10-19-storefront-filter-options.md).

Public `GET /api/catalog/products/{id}` uses a dedicated constructor contract,
`schema_version: 1`, rather than the editable preset DTO. It returns all actual
SKU dimensions/availability, ordered image references and one unique asset
registry. URLs are not CSV fields; only public ready JPEG/PNG/WebP are selected
in SQL. Product descriptions and ORM media graphs are not loaded. SKU-only files
may be referenced by a customer project for that same product. The frontend
validates this version and references; deploy the API and client together.
The complete source still scales with that product's variants/media links.
See [constructor contract, plans and browser checks](../docs/superpowers/plans/2026-10-19-constructor-public-contract.md).

Constructor options use schemas → service → repository and versioned PostgreSQL documents.
A fresh database returns empty colors/sizes without inserting invented defaults.
The first authorized PUT creates revision1; subsequent writes retain immutable
versions and actor IDs. Concurrent first writes serialize without losing history.
New installations need no JSON seed file. Historical landing settings documents
remain archived migration evidence and have no runtime read/write endpoint.

For an existing installation only, create the historical settings/options import
plan from `backend/`. Its planner lives in `catalog/migration/content.py`:

```bash
.venv/bin/python -m scripts.migrate_legacy_catalog_content \
  --uploads-dir /absolute/path/to/uploads \
  --report /absolute/path/to/catalog-content-dry-run.json
```

Missing legacy files use the existing application defaults and this fact is
included in the review report. Apply only the unchanged reviewed plan:

```bash
DATABASE_ENABLED=true DATABASE_URL='<target-postgresql-url>' \
  .venv/bin/python -m scripts.migrate_legacy_catalog_content \
  --uploads-dir /absolute/path/to/uploads \
  --apply \
  --expect-fingerprint <fingerprint-from-dry-run>
```

The initial payloads are stored as revision1. Explicit migration verification
uses that immutable baseline; API startup does not recompute import fingerprints.
Later options edits retain actor-linked revisions. The settings archive is not
used by the storefront.

Privileged roles are never inferred from an email or created by application
startup. Inspect the exact active target first, then repeat with the returned
numeric ID as an explicit apply guard:

```bash
DATABASE_ENABLED=true DATABASE_URL='<target-postgresql-url>' \
  .venv/bin/python -m scripts.bootstrap_role \
  --email manager@example.test --role manager

DATABASE_ENABLED=true DATABASE_URL='<target-postgresql-url>' \
  .venv/bin/python -m scripts.bootstrap_role \
  --email manager@example.test --role manager \
  --apply --expect-user-id <reviewed-user-id>
```

The grant is idempotent and produces a security audit without printing the
email in its result. Use `admin` only when that broader role is intentionally
required.

For an existing deployment, review and verify its data imports before switching
traffic. A new installation does not require import fingerprints. Enable:

```dotenv
DATABASE_ENABLED=true
MINIO_ENABLED=true
CATALOG_READS_ENABLED=true
CATALOG_WRITES_ENABLED=true
IDENTITY_API_ENABLED=true
```

Build the matching frontend image with both
`NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=true` and
`NEXT_PUBLIC_CATALOG_WRITES_ENABLED=true`. The two frontend flags and the two
backend feature flags form one release boundary; unsupported mixed modes must
not receive traffic. The frontend build refuses catalog writes without identity
session v2. Startup validates the schema revision, independently of imported
record counts. The old landing editor is removed; privileged catalog operations
remain available to current production administration.

Before the first target mutation, rollback is configuration-only. After the
first PostgreSQL/MinIO mutation, do not re-enable legacy SQLite catalog writes:
that would create two divergent sources of truth. For an incident, disable the
admin/editor traffic, keep public reads on the target, and fix forward or
restore the previous target release. A full legacy rollback requires an
explicit reverse reconciliation and is not provided by this slice.

## Persistent carts and offline Redis import

With `DATABASE_ENABLED=true` and `CARTS_V2_ENABLED=true`, GET and PUT at
`/api/cart/{cart_id}` store normalized item snapshots, including constructor
`customization`, in PostgreSQL. DELETE returns405; emptying the cart is a
revision-checked PUT with an empty item list. PUT requires `expected_revision`
and a stable `operation_id`: replay returns the same snapshot, while a stale
revision returns409. Responses use `Cache-Control: no-store`.

Redis is an offline migration source only. The current API does not fall back
to a legacy Redis writer when the flag is disabled; the routes are unmounted.

Cart IDs remain bearer-capability values in the public URL contract. PostgreSQL
stores only their SHA-256 digests, and migration reports contain counts plus a
fingerprint rather than raw IDs. Application request logs use route templates,
and Uvicorn access output is disabled. Any separately configured ingress log
must also avoid recording raw capability paths. Constructor items are repriced
from the server catalog and the configurable decoration policy (currently80 ₽
with scale adjustment). Ordinary cart prices remain display snapshots; the
checkout service reprices all items before creating an order/payment amount.

For an existing legacy installation, apply Alembic to the current head and stop
legacy writes before import. With writes frozen, build and
review the current Redis plan from `backend/`:

```bash
.venv/bin/python -m scripts.migrate_legacy_carts \
  --redis-url '<legacy-redis-url>' \
  --report /absolute/path/to/cart-dry-run.json
```

Keep writes frozen and immediately apply the unchanged live snapshot to an
empty target cart store:

```bash
DATABASE_ENABLED=true DATABASE_URL='<target-postgresql-url>' \
  .venv/bin/python -m scripts.migrate_legacy_carts \
  --redis-url '<legacy-redis-url>' \
  --apply \
  --expect-fingerprint <reviewed-cart-fingerprint>
```

The fingerprint binds the digested cart IDs and payload content. Redis TTL is
excluded because it decreases between review and apply; the apply scan re-reads
and preserves each cart's current remaining lifetime instead of extending every
cart by another full retention period. The command refuses changed content, an
invalid cart payload or expiry, or a non-empty target. Only after the apply
commits should the backend be restarted with:

```dotenv
DATABASE_ENABLED=true
CARTS_V2_ENABLED=true
```

The fingerprint is checked by the offline import command; it is not a current
startup setting. A fresh installation needs no import or fingerprint. Startup
validates the current schema. No separate frontend cart feature flag is required;
the current client sends revision and operation IDs. Release the write freeze
only after a real HTTP read/write/empty probe and API restart verify persistence.
The disposable container gate also checks a saved constructor cart with Redis
stopped; this does not migrate real customer data.

Run expiry cleanup from `backend/` on a schedule. The command uses bounded
batches and PostgreSQL `SKIP LOCKED` so multiple workers do not claim the same
rows:

```bash
DATABASE_ENABLED=true DATABASE_URL='<target-postgresql-url>' \
  .venv/bin/python -m scripts.purge_expired_carts
```

Disabling `CARTS_V2_ENABLED` disables the current routes; it does not restore a
legacy implementation. Once PostgreSQL writes begin, Redis is stale. Keep the
PostgreSQL route active and fix forward, or restore a verified compatible target
release/data set. A legacy writer would require explicit reverse reconciliation.
Downgrading the schema is not a data rollback.

## Order creation persistence foundation

The target order service is implemented but is not routed yet. Legacy
`/api/orders` POST/GET traffic, stock mutation, payment creation, CDEK, and
confirmation email behavior remain unchanged. Applying revision
`20260811_0009` creates empty target tables only.

The internal creation service accepts a normalized command plus a stable
idempotency key. PostgreSQL stores only the SHA-256 key digest and a canonical
request fingerprint. The first transaction locks that request and the selected
catalog product/variant rows, resolves the current active catalog values, and
stores:

- server-side product title, price, variant ID, and SKU snapshots;
- exact `NUMERIC(12,2)` subtotal, delivery, line, and total amounts;
- quantity, size, color, image reference, and constructor `customization`;
- contact/delivery snapshots and optional authenticated user ownership;
- an initial versioned `new` status-history event.

The client item title and price never determine the financial snapshot. The
claimed total must equal server-priced items plus the supplied delivery amount,
and a repeated key with different normalized input is rejected. A completed
same-key retry returns the existing order rather than creating another one.
Order items intentionally have no product/variant foreign key because the
current catalog contract permits hard deletion after an order is created.

This service must not be exposed directly yet. Stock reservation and the basic
order lifecycle now exist in the next internal slice, but delivery price still
needs a trusted quote/reservation record, discounts need a server-owned
promotion model, and guest/authenticated read access needs a secure ownership
boundary. Provider IDs and events belong in the later payment and delivery
tables rather than in the order row. Until those slices and a deterministic
legacy-order migration are complete, legacy order routes remain the only
runtime path.

## Inventory reservations and order lifecycle foundation

Revision `20260811_0010` adds `reserved_quantity` to target products and
variants and creates one immutable-snapshot reservation row per order item.
Order creation locks catalog rows in deterministic ID order, validates the
aggregate quantity across duplicate product/variant lines, increments reserved
counters, and writes the order plus reservations in one transaction. Public
catalog responses expose `stock_quantity - reserved_quantity`; physical stock
is reduced only after payment confirmation.

The internal lifecycle currently supports these explicit transitions:

- `new/pending -> processing/paid`: confirm every active reservation and reduce
  physical and reserved counters atomically;
- `new/pending -> cancelled/failed`: release active counters without reducing
  physical stock;
- `processing/paid -> shipped/paid -> completed/paid`: append versioned history
  events without changing inventory;
- expired `new/pending` reservations: release counters and cancel the order in
  bounded batches.

Catalog product replacement/deletion and variant editing return a conflict
while their target rows have active reservations. This prevents a writer from
removing or lowering stock underneath checkout. Resolved reservations retain
the product/variant snapshots even if the catalog row is deleted later.

Run the bounded expiry worker from `backend/` on a schedule:

```bash
DATABASE_ENABLED=true DATABASE_URL='<target-postgresql-url>' \
  .venv/bin/python -m scripts.expire_inventory_reservations
```

Use `--batch-size` to tune a run and `--once` to process one batch. PostgreSQL
workers lock order rows with `SKIP LOCKED`; reservation, product, and variant
rows are then locked in deterministic order. The command is safe to repeat.

This boundary is still internal and does not create a second live order writer.
The current `/api/orders` routes continue to use legacy behavior until order
migration, secure reads, trusted delivery/promotion totals, and payment/CDEK
event ownership are ready behind one guarded cutover. The automated gate checks
the service with SQLite and generates PostgreSQL DDL offline; a real PostgreSQL
concurrency rehearsal remains mandatory before staging activation.

## Deterministic legacy order migration

The order importer reads SQLite in query-only mode and produces a PII-minimized
report. It validates every source column, status, timestamp, money value, item,
quantity, customization object, and provider-reference length. The fingerprint
binds the complete normalized snapshot, including PII and raw cart content,
without printing that content in the report.

Create and review the plan from `backend/`:

```bash
.venv/bin/python -m scripts.migrate_legacy_orders \
  --sqlite-db /absolute/path/to/ecommerce.db \
  --report /absolute/path/to/order-dry-run.json
```

The report separates source and planned order counts and includes item,
payment-reference, delivery-reference, synthetic-ID, and money-reconciliation
counts. Unknown statuses, malformed/non-empty cart violations, invalid money,
and unsupported field lengths make the plan invalid. Missing legacy item IDs
use stable synthetic IDs; missing quantities use the legacy runtime default of
one and both cases are reported. Historical `total_price` remains authoritative
when its item snapshots indicate an old discount or other unmodeled adjustment.

Apply only the unchanged reviewed snapshot to an empty target order store:

```bash
DATABASE_ENABLED=true DATABASE_URL='<target-postgresql-url>' \
  .venv/bin/python -m scripts.migrate_legacy_orders \
  --sqlite-db /absolute/path/to/ecommerce.db \
  --apply \
  --expect-fingerprint <fingerprint-from-dry-run>
```

The import preserves order IDs, contact/delivery fields, raw `cart_items`,
normalized line/customization snapshots, exact total/delivery amounts, current
status/payment status, creation timestamps, and YooKassa/CDEK references. The
provider references and exact source JSON live in `legacy_order_imports` as a
quarantined handoff to future payment/delivery tables; they are not treated as
verified provider events. One `legacy.imported` history event records the only
state known from the source.

Imported historical orders intentionally receive no active inventory
reservation and no creation-request row. Legacy already decremented stock when
it created an order, so reconstructing a reservation would double-consume or
release inventory without evidence. The importer records exact counts in
`order_migration_runs`, synchronizes PostgreSQL sequences after preserving IDs,
and accepts an exact replay only while target counts still match the reviewed
run.

This command prepares data only; it does not enable a target order route. Keep
legacy reads/writes active until secure owner/staff reads, provider event
ownership, trusted checkout totals, and the guarded HTTP cutover are complete.
After import, schema downgrade is not a rollback: preserve target orders and
reconcile any later writes before changing source ownership.

## Guarded target order reads

`ORDER_READS_ENABLED=true` moves only these read paths to PostgreSQL:

- authenticated customer `GET /api/auth/orders`;
- authenticated `GET /api/orders/{order_id}` for the owner or a staff user with
  `orders.read_all`;
- authenticated paginated `GET /api/orders?limit=100&offset=0` for staff with
  `orders.read_all`.

The existing response shape is preserved, including string `cart_items`.
Imported rows return the exact quarantined legacy JSON and provider references;
new target rows reconstruct the same JSON shape from normalized item snapshots,
including constructor customization. A verified email can claim matching
imported IDs once; the claim stores only a keyed digest and remains valid after
an email change. Direct `order.user_id` ownership is supported for new orders.

Public numeric-ID detail access is intentionally closed on this path. Missing
or invalid Bearer credentials return `401`; customers receive `404` for an
unowned order so its existence is not disclosed, and customer list attempts
return `403`. Staff list/detail requires `orders.read_all` from the current RBAC
tables, not an email allowlist.

Enable the boundary only after applying and reviewing both identity and order
migrations:

```dotenv
DATABASE_ENABLED=true
IDENTITY_API_ENABLED=true
IDENTITY_MIGRATION_FINGERPRINT=<reviewed-identity-fingerprint>
ORDER_READS_ENABLED=true
ORDER_MIGRATION_FINGERPRINT=<reviewed-order-fingerprint>
```

Startup refuses a missing fingerprint, changed import/provider counts, missing
source-ID mapping, imported inventory reservations, or incomplete initial
history. It allows later target-created orders/history while requiring the
reviewed imported baseline to remain present.

This is a read-only cutover. `POST /api/orders`, webhooks, and provider actions
still fall through to legacy; the contract test verifies this method split.
Do not enable the flag for production yet: the current public order-result page
still reads detail by numeric ID and the public checkout still writes through
legacy. The guest capability described below is ready for a coordinated
frontend/checkout cutover, but it is not issued by the current HTTP checkout.
Until then, use this boundary only in isolated staff/account staging. Rollback
is configuration-only because target checkout writes remain disabled: set
`ORDER_READS_ENABLED=false` and restart.

## Hashed guest order access

Target-created guest orders can receive an opaque order-scoped capability. The
client must generate 32 cryptographically random bytes and encode them as an
unpadded Base64URL token (43 characters) before its first checkout attempt. The
same token must accompany every retry with the same order idempotency key. Its
SHA-256 digest is included in the request fingerprint, so a changed token fails
closed as an idempotency conflict instead of creating or exposing a different
access path.

The order transaction stores only the token digest and a bounded expiry in
`order_guest_access`. Raw tokens cannot be recovered by the server. The default
TTL is 30 days and can be set from 1 to 365 days with:

```dotenv
ORDER_GUEST_ACCESS_TTL_DAYS=30
```

After checkout, the client keeps the raw token only in its scoped browser/PWA
session and reads the result with a header rather than putting a secret in the
URL:

```http
GET /api/order-access
X-Order-Access-Token: <43-character-token>
```

Missing, malformed, unknown, expired, and revoked tokens all return the same
`404`. Successful and failed responses use `Cache-Control: no-store`. The
application and reverse proxy must redact `X-Order-Access-Token` from request,
error, tracing, and access logs. Do not send the token in query parameters,
analytics, provider metadata, email links, or referrers.

Capabilities can be revoked through the service layer and are deleted with the
order. They are deliberately forbidden for authenticated orders and are never
granted retrospectively to imported legacy orders. The startup cutover guard
also refuses imported rows with a capability.

The creation service currently accepts an optional capability so its
transaction and idempotency behavior can be verified without taking over the
legacy route. A future public target checkout must require the token whenever
`user_id` is absent, persist it client-side before the request, and keep it
through retries/result navigation. Do not enable a target guest checkout route
until that frontend contract, log redaction, browser/PWA behavior, and real
PostgreSQL staging path have been rehearsed together.

## Durable YooKassa payment persistence

Revision `20260811_0013` prepares a default-inert payment domain with three
tables:

- `payments` owns the exact order amount/currency and aggregate provider state;
- `payment_attempts` records each numbered provider operation, a digest of the
  client attempt key, the request fingerprint, one persisted UUIDv4
  `Idempotence-Key`, provider ID, redirect URL, status, and terminal evidence;
- `payment_events` records a bounded safe observation and SHA-256 evidence for
  incoming notifications, never the complete provider body.

Preparing the same client attempt replays the same provider key. Reusing that
client key for another order or changed amount/method fails as a conflict. A
different attempt cannot start while the existing one is `prepared`, has an
unknown network outcome, is pending, or waits for capture. A canceled attempt
may be followed by a new numbered attempt with a new provider key. Successful
payments are terminal and cannot regress.

The provider key is intentionally persisted because YooKassa requires the same
key and request data for a safe retry. YooKassa currently guarantees that
idempotency for 24 hours, so an unresolved request must never be retried with a
new key; after the window, it requires explicit reconciliation rather than a
blind create. See the official
[interaction format](https://yookassa.ru/developers/using-api/interaction-format)
and [response recommendations](https://yookassa.ru/developers/using-api/response-handling/recommendations).

Target webhook intake is exposed only when `PAYMENT_WEBHOOK_V2_ENABLED=true`;
the flag is false by default, so legacy remains the route owner. The target
accepts only the raw bounded JSON body from an official YooKassa source network,
parses the same bytes whose digest is stored, validates
`type=notification`/event/status/amount/order evidence, commits durably, and only
then returns HTTP 200. Exact semantic duplicates receive the same acknowledgement.
Only normalized scalar evidence is persisted; extra payload fields are discarded.
Changed evidence under the same event identity fails closed. YooKassa also
requires checking the current provider object; IP allowlisting alone is not
enough. See the official
[incoming notification guidance](https://yookassa.ru/developers/using-api/webhooks).

The route uses the direct socket peer unless that peer belongs to
`PAYMENT_WEBHOOK_TRUSTED_PROXY_CIDRS`. Only then does it walk
`X-Forwarded-For` from right to left, removing trusted hops. The exact nginx
location replaces any caller-provided forwarding chain with `$remote_addr` and
limits the body to 256 KiB. Never configure `0.0.0.0/0` or `::/0`; determine the
actual private proxy network at deployment. Invalid/untrusted input gets no
HTTP 200, so YooKassa can retry according to its delivery contract.

## Verified payment event worker

The refactored YooKassa read adapter uses an instance-scoped `aiohttp` session
and HTTP Basic authentication; it does not mutate the legacy SDK's global
configuration. It permits no redirects, caps response bodies at 256 KiB, maps
only a validated provider payment snapshot, and classifies safe error codes
without including response bodies or credentials. Staging/production accept
only `https://api.yookassa.ru/v3`; staging rejects live provider objects and
production rejects test objects.

The bounded worker claims one `payment_events` row with `FOR UPDATE SKIP
LOCKED`, increments its persisted attempt, and commits the claim before calling
YooKassa GET. A stale worker lock can be reclaimed. If the final allowed worker
attempt crashed after its claim commit, the next reaper marks the row `dead`
without exceeding the database attempt constraint or calling the provider
again.

After GET, the worker verifies provider ID, metadata order ID, exact
amount/currency, method, environment, and a valid status progression. A
successful payment, inventory confirmation, order transition, and processed
event commit atomically. A canceled payment closes only that payment attempt;
the order/reservation remains pending so the customer can retry until normal
reservation expiry. Changed evidence is rejected. A confirmed payment whose
inventory can no longer be atomically consumed becomes `dead` with a safe error
code for explicit refund/fulfilment handling; the system does not claim that
the order was processed.

Transient provider/processing failures use bounded exponential backoff;
permanent configuration failures and exhausted retries become `dead`. The
processing timeout must exceed the network timeout. Worker logging contains
only event ID, attempt number, state, and an allowlisted error code.

The worker can be started from `backend/` after migrations and credentials are
configured:

```bash
.venv/bin/python -m scripts.process_payment_events --once
```

Compose exposes it only through the explicit `payments` profile. Do not run it
against production yet: guarded HTTP intake now exists but remains disabled;
target payment creation/receipt builder, provider sandbox evidence, real
PostgreSQL concurrency proof, and deployed proxy evidence are still absent.
Legacy remains the payment traffic owner.

## Durable payment reconciliation

Revision `20260811_0015` adds one `payment_reconciliation_jobs` row per payment
attempt. A job is scheduled after a provider-linked attempt becomes `pending`
or `waiting_for_capture`; the bounded seeder can also restore missing jobs for
provider-linked `unknown`/active attempts. Unlinked unknown create outcomes and
imported legacy orders are deliberately excluded: the reconciler never guesses
a provider ID and never repeats create with a new idempotence key.

The reconciler claims and commits one job before its single YooKassa GET. It
then locks the payment attempt before the job (the same ordering used by the
webhook path), verifies the typed current provider snapshot, and atomically
records payment evidence plus any inventory/order transition. It does not
invent a webhook event. A concurrent terminal webhook may complete the job;
the reconciler detects that committed terminal state and exits without applying
the order twice.

Active provider states are checked again after the configured interval. Network
and provider availability failures use bounded exponential retry; stale claims
can be reclaimed, and the last crashed attempt becomes `dead` without another
GET. The default 288 five-minute checks bound the active window to roughly 24
hours and are configurable. A terminal cancellation keeps the order/reservation
available for a new attempt. Paid state with expired/broken inventory rolls
back and becomes a safe manual-action job instead of publishing a false order
state.

Reconciliation remains disabled in normal backend settings and has its own
explicit Compose profile. From `backend/`, after migrations and credentials:

```bash
PAYMENT_RECONCILIATION_ENABLED=true \
.venv/bin/python -m scripts.reconcile_payments --once
```

Do not enable the long-running profile in production before real PostgreSQL
concurrency, YooKassa sandbox, alerting for `dead` jobs, and exact operational
intervals have been rehearsed.

## Durable YooKassa payment creation

Revision `20260811_0016` adds durable create-call evidence to payment attempts:
the SHA-256 of the exact canonical provider request, first/last attempt times,
and the create count. The raw request is not stored because it contains receipt
and customer data. A provider-confirmed request rejection becomes a resolved
`failed` attempt; uncertain transport/provider outcomes remain `unknown`.

The target builder uses immutable order-item snapshots and exact Decimal
amounts. Every product is a separate receipt line and delivery is a separate
service line. The service never guesses VAT, payment mode, payment subject, tax
system, or marked-goods data. `PAYMENT_CREATION_ENABLED=true` is rejected until
the required product/delivery fiscal settings and YooKassa credentials are
explicitly configured.

Before the provider POST, the service commits the request digest, timestamps,
attempt count, and persisted UUIDv4 idempotence key. An unlinked timeout can
retry only the byte-identical request/key within the configured 23-hour window.
Once a verified provider ID is known, recovery uses the durable GET reconciler
instead of another POST. Immediate success records payment, inventory, order,
and history atomically; a local apply failure retains only the verified provider
identity as `unknown` and schedules reconciliation.

The boundary remains intentionally unrouted and disabled. Legacy checkout and
the frontend/PWA response contract are unchanged. Do not enable it before
accounting approves all receipt values and real PostgreSQL plus YooKassa sandbox
create/redirect/webhook/reconciliation scenarios pass. See
[`docs/refactoring/20-durable-payment-creation.md`](docs/refactoring/20-durable-payment-creation.md)
for the exact gate, recovery rules, verification, and rollback.

## YooKassa automatic payments, holds, and payouts

Revision `20260904_0028` extends the payment domain without changing the default
checkout behavior. `POST /api/orders` still creates a one-stage payment unless
the request explicitly contains:

```json
{
  "payment_method": "card",
  "payment_capture_mode": "manual"
}
```

`automatic` sends `capture=true`; `manual` sends `capture=false`. A manually
captured payment becomes actionable only after YooKassa reports
`waiting_for_capture`. The provider's `expires_at` is persisted and exposed to
staff as `capture_expires_at`; YooKassa documents a method-dependent capture
window from two hours to seven days. See the official
[two-stage payment flow](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process#capture-and-cancel).

Set `PAYMENT_MANAGEMENT_ENABLED=true` only with the target database, identity,
payment creation, shop credentials, and either webhook processing or payment
reconciliation enabled. Users need
`payments.manage` (`manager` and `admin` system roles). The staff API is:

```text
GET  /api/payments/orders/{order_id}
POST /api/payments/orders/{order_id}/capture
POST /api/payments/orders/{order_id}/cancel
```

Capture and cancel requests require an empty body and a client
`Idempotency-Key`. The backend persists a separate provider UUIDv4 key before
network access. Exactly one terminal operation is allowed per held payment, so
capture and cancel cannot race. Unknown outcomes retry only with the same
operation and key; confirmed provider rejections are not blindly repeated.

Payouts are a separate domain and never reuse shop credentials. YooKassa
requires the payout gateway `agentId` and its own secret key; configure them as
`YOOKASSA_PAYOUT_AGENT_ID` and `YOOKASSA_PAYOUT_API_KEY`. Then explicitly enable
`YOOKASSA_PAYOUTS_ENABLED=true`. Only `admin` receives `payouts.manage`.
YooKassa must also enable payouts and fund the gateway balance before live use.
See the official [payout overview](https://yookassa.ru/developers/payouts/overview)
and [authentication rules](https://yookassa.ru/developers/using-api/interaction-format#auth).

Create and inspect payouts through:

```text
POST /api/payouts
GET  /api/payouts/{payout_id}
POST /api/payouts/{payout_id}/refresh
```

Creation requires a client `Idempotency-Key` and supports YooKassa payout
tokens, saved payment method IDs, bank cards, YooMoney wallets, and SBP. Prefer
a token or saved payment method so raw card data does not traverse this API.
For example:

```json
{
  "amount": {"value": "500.00", "currency": "RUB"},
  "destination": {
    "type": "payout_token",
    "token": "<token-created-by-the-approved-YooKassa-client-flow>"
  },
  "description": "Выплата по заказу 17",
  "reference": "order:17"
}
```

Raw destination data and payout tokens are used only to build the outbound
request and are never stored. PostgreSQL keeps the amount, safe reference,
destination type, request digest, provider identity, status, terminal evidence,
actor, and retry metadata. A provider timeout remains `unknown`; the identical
request can be retried for 23 hours, within YooKassa's documented 24-hour
idempotency window. `refresh` performs the provider GET needed to move a
persisted `pending` payout to `succeeded` or `canceled`.

Both flags default to false. Apply the migration, verify RBAC, and complete
YooKassa sandbox payment/hold/payout scenarios before enabling either feature
in staging. No production credentials or real financial operation belongs in
pytest, source control, or a manual smoke test.

## Atomic target checkout orchestration

Stage 21 introduced the service-only target checkout boundary now used by the
guarded HTTP route. `CHECKOUT_V2_ENABLED` remains false by default and requires
target catalog reads, identity, target order reads, and durable payment creation
to be enabled together.

The orchestrator atomically prepares the order, immutable items, status
history, inventory reservations, optional guest capability digest, payment,
and deterministic payment attempt. Only after that commit does the payment
creation service call YooKassa. A preparation failure rolls everything back;
a provider timeout retains one replayable order/attempt rather than rolling
back or creating duplicates.

Guest callers must generate and persist their 43-character order-access token
before checkout and submit that same token on every retry. Authenticated callers
use their resolved user ID and cannot also attach a guest capability. The same
checkout idempotency key deterministically derives the payment-attempt key, so
response loss can replay both phases without storing raw keys.

The boundary accepts only current frontend methods `card` and `qr`, mapped to
YooKassa `bank_card` and `sbp`. It reloads order state after payment, so immediate
success reports current `processing/paid` state. With the flag disabled, legacy
`/api/orders`, its `{order_id, payment_url}` response, CDEK/email behavior, and
the frontend/PWA remain unchanged. See
[`docs/refactoring/21-atomic-checkout-orchestration.md`](docs/refactoring/21-atomic-checkout-orchestration.md).

## Guarded checkout HTTP contract

Stage 22 conditionally gives the target application ownership of
`POST /api/orders` only when `CHECKOUT_V2_ENABLED=true`. When the flag is false,
the mounted legacy route still receives the same request. The target response
intentionally remains `{order_id, payment_url}` so the coordinated frontend/PWA
cutover does not need a second response shape.

Every target request requires a 16-128 character `Idempotency-Key`. Guest
checkout also requires the 43-character capability previously generated and
durably retained by the browser/PWA in `X-Order-Access-Token`; authenticated
checkout instead resolves the bearer token and rejects a simultaneous guest
capability. A malformed or unsupported `Authorization` header fails with 401
and is never downgraded to a guest order.

The route accepts only `application/json`, reads at most 512 KiB from the actual
ASGI stream, parses the typed target order command without echoing input values,
and applies `Cache-Control: no-store` to success and handled failures. It maps
catalog/stock/idempotency/payment-state conflicts, invalid totals, known
provider rejection, and unknown provider outcomes to stable safe responses. An
unknown create outcome returns the retained order ID and can be replayed with
the same checkout key/capability; it does not create another order or provider
key.

The FastAPI lifespan owns one aiohttp/YooKassa transport instance and closes it
on shutdown. No provider SDK-global state is used. The reverse proxy remains
unchanged while the route is default-off, so deploying this stage cannot impose
a new legacy request limit. Add an exact 512 KiB proxy limit only in the
coordinated cutover deployment. See
[`docs/refactoring/22-guarded-checkout-http.md`](docs/refactoring/22-guarded-checkout-http.md).

## Authorized payment retry

Stage 23 adds the default-off
`POST /api/orders/{order_id}/payment-attempts` endpoint for a retained target
order after a known failed or canceled attempt. It never creates another order
or another inventory reservation. The route has no request body, requires a
new `Idempotency-Key`, and returns the same `{order_id, payment_url}` shape as
checkout.

Only the direct target `order.user_id` or the valid unexpired guest capability
may authorize a retry. Claimed legacy imports, another account, missing,
malformed, expired, or revoked capabilities all receive the same 404 boundary.
An authenticated caller cannot add a guest capability. A supplied invalid
authorization header remains 401 rather than falling back to guest behavior.

A new attempt is allowed only while the order is still `new/pending`, the
latest attempt is terminal `failed` or `canceled`, and every reservation remains
active. The reservation is atomically refreshed for one configured inventory
TTL before the provider call. Total attempts, including initial checkout, are
bounded by `PAYMENT_MAX_ATTEMPTS_PER_ORDER` (default 3, allowed 1–10), preventing
unbounded stock retention. Exact replay neither spends another attempt nor
extends the reservation again.

Existing attempt replay locks the attempt before its order, matching payment
creation/reconciliation ordering and allowing a lost immediate-success response
to replay without regressing the paid order. A new retry receives a new UUIDv4
provider key; unknown outcomes retain same-key/body recovery and known rejection
does not POST twice. The endpoint is registered only with
`CHECKOUT_V2_ENABLED=true`, so legacy traffic remains unchanged. See
[`docs/refactoring/23-authorized-payment-retry.md`](docs/refactoring/23-authorized-payment-retry.md).

## Durable post-payment fulfillment outbox

Stage 24 adds a default-off publisher for customer payment email, CDEK order
creation, and internal CRM projection. Verified payment application inserts the
selected commands in the same transaction as payment, inventory, and order
state. Payment creation, webhook processing, and reconciliation never perform
SMTP, CDEK, or CRM network requests inline.

`fulfillment_jobs` stores only the order ID, exact succeeded payment-attempt ID,
command kind, retry/lifecycle metadata, and safe result/error fields. Recipient,
phone, address, pickup point, receipt/provider payload, guest token, and
checkout key are not copied into the command. A unique `(order_id, kind)` key
makes payment replay a repair operation instead of a duplicate side effect.

Apply revision `20260812_0017`, keep `FULFILLMENT_OUTBOX_ENABLED=false` until the
consumer handlers and alerts are ready, and use the bounded repair command only
after reviewing target paid-order evidence:

```bash
FULFILLMENT_OUTBOX_ENABLED=true \
.venv/bin/python -m scripts.seed_fulfillment_jobs --limit 100
```

The seeder excludes imported legacy orders. This stage does not add a network
consumer or claim exactly-once external delivery. See
[`docs/refactoring/24-durable-fulfillment-outbox.md`](docs/refactoring/24-durable-fulfillment-outbox.md).

## Fulfillment worker and paid-order email handoff

Stage 25 adds an opt-in fulfillment worker that currently claims only
`customer_payment_email`. CDEK and CRM commands remain pending until their own
handlers are production-complete. The worker does not call SMTP: it revalidates
the paid order/succeeded attempt and atomically writes an AES-256-GCM encrypted
`order_payment_confirmed` notification plus fulfillment completion evidence.

Every claim has numbered attempt history, ownership checks, capped exponential
retry, stale-attempt abandonment, and terminal dead-letter state. The paid-order
template uses immutable item/price snapshots, validates exact totals/RUB, omits
phone/address/pickup data, and autoescapes customer/catalog text. Notification
dedup uses the order ID and native PostgreSQL/SQLite conflict-safe insert, so a
rolled-back handoff leaves no orphaned notification.

Apply revision `20260812_0018`, configure both fulfillment flags and the
notification encryption key, and enable both opt-in worker profiles only after
staging review:

```bash
docker compose --profile fulfillment --profile notifications up \
  fulfillment-worker notification-worker
```

SMTP delivery remains at-least-once and is still owned by the notification
worker. See
[`docs/refactoring/25-fulfillment-worker-email-handoff.md`](docs/refactoring/25-fulfillment-worker-email-handoff.md).

## Immutable CDEK shipment handoff

Stage 26 adds the pre-network CDEK safety boundary. Target order items now keep
trusted product logistics snapshots; CDEK checkout rejects missing/nonpositive
weight or dimensions before payment and never uses the legacy 500/1000 gram or
20x20x10 centimeter fallbacks.

A database-only handoff builds stable CDEK v2 JSON, stores its SHA-256, encrypts
the exact bytes with AES-256-GCM, links the shipment to the paid order, exact
succeeded payment attempt, and source fulfillment job, then records a prepared
event atomically with fulfillment completion. Only safe IDs, digest, lifecycle,
and future provider references remain readable in the database.

Apply revision `20260812_0019`, audit active catalog logistics, and configure an
independent `CDEK_REQUEST_ENCRYPTION_KEY`. The live handler is intentionally not
registered yet: there is no CDEK network worker, unknown-outcome recovery,
webhook/status reconciliation, or sandbox proof in this stage. See
[`docs/refactoring/26-cdek-shipment-foundation.md`](docs/refactoring/26-cdek-shipment-foundation.md).

## Guarded CDEK creation worker

Stage 27 adds an instance-scoped async CDEK v2 adapter and a separate opt-in
creation worker. Each claim and numbered attempt is committed before network
I/O; the worker decrypts and authenticates the exact stage-26 bytes instead of
rebuilding a request. Known pre-POST OAuth failures use bounded retry, provider
validation rejection becomes dead, and every ambiguous create outcome or stale
claim becomes `unknown` with no automatic repeat POST.

Apply revision `20260812_0020`. Enable `FULFILLMENT_CDEK_ENABLED` first to build
encrypted prepared shipments, then enable the independent
`CDEK_CREATION_ENABLED`/`cdek` profile only for reviewed sandbox testing. No live
CDEK activation is justified until real PostgreSQL concurrency and provider
create/get/timeout-after-acceptance scenarios pass. See
[`docs/refactoring/27-cdek-creation-worker.md`](docs/refactoring/27-cdek-creation-worker.md).

## Identity security foundation

Build a PII-minimized, read-only user migration report from `backend/`:

```bash
.venv/bin/python -m scripts.migrate_legacy_identity \
  --sqlite-db /absolute/path/to/ecommerce.db \
  --report /absolute/path/to/identity-dry-run.json
```

The report contains counts, validation errors, warnings, and a deterministic
fingerprint; it does not list email addresses or profile values. The planner
opens SQLite read-only. Legacy plaintext OTP values and expirations are never
copied. If any are present, the report records only their count and those users
must request a new code after cutover.

After reviewing the source snapshot, apply it to an empty migrated target:

```bash
.venv/bin/python -m scripts.migrate_legacy_identity \
  --sqlite-db /absolute/path/to/ecommerce.db \
  --apply \
  --expect-fingerprint <fingerprint-from-dry-run>
```

The target keeps legacy user IDs and assigns the system `customer` role. The
apply step refuses any existing user, role assignment, OTP challenge, refresh
session, security event, or previous identity migration run. System roles and
permissions created by Alembic are allowed and verified.

`IDENTITY_OTP_PEPPER` must be a unique secret of at least 32 characters and
must not equal `JWT_SECRET`. The new service uses a 15-minute access token,
opaque hashed refresh tokens with rotation/reuse detection, peppered OTP
digests, persisted attempt/rate limits, and security audit events. These
components are used by the modular `/api/auth/*` routes when
`IDENTITY_API_ENABLED=true`. A disabled identity boundary removes those routes;
it never falls back to the removed legacy application.

## Encrypted notification outbox

The notification worker requires a URL-safe Base64 key containing exactly 32
random bytes. Generate it outside source control and store it in the deployment
secret manager:

```bash
python -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="))'
```

Set the result as `NOTIFICATION_ENCRYPTION_KEY`. The recipient, OTP, and template
context are encrypted with AES-256-GCM before the outbox row is flushed. Only a
deduplication key, lifecycle state, attempt counters, and safe error code remain
readable in PostgreSQL. Encrypted payload columns are erased after delivery or
dead-lettering.

Apply migration `20260811_0005`, then run one bounded drain from `backend/`:

```bash
.venv/bin/python -m scripts.process_notification_outbox --once
```

For continuous local processing, enable the opt-in Compose profile from the
repository root:

```bash
docker compose -f docker-compose.local.yml --profile notifications up notification-worker
```

During key rotation, increment `NOTIFICATION_ENCRYPTION_KEY_VERSION`, put the new
key in `NOTIFICATION_ENCRYPTION_KEY`, and retain old versions as a secret JSON
object in `NOTIFICATION_PREVIOUS_ENCRYPTION_KEYS` until all active rows using
them are drained. For example, the shape is `{"1":"<old-base64-key>"}`; never
commit real values.

The worker claims rows with `FOR UPDATE SKIP LOCKED`, commits the claim before
the SMTP request, retries transient failures with capped exponential backoff,
and recovers stale processing attempts. Delivery is intentionally at-least-once:
a process failure after SMTP accepted a message but before the database commit
can produce a duplicate. Email content must therefore remain safe to repeat.
Current auth routes enqueue through this outbox in the same transaction as the
challenge. Email, Telegram and disabled phone transports use one registry. Replaced,
consumed, or expired OTP notifications are dead-lettered and their encrypted
payload is erased before a later retry can deliver a stale code.

## Identity API and authentication methods

Revision `20260811_0006` contains the complete refactored HTTP boundary for the
current frontend paths:

- email OTP request and verification;
- `GET`, `PUT`, and `DELETE /api/auth/me`;
- verified email change;
- `GET /api/auth/orders`;
- refresh-token rotation, bounded legacy-session migration, and logout.

The example environment enables the modular boundary. Set independent secrets
outside source control and apply migrations before starting it:

```dotenv
DATABASE_ENABLED=true
IDENTITY_API_ENABLED=true
IDENTITY_OTP_PEPPER=<independent-secret-at-least-32-characters>
NOTIFICATION_ENCRYPTION_KEY=<url-safe-base64-of-32-random-bytes>
```

`GET /api/auth/methods` describes each API method and its availability.
`POST /api/auth/password/login` accepts a verified identifier and password;
authenticated `PUT /api/auth/password` sets or changes the Argon2id credential.
`IDENTITY_PASSWORD_AUTH_ENABLED=true` is the default, with five attempts and a
15-minute lockout controlled by `IDENTITY_PASSWORD_MAX_ATTEMPTS` and
`IDENTITY_PASSWORD_LOCKOUT_MINUTES`. Password hashing has bounded concurrency.

`POST /api/auth/telegram` validates the signed Telegram payload and reuses its
existing external identity. It requires `IDENTITY_TELEGRAM_AUTH_ENABLED=true`
and `TELEGRAM_BOT_TOKEN`; both auth and Telegram delivery are off by default.
`TELEGRAM_AUTH_MAX_AGE_SECONDS` bounds the signature age. Telegram notification
delivery separately requires `NOTIFICATION_TELEGRAM_ENABLED=true` and the bot.

Phone endpoints and transport are present as explicit disabled methods;
`IDENTITY_PHONE_AUTH_ENABLED` and `NOTIFICATION_PHONE_ENABLED` must remain false
until a real delivery provider exists. Settings reject enabling them now.
Updating a contact phone does not establish a verified login phone. No OTP is
returned in an API response. The current frontend form exposes email OTP only;
the fake Telegram tab has been removed. API support does not imply a completed UI.

Existing pre-cutover Bearer tokens can be accepted temporarily by setting a
timezone-aware `IDENTITY_LEGACY_TOKEN_GRACE_UNTIL`. The cutoff cannot be more
than 31 days in the future. During that window,
`POST /api/auth/session/migrate` accepts only the old token shape and converts
it into a target refresh session without making the user log in again. New
logins receive a 15-minute access token plus a rotating opaque refresh token in
a host-only, HttpOnly, SameSite=Lax cookie; staging and production also set
Secure. Refresh, migration, and logout reject cross-origin requests, and reuse
of a rotated token revokes its entire session family.

Order reads use the PostgreSQL order service, pagination and ownership checks.
The old runtime SQLite ownership bridge is removed. Historical imports are
explicit tools; CDEK is not called from cabinet reads.

The refactored frontend lifecycle is guarded separately by the build-time
`NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED` flag. The example environment enables
it together with the API. The access
token is memory-only, the HttpOnly cookie restores the session, authenticated
requests retry once after a coordinated refresh, tabs exchange only opaque
coordination markers, and backend logout is retried after offline or transient failure.
An old persisted Bearer token is removed from browser storage while the bounded
migration endpoint establishes its refresh session.

Do not enable either identity flag for live traffic yet. Build the frontend
with `NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=true` and set
`IDENTITY_API_ENABLED=true` only as one staging cutover after the identity
import and worker are ready. Enabling only one side creates an intentionally
unsupported mixed mode. Real PostgreSQL, SMTP, web, and installed-PWA rehearsal
is the next gate.

## Partner cabinet finances and requisites

The partner cabinet reads its real SQL dashboard, owner landing editor and
paged payout history from `/api/partner/*`. Payout requests remain an internal
review workflow and cannot exceed the matured, unreserved balance.

Before the first payout request, a partner must save bank requisites through
`GET` and `PUT /api/partner/requisites`. Revision `20260904_0031` stores one
requisites record per partner. Recipient and bank fields are serialized and encrypted
with AES-256-GCM, bound to the partner ID, and never stored in plaintext. The codec uses
the configured notification encryption key ring so existing key rotation continues to
decrypt older records. Only a user with `partners.read_own` can read or replace their
own details.

## Verification gate

```bash
make -C backend check PYTHON=.venv/bin/python
```

This runs Ruff checks/format verification, all unit, contract, catalog,
identity, notification, and migration tests, plus offline PostgreSQL
upgrade/downgrade generation.

Without native test dependencies, `make check` permits PostgreSQL/MinIO skips.
The release CI instead provisions four isolated PostgreSQL test databases and
MinIO, then runs `python -m scripts.check_tests`: the complete suite must pass
with no skips. See [runtime checks](docs/runtime.md#проверки-миграций) for the
required environment and private configuration. This command uses the active
Python interpreter and does not require a machine-specific shell wrapper.

Verify both frontend flag modes separately:

```bash
cd frontend
npm run check
NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=true npm run build
NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=true \
  NEXT_PUBLIC_CATALOG_WRITES_ENABLED=true npm run build
```

The second build verifies the guarded cutover bundle explicitly; it does not
replace the staging browser/PWA rehearsal.

Manual SMTP connectivity is kept outside pytest:

```bash
cd backend
.venv/bin/python -m scripts.check_smtp
```

Never place credentials in source files, examples, logs, or command history.

## CRM paid-order production intake

Revision `20260812_0021` adds the first private CRM aggregate. A paid-order
fulfillment command creates one PII-free production project and expands each
order line into one numbered production unit per purchased quantity. The rows
reference immutable order/payment evidence and do not copy customer identity,
delivery data, product text, customization, or provider IDs.

The handoff is disabled by default. After applying the migration, opt in on
staging with:

```dotenv
DATABASE_ENABLED=true
FULFILLMENT_OUTBOX_ENABLED=true
FULFILLMENT_CRM_ENABLED=true
```

Drain a bounded batch from `backend/`:

```bash
.venv/bin/python -m scripts.process_fulfillment_jobs --once --max-items 100
```

Project changes use explicit versioned transitions and append-only audit events.
No CRM HTTP route is exposed in this stage; manager/admin RBAC, private MinIO
attachments, reference data, material movements, and the internal cabinet are
separate follow-up slices. See
`docs/refactoring/28-crm-paid-order-intake.md` for invariants, staging checks,
score, and rollback.

## Versioned CRM reference data

Revision `20260812_0022` adds private fabrics, garment models and stable sizes,
explicit links to the existing public catalog, immutable tech-card revisions,
ordered checkpoints, and checksum audit events. The implementation keeps the
useful domain language from the early prototype without recreating its
`Item`/`ItemVariant` storefront tables.

Fabric quantities are intentionally not mutable columns; the following
material-ledger stage will derive balances from append-only movements. Likewise,
published tech-card checkpoints are never overwritten: changes create a new
draft revision, which is explicitly published or discarded.

This stage exposes no HTTP route and needs no feature flag. Apply migration
`20260812_0022` only after backing up the target PostgreSQL database. Online
downgrade refuses to delete any durable CRM reference row. See
`docs/refactoring/29-crm-reference-data.md` for ownership rules, revision flow,
verification, score, and rollback.

## Pinned CRM production workflow

Revision `20260812_0023` gives each paid-order production unit a versioned event
history and immutable plan revisions. A plan resolves the public product through
its CRM model link, matches a stable CRM size to the order snapshot, and pins an
exact published tech-card revision. Publishing a newer card cannot rewrite work
already planned against the older revision.

Units cannot start without an active plan, cannot be replanned after work starts,
and follow an explicit queued/in-progress/quality/completed lifecycle with
terminal protection. This is still a private application service with no staff
HTTP route or feature cutover. See
`docs/refactoring/30-crm-production-workflow.md` for invariants, migration
backfill, verification, score, and rollback.

Production order detail now uses request-local `ProductionDetailRepository` batches
(up to256 IDs), shared specification validation and the same role projection.
Migration `20261019_0080` replaces model/plan-only indexes with ordered first-row
indexes for fabric requirements and reservations. The full response remains
proportional to this order; no page Provider or persistent cache was added.
See `docs/superpowers/plans/2026-10-19-production-detail-batches.md` for exact
PostgreSQL comparisons, physical plans and release limitations.

## Append-only CRM material ledger

Revision `20260812_0024` adds material receipts, reservations, consumption,
release, and adjustments. Fabric availability is derived from immutable
movements plus a locked balance projection, not mutable stock fields on the
fabric reference row. Commands are idempotent through persisted SHA-256 key and
command fingerprints.

Reservations pin exact production-plan revisions. Active reservations block
replanning until released, and adjustment-out cannot consume reserved material.
This remains a private service with no staff route. See
`docs/refactoring/31-crm-material-ledger.md` for accounting equations,
reconciliation, verification, score, and rollback.

Administrative landing directories (`/api/admin/partners/landings` and production
`/api/production/admin/assortment/product-communities`) now return `{items,next_cursor}`
with search/status, default24/max100 and filter-bound ID cursors. They select scalar
summaries with product_count/version, without content or product_ids. Identity
partners.manage and production system-admin authorization remain separate; responses
are no-store. The unbounded list_all_landings reader is removed.

Catalog administration returns variant_count/sku. Production additionally receives
a maximum of three community summaries plus community_count per product. Membership reads are restricted to IDs
on the current product page. SQL computes capacity without loading ORM variants;
full variant references are available on the detail route. These DTO changes require
a coordinated frontend/backend release; no additional schema migration is required.

Membership previews and the landing total are enabled only by the internal
production adapter. Ordinary identity/CRM catalog reads do not query partner
metadata: community_count/communities count are null and previews are empty.
The identity landing directory separately requires partners.manage. This switch
is not a public query parameter; null means not read, not an asserted zero.

Основной интерфейс товаров — `/production?section=presets`; старые `/admin/models` и `/admin/products/*` перенаправляют туда. Производственная сессия и системные права обязательны. Поиск товаров для коллекции постраничный, выбранные ID/порядок сохраняются независимо от страницы; лимит 50. См. `docs/superpowers/plans/2026-10-18-primary-presets.md`.

Private partner reads: `/api/admin/partners` and `/api/partner/payouts` now return
`{items,next_cursor}`, default limit 24, max 100. Profile cursors bind search/status/
selectable; payout cursors bind the authenticated owner and `(created_at,id)`.
No ORM collections or bank requisites are selected for these lists. Dashboard
aggregates use one SQL statement and retain Decimal and payout locking rules.
Revision `20261018_0071` adds matching read indexes. Removed unused exact list GETs:
`/api/partner/landings` and `/api/partner/commissions`; public slug reads remain.
Deploy the matching frontend/backend together; see
`docs/superpowers/plans/2026-10-18-partner-private-reads.md` in the repository root.

Кабинет владельца: owner list возвращает краткие карточки с product_count;
полный контент читается через detail endpoint. Dashboard содержит has_requisites
без банковских полей; отдельный редактор реквизитов читает их по открытию блока.
Ошибка этого GET не закрывает кабинет и не разрешает пустое сохранение.
DTO требуют согласованного выпуска frontend/backend. Подробности:
`docs/superpowers/plans/2026-10-18-owner-cabinet-boundaries.md`.

Настройка S3-бакетов выполняется явно командой `python -m scripts.bootstrap_storage`
из backend-каталога. Local/server Compose запускают её сервисом `minio-init`
в backend-образе; отдельный `minio/mc` больше не нужен. Команда сохраняет объекты,
закрывает CRM/projects и разрешает media только анонимное чтение объектов.
Имена передаются в `MINIO_MEDIA_BUCKET`, `MINIO_CRM_BUCKET`, `MINIO_PROJECTS_BUCKET`;
подключение — `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`.
`--help` не меняет хранилище. API startup не выполняет provisioning.
Подробности: `docs/superpowers/plans/2026-10-19-storage-bootstrap.md`
в корне репозитория. Поставка серверного MinIO теперь описана в
[source build](../deploy/minio/README.md): образ заранее собирается из закреплённых
исходников и загружается на сервер. Сам deploy его не скачивает и не собирает.
