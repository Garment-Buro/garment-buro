# Customization pricing implementation plan

> **For agentic workers:** Use superpowers:executing-plans in the existing authorized checkout. Steps use checkbox syntax.

**Goal:** Preserve the user's 80 RUB scale rule while making previews and checkout use one replaceable server policy.

**Architecture:** Catalog pricing owns bounded placement input, Decimal calculation and normalized snapshots. Storefront exposes a small no-store public preview. A cancellable debounced frontend resource binds prices to the exact product/placements. Cart and orders reuse the policy; historical snapshots and accepted-order replay retain their semantics.

**Tech Stack:** Existing FastAPI/Pydantic/SQLAlchemy, React external stores, Next.js16.3; no new dependency.

**Spec:** `docs/superpowers/specs/2026-10-16-customization-pricing.md`.

## Global constraints

- Keep `max(80, round_half_up(80 * scale))` per placement; both views count.
- Canonical Product supplies base price. Client prices never determine a new order.
- Preserve current checkout confirmation, delivery proof, inventory and payment recovery.
- No stage/commit/push/deploy; no invented hardware catalog or tariff editor.

### Task 1: Server policy and order/cart boundaries

**Files:** `backend/app/modules/catalog/pricing.py`, `storefront_router.py`, `storefront_service.py`, `storefront_repository.py`; carts/orders schemas/service; focused unit and checkout contract tests.

**Interfaces:** `ConstructorPriceInput(decorations=[{uid,scale}])`; `calculate_customization_price(base_price, input)` returns a typed quote; `price_customization(base_price, customization)` returns authoritative total and copied snapshot. Preview route `POST /api/catalog/products/{id}/price` returns product_id, policy_revision, decoration_base_price, base_price, customization_price, total_price and per-UID prices.

- [x] Add checkout regression: base100.25 + scale1.5 print120 + scale0.25 text80, quantity2 + delivery50 =650.50. Existing code must fail (409). Tampered price fields must never lower it; replay must not call payment twice.
- [x] Add literal policy tests for minimum80, scale1.5→120, half80.5→81, both views, no decorations and invalid bounds/duplicates. Observe RED.
- [x] Implement one Decimal policy and copied snapshot normalization; validate input at cart/order schemas. Use it in `_order_item` and batch constructor Product reads in cart writes. Preserve historical imports and unrelated legacy metadata.
- [x] Add public preview tests: exact quote, one bounded price query, no-store, hidden/demo/missing404, malformed422 and no writes. Reuse public publication policy.
- [x] Run focused backend tests/Ruff and resolve failures.

### Task 2: Current server preview in constructor

**Files:** `frontend/lib/constructor/priceResource.ts` and tests; `frontend/lib/api/storefront.ts` and tests; `frontend/hooks/constructor/useConstructorPrice.ts`, derived/controller hooks, constructor workspace/notice, customization builder.

- [x] Add resource tests: newer scales/product hide the old quote; obsolete responses/cancel cannot publish; debounce reduces burst to last request; errors/retry; response placement/product mismatch rejected. Observe RED.
- [x] Implement compact request transport and cancellation/debounce. Hook returns ready only for the current fingerprint; x/y/rotation/comment do not enter it.
- [x] Remove browser pricing formula. Populate all displayed line/total prices and cart payload from current server quote. Disable purchase while pending/error, render pending labels and retry; project save may retain a non-authoritative preview.
- [x] Verify full frontend tests/lint/build and real constructor browser behavior, including scale edits and unavailable preview.

### Task 3: Review, evidence and offline map

- [x] Independently review changed pricing/payment boundaries; resolve substantive findings.
- [x] Run relevant backend contracts plus full suite if cross-boundary regressions warrant it. Record actual results; preserve shared fixture infrastructure.
- [x] Explain formula/source/change location in release notes and standalone project map. Exercise offline navigation/provider/file-description harnesses.
- [x] Stop exact owned runtime fixtures and remove only their synthetic data. Report local result and remaining full release work.

## Verified result, 16 October

- Backend848 passed,0 skipped,1086.19s with real PG17/MinIO; full Ruff. Final24 pricing/checkout tests passed after adding underclaimed409 and cart batch assertions.
- Frontend444 passed,0 skipped; full ESLint and production build/TypeScript. Existing Alumni Sans SC fallback warning remains.
- Production-built Chromium pricing and constructor lifetime harnesses pass: held/obsolete prices,8 edits→1 POST, scale171 RUB, both views,503/retry, matching persisted cart, saved-notice retry, OTP/account switch/late reads/deleted model;320/390/736/1280,no JS errors. Screenshots inspected.
- Independent review Important about hidden retry fixed with two actual React-render RED→GREEN tests; follow-up review has no open Critical/Important.
- Offline map188 components,437 metadata files,16 shells; six harnesses passed without HTTP requests/JS errors. Formula change location and non-Provider pricing hook explained.
- Exact owned Next/FastAPI stopped; synthetic DB/three buckets/media/private fixture removed. Four full-suite DBs removed. Shared PostgreSQL/MinIO preserved. No stage/commit/push/deploy. Full release still active.
