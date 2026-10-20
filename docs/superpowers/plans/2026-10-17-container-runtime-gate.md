# Container runtime release gate

The previous stage reduced shared frontend JavaScript and passed local checks.
CI currently builds images without loading or starting them. Local Docker is
unavailable (the executable points to a missing OrbStack installation).

- [x] Add an isolated runtime smoke command using the actual server Compose
  descriptor and built images, fresh random project/volumes, private synthetic
  configuration, bounded commands and cleanup on success or failure.
- [x] Implement checks for migrations, restricted runtime user, dependency readiness, public
  APIs through Next's rewrite, authentication rejection, standalone pages and
  referenced JS/CSS assets. Keep payment/delivery integrations disabled.
- [x] Configure CI image loading and runtime checks in the reusable quality gate.
- [x] Exercise HTTP validation against actual local HTTP responses and failure
  handling/isolation with controlled command transport; validate workflow and
  document exactly what has and has not run. Do not claim container success
  until an actual Docker execution succeeds. No push/deploy.

Evidence: 19 new tests passed; the 46 existing deployment tests passed in the
combined run (the new configuration test initially caught a missing public
MinIO URL, fixed and all 19 new tests re-run). Ruff/format and YAML passed.
Copied Next standalone package served home/catalog, 15 distinct JS/CSS assets
and sw.js; its owned process and temporary copy were removed. This is native
packaging evidence, not Docker proof. Actual Docker/CI execution remains open.
