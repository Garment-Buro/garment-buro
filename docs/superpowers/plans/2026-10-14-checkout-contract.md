# Modern checkout contract Implementation Plan

> **For agentic workers:** Execute this plan inline in the already authorized
> release worktree. Independent review is required after each completed stage.

**Goal:** Replace divergent browser checkout with a real server-owned, replayable purchase flow.

**Architecture:** Preserve modular order/inventory/payment services. Add a signed
delivery quote boundary, validate it only for a new creation request, and share
the client contract and retry controller across both forms. Persist independent
buyer/recipient snapshots in PostgreSQL.

**Tech Stack:** FastAPI, Pydantic, async SQLAlchemy/PostgreSQL, PyJWT, Next.js/React/TypeScript.

**Spec:** `docs/superpowers/specs/2026-10-14-checkout-contract-design.md`.

## Global constraints

- Preserve existing UI copy, guest/auth purchase, CDEK pickup/courier and payment modes.
- No legacy HTTP fallback, fake successful order, client-owned shipping charge or invented logistics.
- Quote validity:15 minutes; directory max age:7 days. Exact persisted replay bypasses expiry.
- No network I/O while holding order/inventory locks. No tokens/PII in logs, URLs or reports.
- Existing dirty worktree belongs to this release. No unsolicited commit/push/deploy.

## Task1: Verified delivery quotes

Files: new `delivery/quote_proof.py`, `delivery/destination.py`,
`checkout/delivery.py`; modify quote schemas/service/router, checkout/service,
orders/schemas/service. Tests: quote proof and HTTP purchase contracts plus
existing quote/checkout suites.

Interfaces:

```python
class DeliveryQuoteProof:
    def issue(self, prepared: PreparedCdekQuote, amount: Decimal, *, now: datetime | None = None) -> str: ...
    def verify(self, token: str, prepared: PreparedCdekQuote, *, now: datetime | None = None) -> Decimal: ...

class CheckoutDeliveryService:
    async def verify(self, session: AsyncSession, command: OrderCreationCommand, *, now: datetime | None = None) -> OrderCreationCommand: ...
```

- [x] RED: submit an otherwise valid order with shipping0 and no signed quote;
  assert no order, inventory reservation or provider payment is created.
- [x] RED: quote pickup using spoofed browser city/address; assert canonical
  database destination, then reject changed quantities, dimensions and amount.
- [x] Implement bounded purpose-signed proof and canonical destination resolution.
  Include request binding in PreparedCdekQuote and return token/canonical fields.
- [x] Invoke checkout delivery verifier after completed creation-request replay
  and before new order writes. Verify missing/invalid/expired proof is safe.
- [x] GREEN: exact retry remains the same order/payment after expiry or directory
  outage; quote failure creates no payment. Keep provider network outside locks.
- [x] Run full backend checks, PostgreSQL proofs and independent review; record evidence.

Task1 evidence (2026-10-14): unsigned shipping0 originally created an order;
spoofed pickup city originally entered the provider request. Both RED cases
now pass. HTTP quote→checkout contracts reject tampering, expiry and malformed
destinations, preserve completed retries through expiry/directory outage, and
produce no free-delivery fallback. Real PostgreSQL: five concurrent retries
while the first provider call waits produce one order/reservation/payment
attempt and one provider call. Full backend:602 passed,0 skipped,116.71s with
four PostgreSQL test DBs and real MinIO. Ruff/format487 files and offline
Alembic up/down0060 passed. Independent review:14 tests passed, no confirmed
remaining findings. An earlier review's malformed-address503 was fixed and
its two HTTP regressions now return422. No frontend source, SQL schema,
commit or deployment changed in Task1. Task1 does not cover Tasks2–4.

## Task2: Buyer and recipient snapshots

Files: checkout schemas/contact, order schemas/models/service, Alembic0061,
notification/delivery consumers and read mapping.

- [x] RED: buyer and recipient differ; assert persisted receipt owner and shipping
  contact remain distinct after restart and recipient cannot read the order.
- [x] Add nullable historical columns, typed public nested contacts and explicit
  domain mapping. Validate contacts before payment; do not create verified sessions.
- [x] Verify migration upgrade/downgrade, real PostgreSQL constraints and affected consumers.

Task2 evidence (2026-10-14): nested-contact HTTP requests originally failed422;
paid email/admin contact originally used the recipient's name. RED/GREEN now
proves guest/auth purchase, persistent read after restart, separate receipt and
CDEK contact, buyer email greeting/admin search, and no recipient or submitted
guest-buyer email ownership. Invalid contacts create no order/payment/session.
Alembic0061: historical NULLs, all-or-none check, metadata equality, real
PostgreSQL upgrade/downgrade and retained existing rows. Fixed unresolved
OpenAPI model references for both bounded-body purchase/quote routes through
one documentation helper; two actual-document reference tests went RED/GREEN.
Final backend:614 passed,0 skipped,124.35s with four PostgreSQL DBs and real
MinIO; Ruff/format490 files, offline Alembic up/down0061, routing and shell
checks passed. Independent final review:11 tests passed, no remaining findings.
Frontend sources untouched; Tasks3–4 and the full release gates remain open.

