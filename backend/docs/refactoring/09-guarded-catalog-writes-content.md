# Stage 9: guarded catalog writes, content, and privileged roles

Status: complete for the bounded write-cutover slice; disabled by default

Quality score: 93/100

## Safety boundary

This stage does not enable catalog or identity traffic in any environment. The
backend `CATALOG_WRITES_ENABLED` and frontend
`NEXT_PUBLIC_CATALOG_WRITES_ENABLED` defaults remain `false`. Backend writes
cannot be enabled unless reviewed catalog/content/identity fingerprints,
PostgreSQL, MinIO, catalog reads, and the identity API are configured together.

No production database, bucket, role, frontend image, service, or live traffic
was changed. The existing frontend behavior remains unchanged on the legacy
request path while the frontend flag is false.

## Delivered

- SQLAlchemy/Pydantic/repository/service ownership for product create, full
  product update, product delete, variant list, and compatible standalone
  variant update;
- atomic validation of every product/variant media reference against ready
  metadata in the environment-specific MinIO bucket;
- actor-linked immutable catalog audit events with canonical SHA-256 snapshots
  or mutation details;
- RBAC dependencies that require `catalog.write`; anonymous and customer
  requests are rejected before any mutation;
- a dry-run-first, fingerprint-guarded importer for legacy `settings.json` and
  `variant_options.json`, including exact current defaults when files are
  absent;
- PostgreSQL catalog documents with versioned immutable revisions and startup
  verification of the original reviewed content fingerprint;
- an idempotent manager/admin bootstrap command with an explicit expected-user
  ID guard and security audit;
- authenticated, size-bounded, content-sniffed media upload to MinIO with the
  uploading actor recorded in PostgreSQL;
- frontend Bearer integration for product, variant-associated media,
  settings, and option writes through the existing refresh/retry lifecycle;
- coordinated Docker/Compose build and runtime flags, all defaulting to false;
- a frontend build-time failure when catalog writes are requested without the
  v2 identity session boundary;
- direct production backend-port removal, retirement of direct legacy SQLAdmin
  after write cutover, and removal of nginx public caching from mutation-capable
  product routes;
- writable restart validation that preserves the reviewed migration and media
  baseline without incorrectly requiring product counts to stay frozen.

Product deletion remains a hard delete because that is the current API
contract. Media metadata/objects and audit rows are retained. The future order
model must store product/variant snapshots and must not introduce a restrictive
foreign key that would silently change this behavior.

## Verification

- complete backend gate: Ruff lint/format passed, 98 tests passed, and offline
  PostgreSQL Alembic upgrade/downgrade through `20260811_0007` passed;
- catalog HTTP contract: anonymous `401`, customer `403`, manager product and
  variant CRUD, settings/options revisions, audit actors, and MinIO metadata
  links passed;
- upload rejection: anonymous/customer access, over-limit input, SVG content,
  and unsafe catalog-content URL checks passed;
- unknown/non-ready media is rejected atomically and no product/audit row is
  left behind;
- strict pre-write and mutation-aware post-write restart guards passed;
- complete frontend gate: ESLint, 196 tests, TypeScript, and production Next.js
  build passed;
- explicit production build with both identity and catalog write flags enabled
  passed;
- local and production Compose rendering passed;
- current read-only content dry-run passed with `settings.json` as source,
  default options, 0 links, 2 colors, 6 sizes, and fingerprint
  `35e32c6d3c64bc49642f91dec21f90a91bef45691dee18065a37bc36530ba67c`;
- repository whitespace check passed.

Docker/OrbStack was not running, so this evidence does not claim a real
PostgreSQL row-lock/constraint run, a real MinIO object transfer, a browser or
installed-PWA admin edit, a role grant against staging, or a deployed cutover.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Routes, services, repositories, models, migration tools, and frontend auth boundary stay separated in the existing modular-monolith style. |
| Security and privacy | 20/20 | RBAC covers every legacy catalog mutation, unsafe content/media is rejected, SQLAdmin is shadowed, and privileged grants require exact reviewed identity. |
| Reliability and data safety | 19/20 | Transactions, row locks, immutable audits/revisions, deterministic imports, restart-safe guards, and default-off activation are covered. |
| Compatibility | 19/20 | Existing paths and response shapes remain, variant replacement semantics match legacy, and disabled flags preserve the current frontend/backend boundary. |
| Verification | 16/20 | Full automated gates and both flag builds pass; real PostgreSQL, MinIO, browser/PWA, and staging proof remain outstanding. |
| Total | 93/100 | The bounded stage exceeds the requested threshold without presenting local doubles as live infrastructure evidence. |

## Staging rehearsal

1. Apply Alembic through `20260811_0007` to an isolated PostgreSQL target and
   provision the environment-specific media bucket.
2. Run and review the catalog, catalog-content, and identity dry-run reports;
   apply only the unchanged exact fingerprints.
3. Inspect the intended active user, grant `manager` with the expected numeric
   ID, and verify the single security-audit event.
4. Start backend and frontend with all feature flags still false and prove
   legacy behavior plus readiness.
5. Build one frontend image with both identity and catalog flags true. Switch
   it together with backend identity/catalog reads/catalog writes as one
   blue/green release.
6. Through real HTTP and MinIO, upload each supported format, create/update a
   product and variant, edit settings/options, restart backend, and verify the
   same public catalog response, media range behavior, actor audits, revisions,
   and customer/anonymous rejection.
7. Verify web and installed-PWA session refresh while editing, two tabs, access
   expiry, offline recovery, logout, and a non-manager account.
8. Observe logs, database locks, audit/revision counts, object metadata, and
   public ISR freshness before production consideration.

## Rollback

Before any target write, restore the frontend image with both public flags
false and set `CATALOG_WRITES_ENABLED=false` and `IDENTITY_API_ENABLED=false`.
The legacy facade then owns the old paths again.

After the first target write, legacy SQLite and local uploads are stale. Do not
resume legacy catalog mutations. Remove admin/editor traffic, leave public
reads on the target, retain PostgreSQL/MinIO/audits/revisions, and fix forward
or restore the prior target application image. A switch back to legacy writes
requires a separately reviewed reverse reconciliation; schema downgrade is not
a rollback for data already written through this stage.
