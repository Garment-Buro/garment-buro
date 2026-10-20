# Retire legacy catalog and landing editor

> **For agentic workers:** execute this bounded stage inline, then request focused review. Preserve all unrelated working-tree changes.

**Goal:** Remove the old storefront/editor and their exclusive dependencies while preserving current storefront, cart, partner landings and order URLs.

**Architecture:** Direct order URLs use PlatformEntry as their background; intercepted orders retain the existing parallel modal route. Active cart selection belongs to the cart domain. A static `/catalog` entry reuses PlatformEntry with `initialCategory="clothing"`. This preserves static rendering of `/` and avoids a second catalog implementation.

**Tech stack:** Next.js App Router, React, TypeScript, Zustand, node:test, browser verification with the installed Playwright runtime.

**Spec:** `docs/release-refactoring.md` and the user's release objective; this is one stage of that full scope, not the completed release.

## Constraints

- Preserve legal copy, links, current cart behavior and individual landings.
- Do not delete catalog APIs used by constructor, administration or partner landings.
- Do not commit, stage or deploy the large existing worktree as part of this stage.
- Read installed Next.js route/layout guidance; verify behavior, not deleted symbol names in source-regex tests.
- Remove source-regex checks exclusive to retired UI; retain independent constructor, cart and current chrome checks.

## Task 1: Preserve current entry behavior

- [x] Record initial browser failures: `/admin/editor` returned200; the direct clothing selection target did not open the current catalog. Keep `/product/[id]` unavailable.
- [x] Add a failing behavioral chrome check: an order URL has the home background and hides global site chrome. Also verify reserved `/order/success`, `/order/error` and nested404 paths retain ordinary chrome.
- [x] Preserve existing active-cart selection using explicit active ID, fallback to last item, and an empty cart. Three behavioral tests exercise the extracted helper.
- [x] Switch the direct order page to PlatformEntry. Preserve Popup close-to-home and the unchanged intercepted order route.
- [x] Create the static `/catalog` entry; pass the initial category through PlatformEntry to ServiceHome. Update library creation action and reset the URL when leaving this catalog.

## Task 2: Remove obsolete frontend branches

- [x] Delete editor and disabled product routes, old catalog/product components, exclusive hooks and utilities, old logo editing, settings store/client and footer editing wrapper.
- [x] Preserve shared footer content with ordinary shared Link and DecryptedText.
- [x] Remove the product-page-only add-card branch from the shared expanded cart, its unused props and product-card quantity variant. Keep current row/collapsed variants.
- [x] Remove obsolete test cases/imports, retaining independent active behavior checks.
- [x] Delete the four remaining components with no app imports: PlatformHome (+CSS), DesignPopup, Divider, Textarea. The refreshed graph has179 components, all reachable; this does not prove every export/style/asset is used.
- [x] Regenerate Next.js route types and check TypeScript resolution and remaining imports.

## Task 3: Verify and document

- [x] Run complete frontend tests (**346 passed,0 skipped**), lint (no warnings), TypeScript and production build. `/` and `/catalog` are static in the build output.
- [x] Verify HTTP retirement, clothing selection/back/Escape/reload, direct order overlay/close/reload, seven legal footer links at390/1440 and individual landings in the browser.
- [x] Verify actual OTP login, a backend-empty project library, creation action to `/catalog`, real rendered product cards and cleanup of the disposable account.
- [x] Request focused independent review twice; no confirmed remaining findings. Reviewer independently ran40 and36 narrowed checks respectively.
- [x] Refresh the local map and release journal; keep remaining backend content/runtime, demo data, performance and release gates explicit.

## Evidence and limits

- Local production build runs as `.next/standalone/server.js` at `http://localhost:3100`; public/static directories are linked inside the ignored build artifact for this local proof. The previous local `next start` process was replaced after verifying ownership.
- Requests use the existing disposable backend at8108 with real PostgreSQL/MinIO fixtures from earlier stages. Backend code was not changed or fully re-tested in this stage;593 is the previous backend stage's result.
- An initial auth probe on127.0.0.1:3101 correctly received403 because the fixture trustslocalhost:3100. The final authenticated proof used that configured origin; backend origin protection was not relaxed.
- Browser scripts: task-owned `check-retired-catalog.cjs` and `check-project-create-entry.cjs`. They do not create payments. OTP is read privately from the disposable encrypted outbox; this does not prove SMTP delivery.
- Direct order proof uses an unavailable order ID to verify composition, order ID propagation and close/reload. The intercepted route's source and dependencies were reviewed; a successful purchase followed by the intercepted modal remains part of the overall release E2E gate.
- Offline map checks:13 page variants,5 tabs,179 component entries,736/390/320 widths, no JS errors or HTTP requests, persisted selection restored.
- Build retains the existing Next.js font warning for missing Alumni Sans SC fallback metrics. Font loading remains in the performance stage.
- No commit, staging, push, deployment or production changes in this stage. Backend content/settings, legacy runtime/Compose, demo data, server pricing, checkout/history behavior and release rehearsal remain open.
