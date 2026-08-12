# Stage 8: guarded web and PWA session compatibility

Status: complete for the bounded compatibility slice; disabled by default

Quality score: 93/100

## Safety boundary

This stage prepares the refactored frontend to use the short access token and
rotating HttpOnly refresh session delivered in Stage 7. It does not enable the
new identity boundary in any environment. Both
`IDENTITY_API_ENABLED=false` and
`NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=false` remain the defaults.

The client flag is compiled into the Next.js image. It must never be toggled
independently of the backend identity flag. No staging or production service,
database, bucket, email, browser storage, or installed PWA was changed during
this stage.

## Delivered

- `POST /api/auth/session/migrate`, which accepts only the legacy Bearer shape
  during the bounded grace window, creates an auditable target session, and
  sets the same protected refresh cookie as a new login;
- same-origin credentials on the centralized browser HTTP boundary so the
  host-only refresh cookie participates in refresh, migration, and logout;
- a build-time frontend cutover flag wired through the Dockerfile, both Compose
  configurations, and the environment template with a safe `false` default;
- memory-only v2 access tokens; Zustand persists only an unfinished logout
  intent, never the access token or profile payload;
- automatic initial refresh and seamless conversion of an existing persisted
  legacy Bearer token without another OTP login;
- one retry of authenticated profile, email-link, delete, and order requests
  after an authorization failure;
- per-tab single-flight refresh/logout and cross-tab coordination through Web
  Locks, a bounded local-storage mutex fallback, and BroadcastChannel session
  notifications;
- immediate anonymous UI on logout, durable pending-logout state, and retry on
  connectivity recovery or a bounded background interval so an old refresh
  cookie does not silently restore the account;
- recovery retries after transient initial refresh failures, while terminal
  missing/invalid-session responses cleanly resolve to the guest state;
- a session-ready UI boundary so the account popup does not flash a guest form
  while an installed PWA or web tab restores its cookie session;
- unchanged legacy persistence and local logout when the v2 flag is disabled.

The cross-tab local storage contains only an opaque session generation and a
short-lived lock owner. Access and refresh tokens are not written there.

## Verification

- complete backend quality gate: 88 tests passed, Ruff lint/format passed, and
  offline Alembic upgrade/downgrade through `20260811_0006` passed;
- focused identity service and HTTP contract checks for legacy-to-target
  session migration: passed;
- complete frontend quality gate: ESLint passed, 195 tests passed, TypeScript
  passed, and the production Next.js build completed;
- explicit production build with
  `NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=true`: passed;
- concurrent refresh success/failure reset and logout single-flight tests:
  passed;
- source contracts for memory-only persistence, guarded build configuration,
  bootstrap mounting, and authenticated-request routing: passed;
- same-origin cookie credential contract: passed;
- local and production Compose parsing with the build argument: passed;
- repository whitespace check: passed.

Docker/OrbStack was not running, so this evidence does not claim a real
PostgreSQL transaction/lock run, SMTP delivery, cookie handling in a browser,
multiple physical tabs, service-worker lifecycle, offline installed-PWA logout,
or a staging cutover.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 19/20 | API calls, store lifecycle, tab coordination, and bootstrap are separate focused modules behind the existing store boundary. |
| Security and privacy | 20/20 | V2 removes persistent access/profile data, keeps refresh HttpOnly, checks same origin, bounds legacy migration, and preserves pending logout. |
| Reliability and data safety | 19/20 | Per-tab single-flight, cross-tab locking/broadcast, one-shot 401 retry, transient recovery, offline logout retry, and default-off rollback are implemented. |
| Compatibility | 19/20 | Legacy mode is unchanged, old persisted sessions migrate without another OTP, current API/user shapes remain stable, and both web/PWA bootstrap from the root layout. |
| Verification | 16/20 | Full backend/frontend gates and both flag builds pass; real PostgreSQL, browser, installed PWA, and staging evidence remain intentionally unclaimed. |
| Total | 93/100 | The disabled compatibility slice exceeds the requested threshold without treating build tests as live cutover proof. |

## Staging cutover rehearsal

1. Deploy the current backend code with both identity flags still `false`.
2. Apply Alembic through `20260811_0006` to an isolated PostgreSQL target, run
   the reviewed identity import, and configure its exact fingerprint.
3. Start the notification worker with the target encryption-key ring and prove
   one non-customer test email through the real SMTP path.
4. Set a reviewed legacy-token grace cutoff no more than 31 days ahead and
   prebuild the frontend image with
   `NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=true`.
5. Switch the backend identity router and the prebuilt frontend image as one
   blue/green release. Prefer backend-first within the atomic switch; never
   leave only the frontend v2 image active against legacy auth.
6. Verify an existing persisted session, new OTP login, reload, access expiry,
   two-tab refresh, profile update, email change, order ownership, logout,
   offline logout/reconnect, installed-PWA restart, and account deletion.
7. Observe API/worker logs, security audits, outbox status, session counts, and
   legacy claim counts before considering production.

## Rollback

Restore the frontend image built with
`NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=false`, set
`IDENTITY_API_ENABLED=false`, and restart/switch both services. Retain target
users, sessions, audits, claims, notification rows, encryption keys, and the
legacy source for diagnosis. Do not downgrade identity migrations after target
activity exists. Existing target refresh cookies are path-scoped and become
inactive when the guarded router is disabled; legacy frontend state continues
to follow the pre-cutover behavior.
