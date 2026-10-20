# Legacy Project Read Boundary

**Goal:** Retire the unused browser-only project writer API while retaining historical project opening and explicit account migration.

**Scope:** Frontend only; no user-data writes, backend contract changes, new dependencies, commit or deployment. Existing PostgreSQL project CRUD remains authoritative for new saves. Historical local records retain their exact keys, IDs, numbering, images, canvas and snapshots.

- [x] Verify all consumers of savedItems helpers and old grid helpers; only legacy reading and explicit migration remain in production.
- [x] Move the historical record type/validator and read operation into `frontend/lib/projects/legacyRecords.ts`; make its purpose explicit with `LegacyProjectRecord`, `isLegacyProjectRecord`, `readLegacyConstructorDraft` and the two `LEGACY_*_STORAGE_KEY` constants.
- [x] Remove unused builders, serialization/writer/remover functions and old local-grid selection helpers. Keep the receipt-checked, lossless migration cleanup in `legacyMigration.ts`.
- [x] Replace old writer tests with literal historical records and read-only behavior tests; demonstrate denied storage failing before the fix and succeeding after it.
- [x] Update constructor and migration imports; preserve the migration key/fingerprint algorithm unchanged.
- [x] Verify parser, snapshots, lost response/retry, account changes, lossless cleanup, constructor/source tests, full frontend tests, lint and build.
- [x] Refresh map metadata and explanations, verify offline interactions, document results and remaining release work.

**Acceptance:** No general local project writer remains. Reading cannot alter local records; access failures cannot crash the constructor effect. Migration still requires explicit selection and account-scoped confirmation, preserves unknown raw records, and never deletes a changed/unconfirmed source.

**Results:** 37 focused tests and all 449 frontend tests passed, no skips; full ESLint and production build/TypeScript passed. Denied storage was reproduced before the fix. Production-built Next/Chromium with synthetic HTTP responses verified historical restoration, denied reads and malformed JSON, no source mutation or implicit project write, widths 320/390/736 and no JS errors/overflow. Eight offline map harnesses passed. No backend or deployment verification was repeated in this stage; the full release remains active.
