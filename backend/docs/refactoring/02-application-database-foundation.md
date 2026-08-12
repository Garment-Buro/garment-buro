# Stage 2: application and async database foundation

Status: complete for the branch

Quality score: 93/100

## Delivered

- a refactored `app.main:app` entrypoint that owns one FastAPI lifespan;
- the legacy application mounted as a compatibility facade without changing its
  public `/api/...` paths;
- `/health/live` and database-aware `/health/ready` endpoints;
- a lazy application-scoped async SQLAlchemy engine and session factory;
- explicit transaction rollback at the session dependency boundary;
- PostgreSQL URL normalization for the `asyncpg` driver;
- SQLAlchemy 2 declarative base, typed ID/timestamp mixins, and deterministic
  constraint names for stable Alembic output;
- Alembic async online migrations and PostgreSQL offline SQL generation;
- an intentionally empty baseline revision from which domain schemas can grow;
- PostgreSQL 17 and a one-shot migration service in the local Compose stack;
- backend readiness gating before the local frontend starts;
- a production compatibility switch: the new database remains opt-in and the
  deployed legacy entrypoint is unchanged;
- tests for lifecycle ownership, health behavior, rollback, URL normalization,
  Alembic head integrity, constraint naming, and facade API compatibility.

## Compatibility boundary

The new async database is infrastructure only at this stage. Catalog, users,
carts, orders, settings, and uploads continue to use the legacy SQLite path.
This is deliberate: domain data will move only with its schema, repository,
service, migration, and contract comparison in the same logical slice.

Local Compose exercises the refactored entrypoint and PostgreSQL readiness.
Production Compose continues to run the legacy entrypoint with
`DATABASE_ENABLED=false` by default. Therefore this stage adds no hidden
production data cutover.

Mounted legacy routes are reachable through the facade, but they are not merged
into the parent application's OpenAPI document. Each migrated module will become
a first-class router and will then appear in the new schema.

## Evidence

- `make -C backend check PYTHON=../.venv/bin/python`: passed;
- Ruff lint and format checks: passed;
- unit, contract, auth, and image migration tests: 35 passed;
- offline PostgreSQL Alembic upgrade and downgrade SQL generation: passed;
- Alembic graph: one linear head, `20260811_0001`;
- local Compose configuration: valid with `postgres`, `migrate`, `redis`,
  `backend`, and `frontend` services;
- production Compose configuration: valid and still uses the legacy entrypoint;
- real facade request: `/api/products` keeps the legacy frontend contract;
- readiness tests cover both a reachable database and a `503` failure path.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 24/25 | Factory, lifespan, health router, database manager, and migration boundary are isolated; domain routing starts in the next slice. |
| Data safety | 24/25 | No automatic schema mutation or production cutover; transaction rollback and explicit migrations are enforced. |
| Compatibility | 24/25 | Characterization tests pass through the mounted legacy facade; parent OpenAPI cannot yet merge mounted routes. |
| Verification | 21/25 | Full local gate and offline PostgreSQL migration checks pass; a live PostgreSQL container could not be started because the local Docker runtime was unavailable. |
| Total | 93/100 | Stage threshold exceeded. |

## Required before production cutover

1. Run Alembic upgrade and downgrade against an isolated real PostgreSQL
   instance when the Docker runtime or staging database is available.
2. Add PostgreSQL backup/restore and migration-rehearsal runbooks.
3. Add separate staging database credentials and make the refactored entrypoint
   the staging deployment target before changing production.
4. Move one complete domain module before treating PostgreSQL as a source of
   business data.

These items belong to the infrastructure and catalog migration slices. They do
not block the next stage, but they do block production data cutover.
