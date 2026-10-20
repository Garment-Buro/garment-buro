# Owner community landings implementation plan

> **For agentic workers:** Use superpowers:executing-plans in the current checkout. Steps use checkbox syntax for tracking.

**Goal:** Let an existing active community owner create, edit and publish their own catalog collection and landing.

**Architecture:** Reuse PartnerLanding, PartnerLandingProduct and the existing landing validators. Resolve owner identity on the server; serialize writes with account/partner changes and use an integer version for both owner and administrator edits. Keep public reads separate from authenticated editor reads.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL/Alembic, Next.js, React.

**Spec:** `docs/superpowers/specs/2026-10-15-public-people-and-communities-design.md`, stage 4.

## Global constraints

- No duplicate community table, product identity or copy of landing content.
- Owner routes derive partner_id from authenticated User; ordinary users gain no partner permissions.
- Private editor responses are no-store. No automatic publication.
- Public visibility requires a published landing, active partner and active user.
- Pending operations belong to the current account lifetime; token rotation preserves input.
- Local changes remain unstaged and uncommitted; production is unchanged.

### Task 1: Owned backend commands and conflict protection

**Files:** partners models/repository/service/schemas/router; migration `20261016_0065_partner_landing_versions.py`; contract `test_partner_owner_landings.py`; integration `test_partner_landing_schema.py`; existing migration/lifecycle tests.

**Interfaces:** POST `/api/partner/own-landings` consumes the existing create DTO and returns PartnerLandingResponse with version 1. GET `/api/partner/own-landings/{landing_id}` returns the owner's record or 404. PATCH the same path consumes the existing update DTO plus required positive `expected_version`, returns the incremented version, or 409 without changing fields/products. GET `/api/partner/own-landings` returns bounded editor pages. This separate namespace avoids colliding with the existing public GET `/api/partner/landings/{slug}`. The administrator PATCH uses the same version contract.

- [x] Write HTTP tests that create with two real identity sessions, assign partner roles, and verify owner derivation, ordinary-user/guest denial, foreign-record 404, forbidden client partner_id, persistence after app restart, draft/public transitions and stable catalog product order.
- [x] Run those tests before production edits; missing owner routes must produce the observed failure.
- [x] Add version migration with existing rows initialized to 1 and a positive CHECK. Lock order is User → PartnerProfile → landing; freshly reload state under locks. Every edit claims the expected version through a conditional SQL UPDATE. Resolve all owners on the server.
- [x] Reuse public_product_ids for selectable products. Reject hidden/demo/inactive-category/missing product IDs when selected and recheck all IDs at publication. Status-only removal from publication must work even if a selected product was withdrawn. Drafts may have an empty collection; owner publication requires a selected product.
- [x] Add bounded owner list pagination without breaking the existing cabinet list while the UI moves to the bounded interface. A new page endpoint returns `{items,next_cursor}` with maximum 24 rows and query-bound keyset cursor.
- [x] Verify concurrent stale owner/admin writes on PostgreSQL, stale in-session ORM state, partner suspension/account deletion, slug collisions and rollback of both version and ordered product links.
- [x] Verify migration upgrade/downgrade preserves historical landing content/products and ORM/schema parity; run existing partner/identity/community tests and independent review.

### Task 2: Owner cabinet collection editor

**Files:** frontend partner API/types, focused landing editor controller/hook/components, PartnerDashboard/PartnerLandingsCard, partner cabinet account boundary.

**Interfaces:** `PartnerLanding.version`; update payload requires `expected_version`. The editor uses authenticated runForCustomer and confirmed server DTOs; a 409 keeps the local draft until explicit reload. The product chooser reads bounded real catalog pages and stores only ordered numeric IDs in the command.

- [x] Read the installed Next.js route/client-component guides before frontend edits.
- [x] Write controller/HTTP boundary tests for create/save/publish/unpublish, latest account, retry and conflict retention. Run and observe missing behavior.
- [x] Add create/edit controls to the existing cabinet, separate save/publication actions, human descriptions of collection/landing fields and a real product picker. Reuse existing landing content/template and public rendering.
- [x] Ensure account changes immediately hide old cabinet/requisites/editor data, abort old reads and suppress late operation results. Preserve drafts on token rotation.
- [x] Run frontend tests, lint, build and real Chromium scenarios at 320/390/736/1280 with two owners and an ordinary user; verify published/withdrawn content using actual Next/FastAPI/PostgreSQL.

### Task 3: Immediate public visibility and project map

**Files:** public landing API cache headers, `partners.server.ts`, `/p/[slug]`, standalone project map source/export, release journal.

- [x] Write a server HTTP cache-contract regression showing a landing withdrawn by its owner cannot be replayed from a previous public response or Next data/page cache.
- [x] Use no-store for revocable landing reads and dynamic page rendering while retaining per-request metadata/page read deduplication. Preserve the existing bounded product fetch and 404/error distinction.
- [x] Update the map with the owner command path, field meanings, page wrappers, completed checks and remaining release work; export self-contained HTML and exercise offline interactions.
- [x] Run full backend/frontend checks and independent review, stop owned fixture processes and remove only exact owned test DB/buckets/configs. Record measured results without claiming a production release.

## Review boundaries

Task 1 can be reviewed independently before frontend work. Tasks 2–3 remain required after that boundary; a completed API does not mean the owner workflow or release is complete.

## Verified local outcome · 2026-10-16

- Backend: 813 tests passed without skips against real PostgreSQL 17 and MinIO; Ruff passed. Migration 0065 upgrade/downgrade, stale ORM data and concurrent owner/admin CAS independently exercised.
- Frontend: 424 tests passed without skips; full ESLint and final production build passed. Eight new tests cover owner transport/controller behavior; independent reviewer reran 19 focused tests with no open Critical/Important findings.
- Actual production-built Next + FastAPI + PostgreSQL: two owners and an ordinary user; private ordered draft, publication/SSR without JS, immediate withdrawal404, retained dirty text,409/reload,503/retry,401/token refresh without losing editor, foreign404, ordinary-user denial and account switch during pending PATCH. Widths320/390/736/1280, no JS errors or horizontal overflow. This is a synthetic local fixture, not production proof.
- Map export: 188 reachable components, 432 frontend file descriptions/metadata and 16 page shells. Four Chromium offline harnesses pass at320/390/736 with no external requests or JS errors.
- Exact owned Next/FastAPI processes stopped; synthetic PostgreSQL database, three empty MinIO buckets and private0600 credential/OTP config removed. Shared PostgreSQL/MinIO retained.
- This owner-community stage is complete locally. The broader release remains active; constructor/order/pricing, residual cleanup, real-phone and container/recovery/public release checks remain required. No Git stage/commit/push or production switch.
