# Constructor account lifetime and availability plan

> **For agentic workers:** Use superpowers:executing-plans in this existing checkout. Steps use checkbox syntax for tracking.

**Goal:** Keep guest work through its first login while preventing another account, a late image read or an unavailable product from reusing the previous editor state.

**Architecture:** An explicit account-lifetime policy owns the React editor boundary. A product resource returns data only for the currently requested ID and distinguishes load failure from usable product data. Existing ProjectEditor remains the versioned server command owner; cancellation is checked between each dependent read.

**Tech Stack:** React 19, installed Next.js 16.3, existing FastAPI/PostgreSQL/MinIO.

**Spec:** `docs/release-refactoring.md` full release requirements; `docs/superpowers/specs/2026-10-15-public-people-and-communities-design.md` account lifetime invariant.

## Global constraints

- Guest → first authenticated account preserves new unsaved canvas input. Token rotation preserves it. An authenticated lifetime ending or changing discards its canvas/input and late results immediately.
- Existing project IDs remain account scoped and reloaded through authenticated backend commands. Product identity never falls back to another product or zero for a cart write.
- The current UI and geometry remain; no duplicate project store or snapshot schema.
- Old local projects remain available only for deliberate migration until the residual cleanup stage. This plan does not turn them into authoritative server records.
- No stage/commit/push/deploy; the full release and server customization pricing remain required after this plan.

### Task 1: Account boundary and asynchronous local input

**Files:** `components/constructor/ConstructorPage.tsx`, `hooks/constructor/useConstructorPageController.ts`, focused lifetime policy/tests under `lib/constructor/`.

- [x] Run the current production-built editor with two synthetic accounts. Add text to a new canvas, switch accounts through the real session channel/cookies, and observe the old decoration remains. Retain safe RED evidence.
- [x] Add literal policy tests: guest→login retains new canvas; authenticated→other/login-epoch/logout resets; same account epoch/token refresh retains; existing project changes reset. Observe failure, then implement the policy and integrate it with the real React key.
- [x] Cancel pending local image decoding on editor disposal and reject late reads before adding variants. Recheck editor lifetime before asynchronous canvas actions. Keep the guest login handoff distinct from an authenticated account change.
- [x] Verify real canvas clearing, guest OTP/save, token refresh, late image input, pending save during account switch and reload/foreign project denial at320/390/736/1280.

### Task 2: Product availability and dependent project reads

**Files:** public catalog detail under `backend/app/modules/catalog/`, storefront contract tests, `frontend/lib/api/storefront.ts`, `hooks/constructor/useConstructorProduct.ts`, focused product resource/tests under `lib/constructor/`, `lib/projects/editor.ts` and its tests, controller/workspace status.

- [x] Add a behavior test that changes the requested product to null or another ID with a delayed/failed response; the old product/size/fit must become unavailable immediately. Add malformed ID and retry cases. Observe RED.
- [x] Return only the current resource's successful product; abort obsolete reads and preserve selected fit for a retry of the same valid product. Purchases require the actual current canonical product.
- [x] Add a project-load cancellation test: account changes while GET metadata is pending; resolving it must not start an images request or publish old data. Check cancellation between dependent reads.
- [x] Verify a saved project whose product is withdrawn/deleted retains the server document but does not render or purchase the former product. Loading/private access failures must not become a new project save.

### Task 3: Verification and map

- [x] Run frontend full tests, ESLint, TypeScript/production build, relevant backend contracts and independent review. Test failures must be resolved before claiming this stage complete.
- [x] Update the standalone project map with the actual new boundary and availability behavior; preserve V1/V2 file classification and page/provider explanations. Exercise all offline map harnesses.
- [x] Stop only exact owned fixture processes; remove exact synthetic database/buckets/private config. Preserve shared PostgreSQL/MinIO. Record measured results and remaining full-release requirements.

## Verified result, 16 October

- Browser RED retained one decoration after account switch. Final real PG17/MinIO/production-built browser run passes guest OTP, persistence/reload, rotation, account switch, held FileReader/POST, foreign404, withdrawal/purchase suppression, deletion and explicit reload in the same editor; widths320/390/736/1280, no JS errors.
- Browser also exposed the admin-compatible product detail accepting inactive products. The constructor now uses public detail with the shared publication policy, bounded canonical ID and no-store200/404; private/pending media excluded. SQLite+PostgreSQL contracts include variants, hidden/demo/missing/withdrawn products and invalid IDs.
- Frontend437 tests (0skip), full lint and production build; backend825 tests (0skip),393.64s with real PostgreSQL/MinIO, full Ruff. Independent reviews: no Critical/Important;20 focused and10 transport/resource tests rerun.
- Map:188 reachable components,435 metadata files,16 shells, five offline browser harnesses. Exact owned DB/three buckets/media/private config removed; owned Next/FastAPI stopped, shared infrastructure preserved.
- Full release remains active: server customization pricing/hardware, orders/pagination, residual cleanup, phone/container/backup/rollback/CI/public E2E. No stage/commit/push/deploy.
