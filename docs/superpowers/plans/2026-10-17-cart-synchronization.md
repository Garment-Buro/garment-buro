# Cart snapshot synchronization

Part of the release refactor, not proof that the release is ready.

- [x] Reproduce edits lost during initial GET, an empty server snapshot being
  ignored, and overlapping PUTs in the actual Zustand store.
- [x] Move synchronization ownership out of the store's UI/data actions.
  Serialize GET/PUT work, coalesce queued writes, and reject late initialization
  when the local snapshot changed. Apply an authoritative empty snapshot too.
- [x] Stop treating an HTTP failure as an absent cart. Keep local edits and
  expose a manual retry in the cart. Do not invent background retry loops.
- [x] Verify store races, failures/retry, production build and browser behavior.
  Update the project map and document the limits of this stage.

The existing timestamp protocol remains an intermediate limitation: it does not
provide compare-and-swap across tabs/devices. A later coordinated API/client
stage must replace clock ordering with a server revision and explicit conflict
handling. Serializing one document is necessary but does not prove that invariant.

Verification: six regression tests failed before the fix. Final frontend493
passed, no skips; ESLint and production build/TypeScript with identity V2 and
catalog writes enabled. Eight Zustand regressions plus three API checks cover
the races, single-flight initialization, errors/retry, no-store and the10-second
GET deadline through headers, success JSON and error bodies (real local HTTP).

Production-built Chromium before: a newer empty snapshot was uploaded over, and
a delayed GET resurrected a deleted line. After: both fixed; one in-flight PUT,
quantity snapshots2 then4; explicit retry after read/write503, desktop checkout,
and a stalled10-second GET. Seven cases,320/390/736/1280, no JS errors/overflow.
API responses were synthetic; backend persistence, multi-tab conflict resolution
and production were not verified by this browser fixture. Backend unchanged.
