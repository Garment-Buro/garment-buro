# Multi-channel authentication integration plan

**Goal:** Integrate the existing multi-channel backend into current main without exposing Telegram login to customers.

**Architecture:** Preserve the identity service, auth method registry, and notification outbox. Append migration 20261012_0056 after 20260929_0055; preserve internal employee identities. Email login stays the customer entry point; phone remains unavailable until a provider exists, Telegram remains disabled by default.

**Scope:** Existing commit f7c828d, adapted to current main. No production provider activation or credentials changes.

- [x] Establish identity/notification/migration test baseline (44 tests).
- [x] Confirm old multi-channel tests cannot run without the implementation.
- [x] Port implementation and append migration, retaining production identities.
- [x] Remove the inactive Telegram UI and verify email login is preserved.
- [ ] Run backend quality gates, frontend checks, migration checks and review.
- [ ] Create PR, wait for CI, merge, and verify remote main.

Review corrections: offload Argon2 through bounded worker threads, keep profile phones separate from authentication identifiers, and guard data-dependent schema rollback. Focused regression tests observed failing before fixes and passing afterward.
