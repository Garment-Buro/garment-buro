# Bounded customer order history

Replace the unbounded `/api/auth/orders` response with `{items, next_cursor}`;
24 summaries by default, maximum 100. Preserve ownership of canonical and
explicitly claimed historical orders. Read full order snapshots only when
the customer opens one order. No browser persistence or new cache.

- [x] Add bounded, indexed keyset selection across owned and claimed orders,
  without cart/customization/contact columns in summary queries. Cover overlap,
  new inserts, empty/final pages, invalid cursors and foreign ownership.
- [x] Replace repeated legacy claim ID scans with one conflict-safe insert/select
  of unclaimed imported orders matching a verified email; preserve existing claims.
- [x] Add reversible composite indexes and check migration/schema/query plans
  using PostgreSQL with a large unrelated order population.
- [x] Connect both customer history views to pagination and selected-detail
  loading; preserve loaded summaries on next-page failure and discard stale
  account/detail responses. Display only server-reported customer stages.
- [x] Verify focused API and frontend behavior, full relevant checks and browser
  interactions. Update documentation/map; no commit or deployment in this stage.

This changes the customer history response contract, so frontend and backend
must ship together. Staff order listing and guest order access retain their
existing contracts. Accepted historical prices/snapshots remain unchanged.
