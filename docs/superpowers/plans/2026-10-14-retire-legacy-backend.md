# Retire legacy backend runtime and landing settings

**Goal:** Remove the old runnable backend and landing settings API; keep current configuration, notifications, media and data migration workflows in explicit modules.

**Architecture:** `/api/options` uses a dedicated schema → service → repository boundary and the existing versioned PostgreSQL document table. No row means an empty list, not invented colors/sizes. Authorized PUT can initialize the real configuration; concurrent initial writes serialize through INSERT ON CONFLICT and a row lock. Historical import and fingerprint verification live only under `catalog/migration`, with no dependency from HTTP/runtime to that package. Historical settings data is preserved as migration evidence, without an API that reads or changes it.

**Constraints:** Preserve current API authorization and media/SMTP behavior; do not remove actual CDEK/aiohttp adapters or historical migrations needed to transfer user data. No SQL schema change, customer data deletion, commit, push or deployment in this stage. Existing dirty changes belong to the active full release goal.

## Implementation

- [x] Add failing checks: GET/PUT `/api/settings` are404; a fresh configuration reads empty and accepts its first authorized update; SMTP failures do not log raw provider diagnostics.
- [x] Extract options schemas/repository/service/router. Preserve validation, actor and immutable version history. Verify concurrent first writes against PostgreSQL.
- [x] Move historical content planner/apply/cutover code into `catalog/migration/content.py`; update explicit command/tests and retain fingerprint semantics.
- [x] Move active SMTP sender to `app/integrations/smtp.py` and image processing to `app/modules/media/images.py`; retain current notification rendering and worker error/retry contracts.
- [x] Delete old main/CDEK/SDK payment/email/image root files and exclusive checkout compatibility functions, old SQLite image mutation utility and tests of removed paths. Retain active pickup directory tests and all modern provider coverage.
- [x] Remove old root Compose, obsolete runtime dependencies and unused product cache settings; update Makefile, pytest configuration and current operator documentation.

## Verification

- [x] Run focused behavioral HTTP, options, image and SMTP checks, and PostgreSQL concurrency proof.
- [x] Run Ruff/format, complete backend suite with four PostgreSQL databases and real MinIO, forward/backward offline migrations, packaging validation and script syntax.
- [x] Request independent focused review; resolve confirmed issues and repeat affected checks.
- [x] Verify runtime import/startup/readiness from the remaining entrypoint, retired HTTP settings routes and active options against a disposable current-code database.
- [x] Update release journal/map with fresh evidence and explicit remaining release gates. Container build/rollback/restore and public deployment remain unproven until exercised.

## Evidence

- RED: old settings GET returned200, absent options raised ConfigurationError,
  old SMTP logging exposed diagnostic text. Corresponding behavioral checks pass.
- Focused64 tests passed, including real PostgreSQL concurrent initial writes.
  Independent review found no confirmed issues and separately ran11 focused tests.
- Fresh complete run:585 passed,0 skipped,117.37s, four loopback PostgreSQL databases
  and real MinIO. Removed tests covered only the deleted legacy application.
  Earlier interrupted handle96222 was missing and no pytest process remained;
  this fresh run56321 completed with exit0.
- Ruff and format481 files passed; offline Alembic upgrade/downgrade through0060,
  domain routing validation and shell syntax checks passed.
- Task-owned runtime proof applied Alembic head to a fresh disposable database,
  provisioned three owned MinIO buckets and exercised actual factory lifespan
  twice. Live/ready200, settings GET/PUT404, fresh options empty, customer403,
  manager PUT200, restart persistence and versions1/2 with correct actor passed.
  Its database and buckets were removed; existing fixtures were not modified.
- HTML export remains offline with descriptions,13 shells and179 components.
  Frontend source unchanged this stage;346 tests/build belong to its prior stage.
- Release remains open: the frontend checkout DTO and current API disagree.
  Fix modern purchase flow next; no legacy fallback. Docker is unavailable here;
  container build, restore, previous-image compatibility and public E2E remain
  unverified. No commit, push or deployment.
