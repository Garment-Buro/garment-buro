# Stage 41: guarded CRM cabinet foundation

Status: complete locally; authenticated staging/API verification pending

Quality score: 92/100

## Scope

This stage connects the frontend/PWA to the read-only staff contracts without
enabling CRM in existing deployments by default.

It adds:

- the build-time `NEXT_PUBLIC_CRM_CABINET_ENABLED=false` flag;
- a build invariant requiring identity session v2 whenever the cabinet is on;
- a non-persisted effective-access store backed by `GET /api/auth/access`;
- a typed same-origin CRM project client;
- a guarded `/admin/crm` production-project list with cursor pagination;
- responsive Russian status presentation and explicit loading, denied, retry,
  empty, and partial-pagination failure states;
- CRM navigation only after the server projection contains `crm.access`.

The first cabinet screen is intentionally read-only. Project status,
assignment, planning, material, and private-file commands remain server-ready
but are not exposed until their staging concurrency and rollback flows have
been exercised with real PostgreSQL/MinIO.

## Security and session boundary

- with the cabinet flag off, `/admin/crm` renders the Next.js not-found surface;
- the flag cannot compile unless `NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=true`;
- access and CRM requests use the existing same-origin `/api` rewrite and an
  in-memory bearer token managed by the refresh coordinator;
- roles and permissions are never stored in `localStorage` or trusted as an API
  authorization decision;
- the UI projection is deduplicated in flight and retained in memory for at
  most 60 seconds to avoid a request from every nested admin component;
- user changes and logout clear or invalidate the effective-access projection;
- every CRM request is still authorized by backend `crm.access`; stale UI state
  cannot grant data access after a role is revoked;
- backend `Cache-Control: no-store` remains the cache boundary for access and CRM
  data in browser and PWA modes.

The existing product/order admin pages have not been redesigned or declared
fully migrated by this stage. Their authorization and legacy compatibility are
a separate cutover. This slice does not weaken their current behavior.

## Deployment contract

Build the frontend with all cabinet prerequisites explicitly coordinated:

```dotenv
IDENTITY_API_ENABLED=true
CRM_API_ENABLED=true
NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=true
NEXT_PUBLIC_CRM_CABINET_ENABLED=true
```

The reviewed identity migration fingerprint and database settings are still
mandatory. `CRM_WRITES_ENABLED` and `CRM_FILES_ENABLED` may remain false for the
read-only cabinet. Build the image again when changing a `NEXT_PUBLIC_*` flag;
changing only the runtime container environment cannot rewrite compiled client
code.

Both primary and local Compose configurations pass the three frontend flags as
explicit build arguments and runtime documentation. Production should not turn
the cabinet flag on until the identity/CRM backend flags and staff role
assignments are already verified in staging.

## Verification

- all 201 frontend architecture/unit/contract tests pass;
- ESLint and the production TypeScript/Next.js build pass;
- the default-off production build returns HTTP 404 for `/admin/crm`;
- the build fails with the expected configuration error when CRM cabinet is on
  while identity v2 is off;
- the enabled production build succeeds and `/admin/crm` returns HTTP 200 with
  the guarded access-loading shell;
- status label and visual-state tests cover every current project state;
- source boundary tests prove default-off wiring in Docker/Compose, same-origin
  authenticated API calls, non-persistence, route gating, permission-gated
  navigation, and data loading;
- both Compose files render successfully (warnings only reflect intentionally
  absent local secrets).

No real staff login, PostgreSQL project list, refresh/revocation flow, MinIO
file flow, browser screenshot at authenticated desktop/mobile viewports, or
staging deployment was available because the Docker runtime and staging
credentials/endpoints are unavailable. Those checks remain mandatory before
enabling the flag outside a disposable environment.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | Typed API/domain/hook/store/component layers; read-only list is intentionally incomplete. |
| Security | 20/20 | Dual build/RBAC gate, no persisted authorization snapshot, backend remains authoritative. |
| Reliability | 18/20 | Refresh integration, in-flight dedupe, cursor paging, safe retry/partial failure; live revocation pending. |
| Compatibility | 20/20 | Default-off, same-origin, PWA/web-safe, no existing route payload changed. |
| Verification | 15/20 | Full local build/test and HTTP flag checks; authenticated staging/browser proof pending. |
| Total | 92/100 | Safe deployable foundation above threshold without claiming unavailable integration proof. |

## Next bounded slice

1. Run the migration/readiness/reconciliation rehearsal on real staging
   PostgreSQL and MinIO.
2. Seed a disposable manager and customer, then prove navigation, 401/403,
   refresh, logout, role removal, and cursor paging in desktop browser and PWA.
3. Add project detail and unit read views only after that contract is green.
4. Expose lifecycle commands one family at a time with expected-version and
   idempotency UX; never reuse a generated idempotency key for changed input.

## Rollback

Set `NEXT_PUBLIC_CRM_CABINET_ENABLED=false` and rebuild the frontend. The route
returns 404 and no cabinet request is made. Backend read APIs can remain enabled
for operators or be independently disabled with `CRM_API_ENABLED=false`. This
stage adds no database migration and no frontend-persisted state to clean up.
