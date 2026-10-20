# Browser storage must not crash the application shell

Production-built Chromium reproduction before changes: denied local/session
storage makes AuthSessionBootstrap access a missing Zustand persist API on home,
catalog and constructor. A full quota throws from shell/session writes on all
three routes. Splash is currently disabled, but its effect still writes storage.

- [x] Give optional UI preferences and auth/cart caches a browser-only adapter
  with a document-memory fallback and guarded JSON hydration. No server memory
  persistence, no tokens in logs, no change to backend business data.
- [x] Migrate shell preference access and old PWA-key cleanup. Keep auth cookie
  mutation coordination and checkout recovery strict when storage is unavailable.
- [x] Test failures and hydration using real Zustand; verify before/after
  production-built home/catalog/PWA plus normal storage, and run frontend checks.
- [x] Update the project map and release evidence with exact limits: fallback
  state lasts only in the current document; purchase must never send without its
  durable recovery record. Production and the 80 RUB policy unchanged.
