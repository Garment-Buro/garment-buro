# Stage 10: persistent carts and guarded Redis cutover

Status: complete for the bounded persistent-cart slice; disabled by default

Quality score: 92/100

## Safety boundary

This stage does not enable cart traffic in any environment and does not change
orders, payment, CDEK, or inventory behavior. `CARTS_V2_ENABLED` remains `false`
by default, so the mounted legacy Redis endpoints continue to own the current
paths until an explicit migration and restart.

No production Redis, PostgreSQL database, service, or live traffic was changed.
The public path and response contract remain `/api/cart/{cart_id}`, so the web
and installed-PWA clients do not require a coordinated build flag.

## Delivered

- normalized SQLAlchemy models for carts, item snapshots, optional future user
  ownership, versioning, expiry, and deterministic migration-run evidence;
- money stored as `NUMERIC(12,2)` and constructor `customization` stored as
  JSONB, while product/title/media/variant choices remain deliberate snapshots;
- no foreign key from an item snapshot to a product, preserving the current
  hard-delete catalog contract and historical cart readability;
- raw bearer-capability cart IDs are never persisted; only SHA-256 digests are
  stored in PostgreSQL and included in the migration fingerprint;
- repository/service/router separation with PostgreSQL row locks, atomic child
  replacement, dialect-specific insert-on-conflict acquisition, and stale
  client timestamp protection; an imported legacy clock outlier is preserved
  but cannot permanently block the next valid current write;
- bounded input rules: valid capability syntax, unique item IDs, at most 100
  items, 512 KiB cart payloads, 64 KiB per customization object, non-negative
  prices, and sane future-clock skew;
- exact empty/read/write/delete response compatibility, with absent optional
  `customization` omitted from the legacy-shaped response;
- expired carts read as empty, can be safely reactivated, and are deleted by a
  bounded maintenance command using PostgreSQL `FOR UPDATE SKIP LOCKED`;
- deterministic Redis `cart:session:*` dry-run planning with count-only reports,
  an exact fingerprint apply guard, empty-target enforcement, and idempotent
  completed-run handling; the content fingerprint deliberately excludes the
  decreasing TTL while apply preserves each freshly read remaining lifetime;
- startup refusal unless the reviewed migration fingerprint is present;
- Compose/environment wiring with all new flags defaulting to false;
- frontend log wording changed from the old implementation detail `Redis` to
  the stable `server` boundary without changing synchronization behavior.

Cart price and catalog data remain untrusted client snapshots. The future order
creation service must resolve the current product/variant, reprice server-side,
validate stock, and create immutable order lines in one idempotent transaction.
Account/guest cart merging is intentionally deferred until the order boundary
defines its ownership and conflict rules.

## Verification

- complete backend gate: Ruff lint/format passed, 109 tests passed, and offline
  PostgreSQL Alembic upgrade/downgrade through `20260811_0008` passed;
- contract coverage: exact empty response, legacy-shaped item response, nested
  customization round trip, stale-write rejection, invalid ID, duplicate item,
  future timestamp, delete, and feature-off route ownership passed;
- persistence coverage: digest-only storage, atomic replacement, expiry,
  reactivation, version reset, and bounded cleanup passed;
- migration coverage: deterministic PII-minimized plan, malformed source and
  invalid expiry rejection, empty-target enforcement, apply, idempotency,
  future legacy timestamp plus remaining-TTL preservation, startup fingerprint
  success, and mismatch failure passed;
- complete frontend gate: ESLint, 196 tests, TypeScript, and production Next.js
  build passed;
- local and production Compose rendering passed;
- repository whitespace check passed.

Docker/OrbStack was not running, so this evidence does not claim a real
PostgreSQL concurrent first-write/row-lock run, a real Redis scan/import, a
browser or installed-PWA cart session, a process restart against persistent
storage, or a deployed staging cutover.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Router, service, repository, models, cutover guard, migration planner, and maintenance job follow the existing modular-monolith boundaries. |
| Security and privacy | 18/20 | IDs are hashed at rest, reports avoid raw capabilities, validation is bounded, and enablement requires reviewed evidence; public path logs and the legacy-compatible capability format still need operational controls. |
| Reliability and data safety | 19/20 | Atomic writes, locks, stale protection, deterministic migration, target-empty enforcement, expiry, and explicit rollback limits are covered. |
| Compatibility | 19/20 | Existing routes and response shapes remain, constructor customization survives, and the default-off flag leaves Redis ownership unchanged. |
| Verification | 17/20 | Full automated backend/frontend and migration gates pass; real PostgreSQL, Redis, browser/PWA, restart, and staging evidence remain outstanding. |
| Total | 92/100 | The bounded cart stage exceeds the requested threshold without conflating local SQLite/SQL generation with live infrastructure proof. |

## Staging rehearsal

1. Apply Alembic through `20260811_0008` to an isolated PostgreSQL target and
   confirm backups plus restore access before migration.
2. Keep `CARTS_V2_ENABLED=false`; block legacy cart `PUT` and `DELETE` briefly,
   then scan Redis and review the count-only report and exact fingerprint.
3. While writes remain frozen, immediately rescan/apply the same fingerprint to
   the empty target and inspect `carts`, `cart_items`, and
   `cart_migration_runs` counts without exposing raw cart IDs.
4. Enable the backend flag with the applied fingerprint and restart. Verify an
   imported GET, a newer PUT, stale PUT, nested customization, DELETE, expiry,
   and another restart through real HTTP.
5. Exercise two browser tabs, an installed PWA, offline edits followed by
   reconnect, an empty local cart versus a newer server cart, and deletion.
6. Run the cleanup command concurrently in two processes and verify PostgreSQL
   lock behavior and bounded deletion.
7. Observe request latency, conflicts, database locks, row growth, access-log
   treatment of capability paths, and Redis independence before production.

## Cutover and rollback

The Redis snapshot is not atomic while clients can write. A short write freeze
is required across dry-run, exact fingerprint apply, backend switch, and the
first target probe. An ordinary live rescan without a freeze is not migration
evidence.

Before any PostgreSQL cart mutation, rollback can freeze writes, disable the
flag, restart, and return ownership to the unchanged Redis source. After the
first PostgreSQL `PUT` or `DELETE`, Redis is stale. Keep target ownership and fix
forward, or perform a separately reviewed reverse reconciliation before legacy
writes resume. Alembic downgrade must never be used as the data rollback.
