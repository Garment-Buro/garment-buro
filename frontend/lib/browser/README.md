# Browser runtime

Browser-specific behavior has one ownership path. UI components should consume it and must not add their own user-agent checks.

## Responsibilities

- `providers/AppEnvironmentProvider.tsx` is the root layout boundary. It applies page-wide DOM data attributes, safe-area CSS variables, and the active theme color.
- `hooks/browser/useBrowserSurface.ts` detects the runtime surface once and exposes `pwa`, `safari26`, `safari18`, or `otherbrowser`.
- `lib/browser/utils/detectBrowserSurface.ts` contains pure browser detection.
- `lib/browser/utils/pageChrome.ts` maps routes to page colors and bottom offsets. Add route-level chrome changes here.
- `lib/browser/utils/splash.ts` owns splash route rules and the pre-hydration bootstrap script; `providers/SplashBoundary.tsx` owns its global lifecycle. It is a layout boundary, not a React Context provider.
- `lib/browser/utils/scriptLoader.ts` is the shared deferred-loader used by browser SDK integrations.
- `lib/browser/config/vendorScripts.ts` is the audited allowlist for third-party browser SDK assets. Business data still travels through the same-origin `/api` boundary; only the Yandex Maps and CDEK widget runtime assets load from their providers.
- `hooks/browser/useCookieConsent.ts` owns browser storage and splash-event coordination for the cookie banner.

## CSS contract

`AppEnvironmentProvider` writes `data-browser-surface` and `data-app-page` on both `html` and `body`. Safari 26 and PWA overrides belong in `app/globals.css` under those attributes, using `--app-top-color`, `--app-page-color`, and `--app-page-bottom-offset`.

When adding a page-wide browser behavior, put pure decisions in `lib/browser/utils`, state and subscriptions in `hooks/browser`, and mount the provider from `app/layout.tsx`. Keep page and visual component files free of user-agent, safe-area, and theme-color logic.
