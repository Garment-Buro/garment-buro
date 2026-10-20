# Partner collection products

**Goal:** `/p/[slug]` requests only its configured models, never the full
catalog; unpublished products remain hidden and outages are shown honestly.

**Design:** Bounded public `/api/catalog/collection-products?ids=…` (1–50 IDs),
one scalar product SELECT and one ranked public-image SELECT. Small DTO:
id/title/decimal price/description/image URL/alt. Reuse public policy and media
selection code; preserve collection image priority (desktop poster, mobile
poster, mobile card, image_left). Return configured order with duplicate IDs
removed. No variants, inventory hydration or unbounded product ORM read.

Frontend server helper fetches this DTO with a two-second timeout and 60-second
public revalidation. Empty ID list makes no request. Landing is read first;
404 stops before product loading. A model API outage displays an explicit
native GET retry form, separate from an empty collection. Remove unused full-catalog and
single-product server helpers after verifying all consumers. No schema change,
commit, stage, push or deployment in this stage.

- [x] RED contract: selected order/dedup, absent/inactive/demo/hidden-category
  exclusion, exact price/description, safe preferred image, invalid ID bounds,
  two SQL queries independent of selected count and no variant reads.
- [x] Implement backend query/schema/service/router; targeted SQLite and real
  PostgreSQL tests pass without skips. Existing storefront behavior stays green.
- [x] RED real HTTP frontend helper: bounded selected IDs only, empty short
  circuit, configured order, no forwarded auth/cookies, HTTP failure/timeout.
  Implement small DTO and page/components; remove unreferenced old helpers.
- [x] Browser through real FastAPI/PostgreSQL/MinIO: published landing/order,
  selected-only models, missing slug, empty list, unavailable models and retry;
  preserve desktop gate, mobile layout and constructor attribution link.
- [x] Full frontend/backend checks as appropriate, independent review,
  map/journal update and offline check. Clean up only owned fixtures.

Visual-QA addition: existing landing reveals concealed the server HTML without
JavaScript. Default content/text must remain visible; animate only offscreen
elements after effect initialization. Share observer lifecycle, skip reduced
motion/absent observer, clean pending attributes on unmount. Browser RED/GREEN
covers disabled/blocked JavaScript, no observer, reduced motion and normal scroll.

This stage does not complete the full release: demo communities/people,
editor/account races, server customization price, order pagination/state and
deployment/restore/public E2E remain required.

Local stage verified: 635 backend tests, 376 frontend tests, ESLint,
production build and real-backend browser scenarios. No deployment performed.
