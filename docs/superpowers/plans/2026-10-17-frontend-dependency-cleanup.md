# Frontend dependency and global-style cleanup

- [x] Measure the current production build's initial JavaScript on home/catalog
  with a controlled public-data fixture and cold browser contexts.
- [x] Remove the animation-engine dependency from plain text spans. Use native
  once-only visibility observation only for the requested view animation;
  preserve hover/click, measuring, SSR and interval cleanup behavior.
- [x] Remove unused direct dependencies and obsolete global CSS only after
  checking all consumers. Preserve public image URLs used by saved snapshots.
- [x] Verify text behavior and observer lifetime, then run frontend tests, lint
  and build. Measure the same routes after the change and inspect responsive UI.
- [x] Update the graph/descriptions and offline project map with exact evidence
  and the remaining release scope. Preserve the dirty checkout; no commit,
  push, deployment or deletion of user data.

Removing public assets alone does not prove a faster first render. Report
decoded JavaScript bytes and computed gzip equivalents separately from actual
wire transfer, page timing and production E2E.
