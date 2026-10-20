# Constructor gesture lifetime

Hardware audit: only custom image/text variants are offered; empty hardware
categories have an explicit empty state. No server hardware catalog/tariff is
invented. Keep the agreed 80 RUB placement policy unchanged.

Confirmed in current source: six independently installed window gesture groups
can outlive their editor; some ignore pointer identity, pointercancel or blur.
Deferred selection treats pointercancel as a completed tap.

- [x] Introduce one pointer-session utility with pointer identity, distinct
  completion/cancellation and teardown on replacement, blur/hidden and disposal.
- [x] Bind the session to each editor hook's actual mount; migrate panel, stage,
  decoration dragging/selection/rotation and cancel one-pointer work on pinch.
- [x] Test real event dispatch and stale callbacks, then verify gestures and
  interrupted editor lifetimes in a production-built browser; run frontend checks.
- [x] Update source explanations, offline project map and release evidence;
  preserve the current look, data and pricing. No commit/push/deployment.

Evidence: the previous compiled production bundle reproduced cancellation
selecting another decoration, a foreign pointer moving it, and retained panel
listeners after SPA exit. The new production bundle passes those scenarios,
normal drag/rotation, stage cancellation, pinch takeover, repeated blur and
interrupted editor exits. Browser instrumentation excludes Playwright's own
hit-target interceptor; it is not an application leak. Synthetic HTTP fixtures,
Chromium widths320/390/736/1280, no JS errors or document overflow. Screenshot
inspected. 470 frontend tests passed, full ESLint and production build passed;
existing AlumniSansSC fallback warning remains. No backend or pricing changes.
