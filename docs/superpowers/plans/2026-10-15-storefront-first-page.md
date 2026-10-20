# Storefront first page implementation plan

**Goal:** Render real public clothing on the first HTML response for `/` and
`/catalog`, without waiting for hydration or repeating the first browser GET.

**Architecture:** Server-only entry loads one bounded public page through
FastAPI. Shared pure catalog types/query serialization identify the initial
page. Each mounted storefront resource owns its initial snapshot and subsequent
browser requests; no global cache, account data or localStorage catalog.

**Constraints:** Next 16.3 installed docs; preserve the existing design, default
filters, search debounce, cursor pagination, error retry and account isolation.
`PlatformEntry` remains synchronous for the client order background. Public
fetch uses no-store, a two-second timeout, no cookies or authorization forwarding.
Do not commit, stage, push or deploy this unfinished release.

### Task 1: Initial snapshot and browser lifecycle

Files: `frontend/lib/catalog/pagedResource.ts` and its `.test.mjs`;
`frontend/lib/catalog/storefront.ts`; `frontend/lib/api/storefront.ts`;
`frontend/hooks/catalog/useStorefrontProducts.ts`.

- [x] RED: seed ready/error snapshots; attach loader without replacing them or
  issuing first GET; load next cursor; explicit reload fetches the first page;
  changed keys cancel late responses; unseeded consumers still refetch by default.
- [x] Extract pure types/query serialization; derive the query key from URL
  parameters excluding cursor. API client re-exports the existing public types.
- [x] Add optional constructor seed and opt-in reuse of settled current state
  on resource start. `reload()` always bypasses reuse. Reconnect cancels pending
  work and clears loadingMore while retaining settled items/cursor.
- [x] Initialize the storefront resource only from a matching query seed;
  preserve active=false and the 250 ms search debounce. Run targeted tests.

### Task 2: Server entry and initial cards

Files: `frontend/lib/server/backend/storefront.ts` and `.test.mjs`;
`frontend/components/platform/ServerPlatformEntry.tsx`;
`PlatformEntry.tsx`, `ServiceHome.tsx`, `ServiceSearchResults.tsx`;
`frontend/app/page.tsx`, `frontend/app/catalog/page.tsx`.

- [x] RED: production browser/no-JavaScript sees four home products and 24
  catalog products in HTML; hydration issues no first-page GET; search and
  pagination request real backend pages. Server outage gives error/retry.
- [x] Real loopback HTTP test verifies `/api/catalog/products`, exact filters,
  no cookie/auth forwarding, no-store, repeat freshness, safe errors and timeout.
- [x] Server-only helper returns a serializable matching page/error seed. Do
  not forward raw backend errors. Page calls the async server entry; synchronous
  entry passes optional seed to the active home/catalog resource.
- [x] Verify actual backend requests, non-JS HTML, hydration, pagination,
  filters/search/late responses, outage retry and account behavior in browser.

### Task 3: Verify release stage and measure

- [x] Full frontend tests, ESLint, production build/TypeScript; independent
  review of server/client boundary and lifecycle. Fix confirmed findings.
- [x] Alternating cold browser comparison against the previous font-optimized
  build under identical conditions. Inspect LCP, request ordering and errors;
  report the actual result, including any regressions or synthetic limits.
- [x] Refresh architecture map and release journal, including route dynamic
  rendering and remaining work. Validate offline map and phone geometry.
- [x] Stop owned fixture processes and remove only owned synthetic DB/buckets/
  private OTP configuration. Leave shared PostgreSQL/MinIO and the goal active.

Evidence: docs/release-refactoring.md, stage 15 October public first-page SSR.
This plan is complete locally; the complete release goal and physical-phone/production gates remain open.