## Task3: Shared client purchase lifecycle

Files: lib/checkout contract/attempt controller, lib/api orders/checkout,
useCartActionCheckout/useCheckout, checkout utilities/types and delivery UI.

Current source evidence after Task2: both API functions send only Content-Type,
no actor/idempotency headers; `requestJson` does not add authorization. Both
quote callers omit point code/courier address. Cart quoting has no active-form
guard, and separate `/checkout` keeps only a numeric fee and has a mock-success
branch. `ApiError` discards structured checkout failure code/order_id, needed
for a deliberate later payment attempt after a known rejection. Preserve safe
typed error metadata when implementing the purchase lifecycle. Read the relevant
installed Next.js guides required by `frontend/AGENTS.md` before frontend edits.

- [x] RED: capture both submissions and assert items/claimed_total_price,
  quote proof, Idempotency-Key and exactly one actor header.
- [x] Implement one typed boundary, operation reuse and shared cancellable quote
  state; preserve semantic payload and original proof for uncertain retries.
- [x] Remove mock success, hardcoded package/city fallback and duplicate legacy
  payload builders. Close hidden quote/payment work until the form is active.
- [x] Prove lost response, reload, repeated click, address/item change and account
  switch; no duplicate order, no stale quote and no lost cart on failure.

Task3 evidence (2026-10-15): both forms use the same nested contacts/items,
signed quote, key and exactly one actor header. Shared operation/quote tests
prove double click, lost response, reload, original-proof reuse, account switch,
blocked storage, changed items/address/recipient, abort/expiry and terminal
versus ambiguous rejection. Definite pre-order stock/catalog/delivery409 codes
allow correction; generic conflicts and unknown responses retain the operation.
Managed payment rejection retains the order for review, forbids a new charge,
and offers explicit archival for another purchase while retaining guest access.

Actual production-build Chromium (390x844), with release identity/catalog flags:
/checkout guest+courier+card and home cart customer+pickup+QR passed. Separate
buyer/recipient, closed-form zero quote/options requests, moderation hiding QR,
reload with the same key/body/proof and account switch/logout were checked.
Portal recipient Save originally submitted a purchase; RED/GREEN now sends no
order. These browser probes replace API transport; they are not Task4 integrated
backend/provider evidence. Legacy /order/success now redirects307 to /profile.

Final local verification:362 frontend tests,0 failures/skips; ESLint and release
build (including TypeScript) passed, with the existing Alumni Sans SC fallback
metrics warning. Backend618 passed,0 skipped,124.28s with four PostgreSQL DBs
and real MinIO. Ruff/format and git diff --check passed. Independent Task3 review
reported no remaining Critical/Important findings and reran22 targeted tests.
Task4 and full release gates remain open; no commit, push or deployment.

## Task4: Integrated verification

- [x] Browser quote→purchase and durable order view for guest/auth, both forms,
  pickup/courier, invalid stock, changed price, outage and retries.
- [x] Frontend full tests/lint/TypeScript/build, backend full suite/migrations,
  independent review. Refresh map/journal with actual scope and open release gates.

Task4 evidence (2026-10-15): production Next build → actual FastAPI → migrated
PostgreSQL, with only CDEK/payment provider transports replaced. Twelve Chromium
390×844 scenarios cover eight form/actor/delivery combinations, stock rejection,
price change in both forms and quote outage. Four lost-response/reload cases
cover guest/customer in both forms and preserve the exact key/body/proof.
Actual backend process restart retained twelve order reads with the original
customer sessions/guest capabilities, with zero new provider calls on read.

The first price probe restored the old catalog value; review correctly rejected
that as proof of recovery at the new price. Added RED/GREEN HTTP/transport/cart
regressions and explicit checkout_price_changed409 with authoritative line prices
from the existing catalog batch. Both forms now show1500 per item/3250 total
while the catalog remains1500, require another click and use a new operation key.
No failed purchase writes an order/reservation/payment. Atomic cart updates retain
customization and reject edited snapshots; account guards precede their application.

Final checks:619 backend passed,0 skipped,196.50s with four disposable PostgreSQL
databases and real MinIO;367 frontend passed,0 failures/skips; ESLint, production
build/TypeScript, Ruff491 files and Alembic up/down0061 passed. Independent review
found no remaining Critical/Important findings;27 targeted frontend tests passed.
The reviewer inspected the integrated script/result without rerunning the matrix.

Coverage limits: all integrated payments are card/pending, payment return is
synthetic, and no real provider/capture/webhook/worker/SMTP/media write is proved.
Restart checks wait for DOMContentLoaded, the real order API response and visible
order content. One earlier wait for the entire page load exceeded30s; background
page performance remains an open release gate. This completes the checkout plan,
not the full release. Demo sources, server customization price, editor races,
order UI/pagination, performance, container/restore/rollback/public verification
remain mandatory. No commit, push or deployment.
