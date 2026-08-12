# Stage 43: guarded CDEK quote foundation (paused)

Status: **paused by owner request on 2026-08-12; not approved for staging or production**.

This checkpoint replaces the unsafe calculation internals behind a default-off
`CDEK_QUOTE_ENABLED` flag. The target path accepts only product identifiers and
quantities, reloads active product logistics from PostgreSQL, uses the same
round-up conversion rules as shipment creation, builds deterministic CDEK v2
request bytes, and calls the provider through the bounded async transport.
Provider failures are classified and no longer become a successful zero-price
response on the target route.

The browser now sends only `product_id` and `quantity` for this request. The
legacy route remains available while the target flag is off.

## Verified at checkpoint

- backend quality gate: Ruff, 294 tests, and Alembic upgrade/downgrade SQL;
- frontend quality gate: ESLint, 201 tests, and production Next.js build;
- production and local Compose configurations render successfully;
- focused CDEK/config suite: 49 tests.

No authenticated CDEK request and no staging runtime were exercised.

## Required before enabling

Do not set `CDEK_QUOTE_ENABLED=true` yet. The next delivery stage must bind the
quoted amount to checkout with a short-lived signed token (or an equivalent
server-owned persisted quote), so a browser cannot replace `delivery_price` at
order creation. It must also add the HTTP contract suite and configure a
multi-instance rate limit at the trusted reverse proxy. After those controls,
run the staging rehearsal with real PostgreSQL, MinIO, and CDEK credentials.

The default-off flag is the safety boundary for this paused checkpoint.
