# Bound public browser reads through the response body

The server storefront has a 2-second deadline. Browser storefront, people,
community, options and constructor product/price reads currently only stop when
their owner aborts. A stalled response leaves the view loading indefinitely.

- [x] Reproduce a stalled browser search against the current production build.
- [x] Add one 10-second public JSON read policy at the existing HTTP boundary.
  Keep caller cancellation and backend errors; include response body reading,
  release timers/listeners, and do not retry automatically. Purchase, auth,
  favorite writes and uploads retain their existing operation policies.
- [x] Verify first-page failure, next-page retention/retry, cancellation, stalled
  headers/body, normal responses and the six public API entry points. Run full
  frontend checks and production-built Chromium before/after.
- [x] Update the project map and release evidence with synthetic-test limits.
  Keep the replaceable 80 RUB formula and production unchanged.
