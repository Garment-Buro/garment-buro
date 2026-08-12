# Stage 40: identity access projection for staff cabinets

Status: complete locally; frontend cabinet integration and live PostgreSQL proof pending

Quality score: 94/100

## Scope

This stage adds one authenticated, read-only identity endpoint:

```text
GET /api/auth/access
```

It returns the current active user's effective roles and permissions as sorted,
deduplicated string arrays. The projection is loaded from `users -> user_roles
-> roles -> role_permissions -> permissions`; it is never read from the access
token or trusted from browser state.

The response is intentionally separate from the existing login, refresh, and
profile payloads. This preserves their frontend contract and avoids embedding a
stale authorization snapshot in a long-lived persisted session. Cabinets can
refresh access independently whenever they enter a protected surface.

## Security boundary

- a valid current identity access token is required;
- inactive, blocked, deleted, expired, and revoked sessions remain rejected by
  the existing identity dependency;
- the endpoint only exposes authorization codes already assigned to its caller;
- `Cache-Control: no-store` prevents browser/proxy caching of the projection;
- frontend visibility remains presentational only: every CRM/catalog/order
  endpoint continues to enforce its own server-side permission;
- no email, phone, profile data, refresh token, session ID, or audit data is
  included.

The projection includes custom database role/permission strings without making
the frontend an authority. This keeps the response forward-compatible while
server policy continues to use the typed permission codes required by each
operation.

## Compatibility

- no database migration or write path is introduced;
- existing `AuthSessionResponse` and `AuthUserResponse` stay unchanged;
- the route only exists when `IDENTITY_API_ENABLED=true`, matching the rest of
  the refactored identity API;
- deterministic ordering makes client caching comparisons and contract tests
  stable without granting cacheability.

## Verification

- repository/service tests prove the customer projection and the deduplicated
  union for a user assigned both customer and manager roles;
- the HTTP contract proves the exact customer payload and `no-store` header;
- all 281 backend unit/contract tests pass;
- Ruff lint and format checks pass, including the legacy entrypoint syntax
  gate;
- the complete offline PostgreSQL Alembic upgrade and downgrade chain remains
  valid at the single `20260812_0027` head.

Live PostgreSQL query-plan/latency evidence is still pending because the local
Docker runtime is unavailable. The endpoint should be exercised with real
manager/admin assignments in staging before the CRM cabinet flag is enabled.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Repository query, service snapshot, schema, and router preserve dependency direction. |
| Security | 20/20 | Current active session, caller-only projection, no-store, no client-side authority. |
| Reliability | 19/20 | Sorted/deduplicated effective access; live PostgreSQL plan remains pending. |
| Compatibility | 20/20 | Additive endpoint with no session payload or schema change. |
| Verification | 15/20 | Full local/offline gate; staging role and latency proof unavailable. |
| Total | 94/100 | Safe foundation for guarded staff navigation without overstating live proof. |

## Next bounded slice

1. Add a default-off `NEXT_PUBLIC_CRM_CABINET_ENABLED` build flag that requires
   identity session v2.
2. Add a typed frontend access client and authenticated access coordinator.
3. Render the CRM navigation and pages only after `crm.access` is confirmed,
   while preserving backend 403 enforcement.
4. Exercise refresh, revocation, role removal, and multi-tab behavior against
   staging PostgreSQL before production enablement.

## Rollback

Remove the additive route and its projection method. No data or migration
rollback is required. If frontend integration is rolled back independently,
leaving the unused read-only endpoint deployed does not change authorization of
any existing operation.
