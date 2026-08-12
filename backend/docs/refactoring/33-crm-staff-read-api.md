# Stage 33: guarded CRM staff read API

Status: complete locally; staging identity/PostgreSQL proof and staff mutations pending

Quality score: 94/100

## Safety boundary

This stage exposes only read models required to start a staff cabinet. The
router is absent unless `CRM_API_ENABLED=true`, and configuration refuses that
flag unless both the target PostgreSQL boundary and target identity API are
enabled. Every route resolves the target bearer session and requires the
existing `crm.access` permission.

Responses are explicit Pydantic DTOs assembled in `router -> service ->
repository -> model` order. ORM entities are never serialized directly. Order
contact, delivery address, payment provider/reference, prices, and constructor
customization are intentionally absent. Unit DTOs expose only production-safe
item snapshots: product/variant IDs, title, SKU, size, and color.

No mutation, private-file URL, or customer cabinet route is introduced.

## Delivered

- default-off `CRM_API_ENABLED` in settings, example environment, and both
  Compose variants;
- guarded application registration for the CRM router and read service;
- shared `require_crm_reader` dependency using target identity and exactly
  `PermissionCode.CRM_ACCESS`;
- `GET /api/crm/projects` with status/assignee filters and descending keyset
  pagination;
- `GET /api/crm/projects/{project_id}` with a separately bounded ascending unit
  cursor, immutable order-item production snapshots, and the active pinned
  production-plan summary;
- project-detail evidence checks compare the durable unit count to the project
  snapshot and fail closed on missing order-item evidence;
- `GET /api/crm/reference/fabrics` with active filter, keyset pagination, and an
  explicit distinction between no balance projection and a real zero balance;
- computed fabric availability is returned as `on_hand - reserved`, never as an
  independently stored field;
- `GET /api/crm/reference/garment-models` with active filter, keyset pagination,
  stable sizes, catalog product links, and only the currently published
  tech-card revision summary;
- all successful responses set `Cache-Control: no-store`;
- project, unit, fabric, and model page sizes are bounded to 100; cursors are
  stable integer IDs and malformed/negative inputs fail validation;
- no schema revision is required because this stage is read-only over revisions
  `0021` through `0025`.

## API contract

```text
GET /api/crm/projects
  status?: queued | in_progress | on_hold | completed | cancelled
  assigned_to_user_id?: positive integer
  cursor?: positive project ID; returns rows with id < cursor
  limit: 1..100, default 50

GET /api/crm/projects/{project_id}
  unit_cursor?: positive unit ID; returns rows with id > cursor
  unit_limit: 1..100, default 50

GET /api/crm/reference/fabrics
GET /api/crm/reference/garment-models
  is_active?: boolean
  cursor?: positive entity ID; returns rows with id < cursor
  limit: 1..100, default 50
```

The next cursor is the final ID in the current page and is present only when a
following page exists. A project-detail response with inconsistent source
evidence returns `409` rather than silently hiding missing or duplicate unit
data.

## PII boundary

The project DTO contains the internal project/order IDs, status/version,
item/unit counts, assignee ID, paid timestamp, and lifecycle timestamps. It does
not contain:

- customer email, phone, name, or profile measurements;
- city, address, CDEK pickup point, or delivery method;
- project/order amounts or payment method/provider identifiers;
- constructor `customization_snapshot` values;
- fulfillment, payment-attempt, or provider evidence IDs.

If production later needs constructor measurements, add a separate reviewed DTO
with field-level validation and a narrower permission/audit policy. Do not add
the raw customization JSON to these list/detail contracts.

## Verification

- Ruff lint, format verification, and legacy-entrypoint syntax pass;
- all 275 backend unit/contract tests pass;
- ASGI contract tests prove no-token `401`, missing-permission `403`, exact
  `crm.access` use, default-off route registration, bounded project/unit keyset
  pagination, assignee filter, `no-store`, explicit response fields, reference
  projections, `404`, validation `422`, and corrupt-evidence `409`;
- the API test seeds contact, address, provider, and customization secrets and
  proves none are present in the project detail JSON;
- local and deployment Compose files render with the new flag;
- the unchanged linear Alembic chain still compiles offline for full PostgreSQL
  upgrade and downgrade through `0025`.

No live PostgreSQL query plan/concurrency proof, real target bearer session,
reverse-proxy check, staging browser flow, or access-log integration was
available. `CRM_API_ENABLED` remains false until those checks are performed.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Explicit DTOs and repository/service/router boundaries; no ORM response leakage. |
| Security and privacy | 20/20 | Default-off dependency flag, target bearer + `crm.access`, no-store, and tested PII/customization exclusion. |
| Reliability and data safety | 19/20 | Stable bounded cursors, immutable evidence joins, balance source-of-truth math, and fail-closed integrity checks. |
| Compatibility | 20/20 | Additive read-only routes; legacy/PWA behavior and database schema are unchanged while disabled. |
| Verification | 15/20 | Full local/offline gate and ASGI contract pass; live PostgreSQL/identity/proxy/browser evidence remains. |
| Total | 94/100 | The bounded read slice exceeds the requested threshold without claiming staging readiness. |

## Activation checklist

1. Apply migrations through `0025` and complete the CRM project/reference/
   production/material reconciliation queries from stages 28-32.
2. Verify target identity role bootstrap grants `crm.access` only to intended
   manager/admin accounts.
3. Exercise the four routes with a real manager token and prove a customer token
   receives `403`.
4. Check PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` for representative project,
   unit, fabric, and model pages at staging data volume.
5. Verify the reverse proxy does not cache responses and preserves Authorization
   headers without logging bearer values.
6. Enable `CRM_API_ENABLED=true` only in staging, run the staff browser contract,
   and monitor `401`, `403`, `409`, `422`, and latency before production.

## Next bounded slice

1. Add staff mutation endpoints for assignment and project/unit state changes,
   with expected-version preconditions, reason codes, actor evidence, and exact
   conflict mappings.
2. Add planning and material commands using existing immutable plan revisions
   and hashed idempotency keys.
3. Add private CRM upload/download HTTP routes behind the same actor dependency,
   with multipart limits and access-event verification.
4. Add a narrow audited endpoint for production customization only after its
   data contract and permission policy are defined.

## Rollback

Set `CRM_API_ENABLED=false` and restart the backend. This removes all CRM staff
routes without changing projects, references, plans, ledger entries, files, or
identity roles. No migration rollback is needed or appropriate for this stage.
