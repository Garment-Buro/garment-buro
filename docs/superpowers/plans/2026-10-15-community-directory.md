# Community directory implementation plan

**Goal:** Replace static repeated community cards and browser-only favorites
with published partner landings and account-owned PostgreSQL favorites.

**Spec:** `docs/superpowers/specs/2026-10-15-public-people-and-communities-design.md`.
This implements stage 2; public user profiles and owner editing remain required.
Use inline execution in this session, with TDD and independent review. No
commit/stage/push/deployment; preserve the existing dirty worktree.

**Architecture:** Directory projection lives in partners, sharing a public
landing policy with slug reads. Favorites have a separate FK table and routes,
reuse existing session/resource/favorite controllers, and never use preview IDs.
One bounded directory SQL SELECT; no landing content, product hydration or PII.
Server initial community cards load in parallel with storefront products.

## Backend

Files: partners/public_policy.py, directory_schemas.py, directory_repository.py,
directory_service.py, directory_router.py; favorites models; migration 0062;
factory/ORM registry; existing partner repository publication read.

- [x] RED contract through real FastAPI: published/active owner policy, exact
  safe DTO, unique rows, newest/name keyset traversal, literal `%`/`_` search,
  bounded input/cursor mismatch, one SQL SELECT and no JSON/product reads.
- [x] Implement projection and query-bound cursor. API `/api/communities` uses
  query/sort/limit/cursor, max 100; disabled partner program exposes no cards.
- [x] RED account favorites: authenticated status/list/PUT/DELETE, repeated
  writes, private isolation, persisted restart readback, unavailable landing,
  policy changes and deleted customer cleanup. Implement separate UserCommunityFavorite
  table, migration and routes `/api/profile/community-favorites`.
- [x] Real PostgreSQL migration upgrade/downgrade and metadata check; parameterized
  SQLite/PostgreSQL contract without skips in authoritative full run.

## Frontend

Files: lib/catalog/communities.ts, lib/api/communities.ts, server/backend/communities.ts;
hooks/catalog/useCommunities.ts, useCommunityFavorites.ts; ServiceCommunityCatalog,
ServiceHome, ServiceCategoryCatalog, ServerPlatformEntry/PlatformEntry; CSS/data/store.

- [x] RED HTTP boundary: encoded queries/cursor, empty status short circuit,
  authentication/no-store on favorites, mutations/cancellation/error propagation.
- [x] Consume bounded API with existing PagedResource and FavoriteController.
  Render real cards and links `/p/[slug]`, no duplicated instances. Explicit
  loading/empty/error/retry and pagination in directory and favorites. Guest
  opens existing authentication UI before saving a favorite.
- [x] SSR initial communities parallel with product seed, no first browser
  duplicate GET. Error seed supports retry. Remove hardcoded community arrays,
  old crops and local preview favorite store after checking consumers.
- [x] Browser: SSR without JS, navigation, search/sort/pagination, two accounts,
  restart readback, error/retry, 320/390/736/1280. Review actual mobile screenshots.
- [x] Full tests/lint/build, independent review, map/journal refresh, offline map
  checks, owned fixture cleanup. Keep remaining release work explicit.
